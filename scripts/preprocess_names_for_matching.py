#!/usr/bin/env python3
"""
Preprocess genealogy names for duplicate detection.

This script implements genealogy naming conventions and standardizes names
before duplicate detection is performed. It ensures "apples to apples" comparisons.

Key Preprocessing Steps:
1. Apply NN convention for missing given names
2. Handle ancient names (given name only - no placeholder surnames)
3. Preserve meaningful surname differences (especially for mothers)
4. Clean up embedded language variants
5. Set proper language codes
6. Normalize name formats

Usage:
    python preprocess_names_for_matching.py database.rmtree [--execute]

    Without --execute: Reports what would be changed (dry-run mode)
    With --execute: Actually makes the changes to the database
"""

import sys
import sqlite3
import argparse
import re
from pathlib import Path
from typing import Set, Dict, List, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime


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
class NamePreprocessingChange:
    """Represents a change to be made during preprocessing."""
    person_id: int
    name_id: int
    change_type: str
    description: str
    field: str
    old_value: Optional[str]
    new_value: Optional[str]
    person_context: str  # For display (name, dates, etc.)


class NamePreprocessor:
    """Preprocesses names for duplicate detection according to genealogy conventions."""

    # Genealogy convention: NN = No Name (given)
    NN_CONVENTION = "NN"

    # Placeholder surname patterns that indicate no real surname information
    PLACEHOLDER_SURNAME_PATTERNS = [
        r'^EndofLine$',
        r'^EOL$',
        r'^Unknown$',
        r'^UNKNOWN$',
        r'^\?+$',
        r'^-+$',
        r'^___+$',
    ]

    # Generic "MRS" type entries that are truly placeholders
    MRS_PLACEHOLDER_PATTERNS = [
        r'^MRS\.?$',
        r'^Mrs\.?$',
        r'^Ms\.?$',
        r'^Miss\.?$',
    ]

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

    # Language detection patterns
    FRENCH_NAME_PATTERNS = [
        r'\b(Jean|Marie|Pierre|Jacques|François|Francois|Louis|Michel|Henri|Paul|André|Andre|Joseph)\b',
        r'\b(Marguerite|Françoise|Francoise|Catherine|Anne|Elisabeth|Jeanne|Suzanne)\b',
    ]

    GERMAN_NAME_PATTERNS = [
        r'\b(Wilhelm|Friedrich|Heinrich|Johann|Karl|Ludwig|Hans|Otto|Bernhard|Bernard)\b',
        r'\b(Margarethe|Katharina|Elisabeth|Anna|Maria|Wilhelmine)\b',
    ]

    def __init__(self, db: SimpleRMDatabase):
        self.db = db
        self.changes: List[NamePreprocessingChange] = []
        self.stats = defaultdict(int)

    def analyze(self) -> None:
        """Analyze all names and identify preprocessing changes needed."""
        print("Analyzing names for preprocessing...")

        cursor = self.db.conn.cursor()

        # Get all name records with person context
        query = """
            SELECT
                n.NameID, n.OwnerID, n.Surname, n.Given, n.Prefix, n.Suffix,
                n.NameType, n.IsPrimary, n.Language,
                p.Sex,
                (SELECT Date FROM EventTable WHERE OwnerID = p.PersonID AND EventType = 1 AND IsPrimary = 1 LIMIT 1) AS BirthDate,
                (SELECT Date FROM EventTable WHERE OwnerID = p.PersonID AND EventType = 2 AND IsPrimary = 1 LIMIT 1) AS DeathDate
            FROM NameTable n
            JOIN PersonTable p ON n.OwnerID = p.PersonID
            ORDER BY n.OwnerID, n.IsPrimary DESC, n.NameID
        """

        cursor.execute(query)
        rows = cursor.fetchall()

        for row in rows:
            self._analyze_name_record(row)

        self._print_statistics()

    def _analyze_name_record(self, row) -> None:
        """Analyze a single name record."""
        person_id = row['OwnerID']
        name_id = row['NameID']
        surname = row['Surname']
        given = row['Given']
        prefix = row['Prefix']
        language = row['Language']
        is_primary = row['IsPrimary']
        sex = row['Sex']
        birth_date = row['BirthDate']
        death_date = row['DeathDate']

        # Create context string for display
        context = self._format_person_context(row)

        # 1. Apply NN convention for missing given names
        if not given or given.strip() == '':
            self._add_change(
                person_id, name_id, "nn_convention",
                "Apply NN convention for missing given name",
                "Given", given, self.NN_CONVENTION, context
            )
            given = self.NN_CONVENTION  # Update for further checks

        # 2. Check for embedded language variants
        if given and given != self.NN_CONVENTION:
            self._check_embedded_variants(person_id, name_id, 'Given', given, context)

        if surname:
            self._check_embedded_variants(person_id, name_id, 'Surname', surname, context)

        # 3. Check for placeholder surnames (but preserve meaningful ones)
        if surname and is_primary:
            self._check_placeholder_surname(person_id, name_id, surname, given, sex, context)

        # 4. Check language codes
        self._check_language_code(person_id, name_id, given, surname, language, is_primary, context)

        # 5. Check for MRS placeholders in given names
        if given and self._is_mrs_placeholder(given):
            self._add_change(
                person_id, name_id, "mrs_placeholder",
                "MRS placeholder in given name - should be reviewed",
                "Given", given, None, context
            )

    def _check_embedded_variants(self, person_id: int, name_id: int,
                                  field: str, value: str, context: str) -> None:
        """Check for embedded language variants in brackets or parentheses."""
        bracket_matches = self.BRACKET_VARIANT_PATTERN.findall(value)
        paren_matches = self.PAREN_VARIANT_PATTERN.findall(value)

        if bracket_matches:
            clean_value = self.BRACKET_VARIANT_PATTERN.sub('', value).strip()
            self._add_change(
                person_id, name_id, "embedded_variant",
                f"Embedded variant [{bracket_matches[0]}] should be separate name record",
                field, value, clean_value, context,
                extra_info=f"Variant: {bracket_matches[0]}"
            )

        if paren_matches:
            # Parentheses might be nicknames or variants - be more conservative
            # Only flag if it looks like a name variant (not a date or place)
            variant = paren_matches[0]
            if not re.search(r'\d{4}|\b(Jr|Sr|III|II|IV)\b', variant):
                clean_value = self.PAREN_VARIANT_PATTERN.sub('', value).strip()
                self._add_change(
                    person_id, name_id, "embedded_variant",
                    f"Possible embedded variant ({variant}) - review if should be separate record",
                    field, value, clean_value, context,
                    extra_info=f"Variant: {variant}"
                )

    def _check_placeholder_surname(self, person_id: int, name_id: int,
                                    surname: str, given: str, sex: int, context: str) -> None:
        """Check if surname is a placeholder that should be removed."""
        # Check against known placeholder patterns
        for pattern in self.PLACEHOLDER_SURNAME_PATTERNS:
            if re.match(pattern, surname, re.IGNORECASE):
                self._add_change(
                    person_id, name_id, "placeholder_surname",
                    "Placeholder surname should be removed",
                    "Surname", surname, None, context
                )
                return

        # Check for "EndofLine" type patterns where surname matches given name pattern
        # This would indicate a placeholder parent (e.g., "Smith" as parent of "John Smith")
        # But we WON'T flag this automatically - need context from family relationships

    def _check_language_code(self, person_id: int, name_id: int,
                             given: Optional[str], surname: Optional[str],
                             current_language: Optional[str], is_primary: bool,
                             context: str) -> None:
        """Check if language code is appropriate."""
        # Detect language from name patterns
        detected_lang = self._detect_language(given, surname)

        # If we detected a language and it's not set
        if detected_lang and not current_language:
            self._add_change(
                person_id, name_id, "missing_language",
                f"Detected {detected_lang} name without language code",
                "Language", current_language, detected_lang, context
            )

        # If language is set but doesn't match detection (and we have high confidence)
        elif detected_lang and current_language and detected_lang != current_language:
            # Only flag as warning, don't auto-change
            self._add_change(
                person_id, name_id, "language_mismatch",
                f"Language code '{current_language}' but name appears to be '{detected_lang}' - review",
                "Language", current_language, detected_lang, context,
                severity="low"
            )

        # Alternate names should have language codes
        if not is_primary and not current_language:
            self._add_change(
                person_id, name_id, "alternate_no_language",
                "Alternate name without language code",
                "Language", current_language, "en", context,
                severity="low"
            )

    def _detect_language(self, given: Optional[str], surname: Optional[str]) -> Optional[str]:
        """Detect language from name patterns."""
        name_text = ' '.join(filter(None, [given, surname]))

        if not name_text:
            return None

        # Check French patterns
        for pattern in self.FRENCH_NAME_PATTERNS:
            if re.search(pattern, name_text, re.IGNORECASE):
                return 'fr'

        # Check German patterns
        for pattern in self.GERMAN_NAME_PATTERNS:
            if re.search(pattern, name_text, re.IGNORECASE):
                return 'de'

        return None

    def _is_mrs_placeholder(self, given: str) -> bool:
        """Check if given name is a MRS placeholder."""
        for pattern in self.MRS_PLACEHOLDER_PATTERNS:
            if re.match(pattern, given, re.IGNORECASE):
                return True
        return False

    def _format_person_context(self, row) -> str:
        """Format person context for display."""
        given = row['Given'] or '(no given)'
        surname = row['Surname'] or '(no surname)'
        sex = {0: 'U', 1: 'M', 2: 'F'}.get(row['Sex'], 'U')

        dates = []
        if row['BirthDate']:
            dates.append(f"b. {row['BirthDate']}")
        if row['DeathDate']:
            dates.append(f"d. {row['DeathDate']}")

        date_str = f" ({', '.join(dates)})" if dates else ""

        return f"{given} {surname} [{sex}]{date_str}"

    def _add_change(self, person_id: int, name_id: int, change_type: str,
                    description: str, field: str, old_value: Optional[str],
                    new_value: Optional[str], context: str,
                    severity: str = "medium", extra_info: str = None) -> None:
        """Add a preprocessing change to the list."""
        if extra_info:
            description = f"{description} - {extra_info}"

        change = NamePreprocessingChange(
            person_id=person_id,
            name_id=name_id,
            change_type=change_type,
            description=description,
            field=field,
            old_value=old_value,
            new_value=new_value,
            person_context=context
        )
        self.changes.append(change)
        self.stats[change_type] += 1

    def _print_statistics(self) -> None:
        """Print statistics about changes found."""
        print(f"\n{'='*80}")
        print("PREPROCESSING CHANGES SUMMARY")
        print(f"{'='*80}\n")

        print(f"Total changes needed: {len(self.changes)}\n")

        print("By change type:")
        for change_type, count in sorted(self.stats.items(), key=lambda x: -x[1]):
            print(f"  {change_type:30s}: {count:6d}")

        print(f"\n{'='*80}\n")

    def print_changes_report(self, limit: int = 50) -> None:
        """Print detailed report of changes."""
        print("\nDETAILED CHANGES REPORT")
        print(f"{'='*80}\n")

        # Group by change type
        by_type = defaultdict(list)
        for change in self.changes:
            by_type[change.change_type].append(change)

        for change_type, changes in sorted(by_type.items()):
            print(f"\n{change_type.upper().replace('_', ' ')}: ({len(changes)} changes)")
            print("-" * 80)

            for i, change in enumerate(changes[:limit], 1):
                print(f"\n{i}. Person #{change.person_id}, Name #{change.name_id}")
                print(f"   Context: {change.person_context}")
                print(f"   Change:  {change.description}")
                print(f"   Field:   {change.field}")
                print(f"   Old:     '{change.old_value}'")
                print(f"   New:     '{change.new_value}'")

            if len(changes) > limit:
                print(f"\n   ... and {len(changes) - limit} more")

    def execute_changes(self) -> None:
        """Execute the preprocessing changes."""
        if not self.changes:
            print("No changes to execute.")
            return

        print(f"\nExecuting {len(self.changes)} changes...")

        cursor = self.db.conn.cursor()
        executed = 0

        for change in self.changes:
            try:
                # Only execute certain safe change types
                if change.change_type in ['nn_convention', 'missing_language',
                                          'embedded_variant', 'placeholder_surname']:
                    query = f"UPDATE NameTable SET {change.field} = ? WHERE NameID = ?"
                    cursor.execute(query, (change.new_value, change.name_id))
                    executed += 1

            except Exception as e:
                print(f"Error executing change for Name #{change.name_id}: {e}")

        self.db.conn.commit()
        print(f"Successfully executed {executed} changes.")

        # Note: Some changes (like creating separate name records for variants)
        # require more complex logic and should be handled by analyze_name_structure.py


