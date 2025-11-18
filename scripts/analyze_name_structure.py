#!/usr/bin/env python3
"""
Analyze and fix structural and language issues in RootsMagic name records.

This script identifies and reports on:
1. Structural issues:
   - Names with embedded language variants (e.g., "Margaret [Marguerite]")
   - Reversed name formats
   - Missing given or surname fields
   - Titles in wrong fields
   - Multiple variants in single fields

2. Language issues:
   - Multiple language variants not using separate name records
   - Language field not set appropriately
   - Alternate names without language codes

The script can optionally fix these issues by:
- Creating separate name records for different language variants
- Setting appropriate language codes
- Cleaning up structural issues
"""

import sys
import sqlite3
import argparse
import re
from pathlib import Path
from typing import Set, Dict, List, Optional, Tuple, Pattern
from collections import defaultdict
from dataclasses import dataclass

# Simplified database access - avoid importing full GedMerge to avoid dependencies
class SimpleRMDatabase:
    """Minimal RootsMagic database access."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row

        # Register RMNOCASE collation
        def rmnocase_collation(s1: str, s2: str) -> int:
            s1_upper = s1.upper() if s1 else ''
            s2_upper = s2.upper() if s2 else ''
            return (s1_upper > s2_upper) - (s1_upper < s2_upper)

        self.conn.create_collation("RMNOCASE", rmnocase_collation)

    def close(self):
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


@dataclass(slots=True)
class NameIssue:
    """Represents an issue found with a name record."""
    person_id: int
    name_id: int
    issue_type: str
    description: str
    current_value: str
    suggested_fix: Optional[str] = None
    severity: str = "medium"  # low, medium, high


class NameStructureAnalyzer:
    """Analyzes and fixes structural and language issues in name records."""

    # Language variant patterns
    BRACKET_VARIANT_PATTERN = re.compile(r'\[([^\]]+)\]')
    PAREN_VARIANT_PATTERN = re.compile(r'\(([^\)]+)\)')

    # Common language markers
    LANGUAGE_MARKERS = {
        'aka': 'en',
        'also known as': 'en',
        'dit': 'fr',  # French "called"
        'genannt': 'de',  # German "called"
        'detto': 'it',  # Italian "called"
    }

    # Common name patterns by language
    FRENCH_PATTERNS = [
        r'\b(Jean|Marie|Pierre|Jacques|François|Louis|Michel|Henri|Paul|André|Joseph)\b',
        r'\b(Marguerite|Françoise|Catherine|Anne|Elisabeth|Jeanne)\b',
    ]

    GERMAN_PATTERNS = [
        r'\b(Wilhelm|Friedrich|Heinrich|Johann|Karl|Ludwig|Hans|Otto)\b',
        r'\b(Margarethe|Katharina|Elisabeth|Anna|Maria|Wilhelmine)\b',
    ]

    # Title patterns that shouldn't be in given names
    TITLE_PATTERNS = [
        r'^(MRS?\.?|MS\.?|MISS|DR\.?|REV\.?)\s+',
        r'^(SIR|LADY|LORD|DAME)\s+',
    ]

    def __init__(self, db: SimpleRMDatabase, verbose: bool = False):
        self.db = db
        self.verbose = verbose
        self.issues: List[NameIssue] = []
        self.stats = defaultdict(int)

    def analyze_all_names(self) -> Dict[str, List[NameIssue]]:
        """Analyze all name records in the database."""
        print("Loading all name records...")

        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT n.NameID, n.OwnerID, n.Surname, n.Given, n.Prefix, n.Suffix,
                   n.Nickname, n.NameType, n.IsPrimary, n.Language
            FROM NameTable n
            JOIN PersonTable p ON n.OwnerID = p.PersonID
            ORDER BY n.OwnerID, n.IsPrimary DESC, n.NameID
        """)

        name_records = cursor.fetchall()
        print(f"Analyzing {len(name_records)} name records...")

        issues_by_type = defaultdict(list)

        for row in name_records:
            name_id, owner_id, surname, given, prefix, suffix, nickname, name_type, is_primary, language = row

            # Check for embedded language variants
            self._check_embedded_variants(owner_id, name_id, given, surname, nickname, issues_by_type)

            # Check for structural issues
            self._check_structural_issues(owner_id, name_id, given, surname, prefix, suffix, is_primary, issues_by_type)

            # Check for language issues
            self._check_language_issues(owner_id, name_id, given, surname, language, is_primary, issues_by_type)

            # Check for title issues
            self._check_title_issues(owner_id, name_id, given, prefix, issues_by_type)

        return issues_by_type

    def _check_embedded_variants(self, person_id: int, name_id: int,
                                 given: Optional[str], surname: Optional[str],
                                 nickname: Optional[str],
                                 issues_by_type: Dict[str, List[NameIssue]]):
        """Check for language variants embedded in name fields with brackets/parens."""

        # Check given name
        if given:
            bracket_matches = self.BRACKET_VARIANT_PATTERN.findall(given)
            if bracket_matches:
                issue = NameIssue(
                    person_id=person_id,
                    name_id=name_id,
                    issue_type="embedded_variant_bracket",
                    description=f"Given name has bracketed variant(s): {bracket_matches}",
                    current_value=given,
                    suggested_fix=self.BRACKET_VARIANT_PATTERN.sub('', given).strip(),
                    severity="high"
                )
                issues_by_type['embedded_variant_bracket'].append(issue)
                self.stats['embedded_variants'] += 1

            paren_matches = self.PAREN_VARIANT_PATTERN.findall(given)
            # Only flag if it looks like a name variant, not a birth name notation like "(née ...)"
            if paren_matches and not any(marker in given.lower() for marker in ['née', 'nee', 'born']):
                issue = NameIssue(
                    person_id=person_id,
                    name_id=name_id,
                    issue_type="embedded_variant_paren",
                    description=f"Given name has parenthetical variant(s): {paren_matches}",
                    current_value=given,
                    suggested_fix=self.PAREN_VARIANT_PATTERN.sub('', given).strip(),
                    severity="medium"
                )
                issues_by_type['embedded_variant_paren'].append(issue)
                self.stats['embedded_variants'] += 1

        # Check surname
        if surname:
            bracket_matches = self.BRACKET_VARIANT_PATTERN.findall(surname)
            if bracket_matches:
                issue = NameIssue(
                    person_id=person_id,
                    name_id=name_id,
                    issue_type="embedded_variant_bracket_surname",
                    description=f"Surname has bracketed variant(s): {bracket_matches}",
                    current_value=surname,
                    suggested_fix=self.BRACKET_VARIANT_PATTERN.sub('', surname).strip(),
                    severity="high"
                )
                issues_by_type['embedded_variant_bracket_surname'].append(issue)
                self.stats['embedded_variants'] += 1

    def _check_structural_issues(self, person_id: int, name_id: int,
                                 given: Optional[str], surname: Optional[str],
                                 prefix: Optional[str], suffix: Optional[str],
                                 is_primary: bool,
                                 issues_by_type: Dict[str, List[NameIssue]]):
        """Check for structural issues in name records."""

        # Missing given name in primary record
        if is_primary and (not given or not given.strip()):
            if surname and surname.strip():
                issue = NameIssue(
                    person_id=person_id,
                    name_id=name_id,
                    issue_type="missing_given_name",
                    description="Primary name missing given name (surname only)",
                    current_value=f"Surname: {surname}",
                    severity="high"
                )
                issues_by_type['missing_given_name'].append(issue)
                self.stats['missing_given'] += 1

        # Missing surname in primary record (less common but still an issue)
        if is_primary and (not surname or not surname.strip()):
            if given and given.strip():
                issue = NameIssue(
                    person_id=person_id,
                    name_id=name_id,
                    issue_type="missing_surname",
                    description="Primary name missing surname",
                    current_value=f"Given: {given}",
                    severity="medium"
                )
                issues_by_type['missing_surname'].append(issue)
                self.stats['missing_surname'] += 1

        # Check for names that might be reversed (surname in given, given in surname)
        if given and surname:
            # Common pattern: surname has comma (e.g., "Smith, John" stored incorrectly)
            if ',' in given or ',' in surname:
                issue = NameIssue(
                    person_id=person_id,
                    name_id=name_id,
                    issue_type="possible_reversed_name",
                    description="Name may be reversed (contains comma)",
                    current_value=f"Given: '{given}', Surname: '{surname}'",
                    severity="medium"
                )
                issues_by_type['possible_reversed_name'].append(issue)
                self.stats['possibly_reversed'] += 1

    def _check_language_issues(self, person_id: int, name_id: int,
                               given: Optional[str], surname: Optional[str],
                               language: Optional[str],
                               is_primary: bool,
                               issues_by_type: Dict[str, List[NameIssue]]):
        """Check for language-related issues."""

        if not given:
            return

        # Detect likely French names without language set
        is_likely_french = any(re.search(pattern, given, re.IGNORECASE) for pattern in self.FRENCH_PATTERNS)

        # Detect likely German names without language set
        is_likely_german = any(re.search(pattern, given, re.IGNORECASE) for pattern in self.GERMAN_PATTERNS)

        if is_likely_french and (not language or language != 'fr'):
            issue = NameIssue(
                person_id=person_id,
                name_id=name_id,
                issue_type="missing_french_language",
                description="Name appears to be French but language not set",
                current_value=f"Given: '{given}', Language: {language or 'None'}",
                suggested_fix="fr",
                severity="low"
            )
            issues_by_type['missing_french_language'].append(issue)
            self.stats['missing_language'] += 1

        if is_likely_german and (not language or language != 'de'):
            issue = NameIssue(
                person_id=person_id,
                name_id=name_id,
                issue_type="missing_german_language",
                description="Name appears to be German but language not set",
                current_value=f"Given: '{given}', Language: {language or 'None'}",
                suggested_fix="de",
                severity="low"
            )
            issues_by_type['missing_german_language'].append(issue)
            self.stats['missing_language'] += 1

        # Check for alternate names without language codes
        if not is_primary and not language:
            issue = NameIssue(
                person_id=person_id,
                name_id=name_id,
                issue_type="alternate_name_no_language",
                description="Alternate name without language code",
                current_value=f"Given: '{given}', Surname: '{surname}'",
                severity="low"
            )
            issues_by_type['alternate_name_no_language'].append(issue)
            self.stats['alternate_no_language'] += 1

    def _check_title_issues(self, person_id: int, name_id: int,
                           given: Optional[str], prefix: Optional[str],
                           issues_by_type: Dict[str, List[NameIssue]]):
        """Check for titles in wrong fields."""

        if not given:
            return

        # Check if given name starts with a title
        given_upper = given.upper()
        for pattern in self.TITLE_PATTERNS:
            if re.match(pattern, given_upper):
                title_match = re.match(pattern, given_upper).group(1)
                suggested_given = re.sub(pattern, '', given, flags=re.IGNORECASE).strip()

                issue = NameIssue(
                    person_id=person_id,
                    name_id=name_id,
                    issue_type="title_in_given_name",
                    description=f"Title '{title_match}' found in given name",
                    current_value=given,
                    suggested_fix=suggested_given if suggested_given else None,
                    severity="medium"
                )
                issues_by_type['title_in_given_name'].append(issue)
                self.stats['title_in_given'] += 1
                break

    def print_summary(self, issues_by_type: Dict[str, List[NameIssue]]):
        """Print a summary of all issues found."""
        print("\n" + "="*80)
        print("NAME STRUCTURE AND LANGUAGE ANALYSIS SUMMARY")
        print("="*80)

        total_issues = sum(len(issues) for issues in issues_by_type.values())
        print(f"\nTotal issues found: {total_issues:,}")

        print("\n=== ISSUE BREAKDOWN ===")

        # Group by category
        structural_issues = [
            'embedded_variant_bracket',
            'embedded_variant_paren',
            'embedded_variant_bracket_surname',
            'missing_given_name',
            'missing_surname',
            'possible_reversed_name',
            'title_in_given_name',
        ]

        language_issues = [
            'missing_french_language',
            'missing_german_language',
            'alternate_name_no_language',
        ]

        print("\nStructural Issues:")
        structural_count = 0
        for issue_type in structural_issues:
            if issue_type in issues_by_type:
                count = len(issues_by_type[issue_type])
                structural_count += count
                print(f"  {issue_type:40s}: {count:6,}")
        print(f"  {'TOTAL STRUCTURAL':40s}: {structural_count:6,}")

        print("\nLanguage Issues:")
        language_count = 0
        for issue_type in language_issues:
            if issue_type in issues_by_type:
                count = len(issues_by_type[issue_type])
                language_count += count
                print(f"  {issue_type:40s}: {count:6,}")
        print(f"  {'TOTAL LANGUAGE':40s}: {language_count:6,}")

        # Show severity breakdown
        print("\n=== SEVERITY BREAKDOWN ===")
        severity_counts = defaultdict(int)
        for issues in issues_by_type.values():
            for issue in issues:
                severity_counts[issue.severity] += 1

        for severity in ['high', 'medium', 'low']:
            if severity in severity_counts:
                print(f"  {severity.upper():10s}: {severity_counts[severity]:6,}")

    def print_detailed_report(self, issues_by_type: Dict[str, List[NameIssue]],
                             issue_type: Optional[str] = None,
                             limit: int = 50):
        """Print detailed report of issues."""
        print("\n" + "="*80)
        print("DETAILED ISSUE REPORT")
        print("="*80)

        if issue_type:
            if issue_type not in issues_by_type:
                print(f"\nNo issues found of type: {issue_type}")
                return
            issues_to_show = {issue_type: issues_by_type[issue_type]}
        else:
            issues_to_show = issues_by_type

        for issue_type, issues in issues_to_show.items():
            print(f"\n--- {issue_type} ({len(issues)} found) ---")

            for i, issue in enumerate(issues[:limit]):
                print(f"\n{i+1}. Person ID: {issue.person_id}, Name ID: {issue.name_id}")
                print(f"   Severity: {issue.severity.upper()}")
                print(f"   Issue: {issue.description}")
                print(f"   Current: {issue.current_value}")
                if issue.suggested_fix:
                    print(f"   Suggested fix: {issue.suggested_fix}")

            if len(issues) > limit:
                print(f"\n... and {len(issues) - limit:,} more")

    def extract_language_variants(self, name_field: str) -> List[Tuple[str, Optional[str]]]:
        """
        Extract language variants from a name field.

        Returns:
            List of tuples: (cleaned_name, variant_name)
        """
        variants = []

        # Extract bracketed variants
        bracket_matches = self.BRACKET_VARIANT_PATTERN.findall(name_field)
        if bracket_matches:
            # Main name is what's outside the brackets
            main_name = self.BRACKET_VARIANT_PATTERN.sub('', name_field).strip()
            variants.append((main_name, None))

            for variant in bracket_matches:
                variants.append((variant.strip(), None))
        else:
            variants.append((name_field, None))

        return variants

    def fix_embedded_variants(self, dry_run: bool = True):
        """
        Fix embedded language variants by creating separate name records.

        Args:
            dry_run: If True, only show what would be changed
        """
        print("\n" + "="*80)
        print("FIXING EMBEDDED LANGUAGE VARIANTS")
        print("="*80)

        cursor = self.db.conn.cursor()

        # Find all names with embedded variants
        cursor.execute("""
            SELECT NameID, OwnerID, Surname, Given, Prefix, Suffix, Nickname,
                   NameType, IsPrimary, Language
            FROM NameTable
            WHERE Given LIKE '%[%]%' OR Surname LIKE '%[%]%'
            ORDER BY OwnerID, IsPrimary DESC
        """)

        records_to_fix = cursor.fetchall()
        print(f"\nFound {len(records_to_fix)} name records with embedded variants")

        if dry_run:
            print("\n[DRY RUN MODE] - No changes will be made")

        fixes_made = 0
        new_records_created = 0

        for row in records_to_fix[:50 if dry_run else None]:  # Limit in dry run
            name_id, owner_id, surname, given, prefix, suffix, nickname, name_type, is_primary, language = row

            if not given:
                continue

            # Extract variants from given name
            variants = []
            if '[' in given:
                bracket_matches = self.BRACKET_VARIANT_PATTERN.findall(given)
                main_given = self.BRACKET_VARIANT_PATTERN.sub('', given).strip()

                print(f"\nPerson ID {owner_id}, Name ID {name_id}:")
                print(f"  Original: {given}")
                print(f"  Main name: {main_given}")
                print(f"  Variants: {bracket_matches}")

                if dry_run:
                    print(f"  [DRY RUN] Would update main name to: {main_given}")
                    for i, variant in enumerate(bracket_matches):
                        print(f"  [DRY RUN] Would create alternate name: {variant} {surname or ''}")
                else:
                    # Update main name
                    cursor.execute("""
                        UPDATE NameTable
                        SET Given = ?
                        WHERE NameID = ?
                    """, (main_given, name_id))
                    fixes_made += 1

                    # Create alternate name records for variants
                    for variant in bracket_matches:
                        # Get the next available NameID
                        cursor.execute("SELECT MAX(NameID) FROM NameTable")
                        max_id = cursor.fetchone()[0] or 0
                        new_name_id = max_id + 1

                        # Determine language (simplified - could be enhanced)
                        variant_language = self._detect_language(variant)

                        cursor.execute("""
                            INSERT INTO NameTable
                            (NameID, OwnerID, Surname, Given, Prefix, Suffix, Nickname,
                             NameType, IsPrimary, Language)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
                        """, (new_name_id, owner_id, surname, variant, prefix, suffix,
                              None, name_type, variant_language))

                        new_records_created += 1
                        print(f"  Created alternate name record: {variant} {surname or ''} (Language: {variant_language})")

        if not dry_run:
            self.db.conn.commit()
            print(f"\n✓ Fixed {fixes_made} name records")
            print(f"✓ Created {new_records_created} new alternate name records")
        else:
            print(f"\n[DRY RUN] Would fix {len(records_to_fix)} name records")

    def _detect_language(self, name: str) -> Optional[str]:
        """Detect language of a name (simplified heuristic)."""
        # Check French patterns
        if any(re.search(pattern, name, re.IGNORECASE) for pattern in self.FRENCH_PATTERNS):
            return 'fr'

        # Check German patterns
        if any(re.search(pattern, name, re.IGNORECASE) for pattern in self.GERMAN_PATTERNS):
            return 'de'

        # Default to English
        return 'en'