def main():
    parser = argparse.ArgumentParser(
        description="Preprocess names for duplicate detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run mode (see what would change)
  python preprocess_names_for_matching.py database.rmtree

  # Actually make the changes
  python preprocess_names_for_matching.py database.rmtree --execute

  # Show detailed report of changes
  python preprocess_names_for_matching.py database.rmtree --report
        """
    )

    parser.add_argument('database', type=Path, help='Path to RootsMagic database (.rmtree)')
    parser.add_argument('--execute', action='store_true',
                       help='Actually execute changes (default is dry-run)')
    parser.add_argument('--report', action='store_true',
                       help='Show detailed report of changes')

    args = parser.parse_args()

    if not args.database.exists():
        print(f"Error: Database not found: {args.database}")
        sys.exit(1)

    print(f"Opening database: {args.database}")

    with SimpleRMDatabase(args.database) as db:
        preprocessor = NamePreprocessor(db)

        # Analyze all names
        preprocessor.analyze()

        # Show detailed report if requested
        if args.report:
            preprocessor.print_changes_report(limit=100)

        # Execute if requested
        if args.execute:
            response = input("\nDo you want to execute these changes? (yes/no): ")
            if response.lower() == 'yes':
                preprocessor.execute_changes()
                print("\nChanges executed successfully!")
            else:
                print("\nChanges not executed.")
        else:
            print("\nDRY-RUN MODE: No changes were made.")
            print("Run with --execute to apply changes.")
            print("Run with --report to see detailed change list.")

    print("\nPreprocessing complete!")


if __name__ == '__main__':
    main()