def main():
    parser = argparse.ArgumentParser(
        description="Analyze and fix structural and language issues in RootsMagic name records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all names and show summary
  python analyze_name_structure.py database.rmtree

  # Show detailed report for specific issue type
  python analyze_name_structure.py database.rmtree --detail embedded_variant_bracket

  # Fix embedded variants (dry run)
  python analyze_name_structure.py database.rmtree --fix-variants --dry-run

  # Actually fix embedded variants
  python analyze_name_structure.py database.rmtree --fix-variants --execute
        """
    )

    parser.add_argument(
        'database',
        type=str,
        help='Path to RootsMagic .rmtree database file'
    )

    parser.add_argument(
        '--detail',
        type=str,
        help='Show detailed report for specific issue type'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Limit number of examples in detailed report (default: 50)'
    )

    parser.add_argument(
        '--fix-variants',
        action='store_true',
        help='Fix embedded language variants by creating separate name records'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        default=True,
        help='Preview changes without making them (default)'
    )

    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually make changes to the database'
    )

    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show verbose output'
    )

    args = parser.parse_args()

    # Validate database file
    db_path = Path(args.database)
    if not db_path.exists():
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)

    # Determine if we're in dry run mode
    dry_run = not args.execute

    try:
        # Open database
        with SimpleRMDatabase(db_path) as db:
            analyzer = NameStructureAnalyzer(db, verbose=args.verbose)

            # Analyze all names
            issues_by_type = analyzer.analyze_all_names()

            # Print summary
            analyzer.print_summary(issues_by_type)

            # Print detailed report if requested
            if args.detail:
                analyzer.print_detailed_report(issues_by_type, args.detail, args.limit)
            else:
                # Show sample of high-severity issues
                high_severity_types = [
                    'embedded_variant_bracket',
                    'embedded_variant_bracket_surname',
                    'missing_given_name',
                ]

                for issue_type in high_severity_types:
                    if issue_type in issues_by_type and len(issues_by_type[issue_type]) > 0:
                        print(f"\n=== Sample of {issue_type} ===")
                        analyzer.print_detailed_report(issues_by_type, issue_type, limit=10)

            # Fix variants if requested
            if args.fix_variants:
                if not dry_run:
                    response = input("\nWARNING: This will modify the database. Are you sure? Type 'yes' to continue: ")
                    if response.lower() != 'yes':
                        print("Aborted.")
                        sys.exit(0)

                analyzer.fix_embedded_variants(dry_run=dry_run)

        print("\n✓ Analysis complete")

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
