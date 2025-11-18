#!/usr/bin/env python3
"""
Simplified test script to demonstrate name parsing and normalization:
1. Load GEDCOM data
2. Show original name data issues
3. Apply intelligent name parsing and normalization
4. Show what fixes would be applied
"""

import sys
from pathlib import Path
from typing import Dict, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from GedMerge.gedmerge.core.gedcom_parser import GedcomParser
from GedMerge.gedmerge.core.person import Person
from GedMerge.gedmerge.core.family import Family
from GedMerge.gedmerge.utils.name_parser import NameParser


def echo_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


def analyze_names(individuals: Dict[str, Person]) -> Dict:
    """Analyze name structure issues."""
    echo_section("ANALYZING ORIGINAL NAME DATA")

    issues = {
        'all_caps': [],
        'embedded_variants': [],
        'titles': [],
        'particles': [],
        'epithets': [],
        'ordinals': [],
        'missing_given': [],
    }

    for person_id, person in individuals.items():
        if not person.names:
            issues['missing_given'].append((person_id, "(no name)"))
            continue

        for name_str in person.names:
            # All caps check
            if name_str.isupper() and len(name_str) > 3:
                issues['all_caps'].append((person_id, name_str))

            # Embedded variants [xxx]
            if '[' in name_str and ']' in name_str:
                issues['embedded_variants'].append((person_id, name_str))

            # Titles
            titles = ['Sir', 'Lady', 'Lord', 'Baron', 'Duke', 'Count', 'Earl', 'King', 'Queen']
            if any(title in name_str for title in titles):
                issues['titles'].append((person_id, name_str))

            # Surname particles
            particles = ['von', 'van', 'de', 'du', 'della', 'di', 'af', 'ter']
            if any(particle in name_str.lower() for particle in particles):
                issues['particles'].append((person_id, name_str))

            # Epithets in quotes
            if '"' in name_str or "'" in name_str:
                issues['epithets'].append((person_id, name_str))

            # Ordinals
            if any(f' {ord}' in name_str for ord in ['II', 'III', 'IV', 'V', 'VI', 'VII']):
                issues['ordinals'].append((person_id, name_str))

    # Report findings
    print(f"\nScanned {len(individuals)} individuals for name structure issues:\n")

    for issue_type, examples in issues.items():
        if examples:
            print(f"{issue_type.upper().replace('_', ' ')}: {len(examples)} found")
            for i, (person_id, name) in enumerate(examples[:3]):
                print(f"  • {person_id}: {name}")
            if len(examples) > 3:
                print(f"  ... and {len(examples) - 3} more\n")

    return issues


def apply_parsing_and_show_fixes(individuals: Dict[str, Person]):
    """Parse names and show what fixes would be applied."""
    echo_section("APPLYING INTELLIGENT NAME PARSING")

    fixes = []

    for person_id, person in individuals.items():
        if not person.names:
            continue

        for name_str in person.names:
            # Parse the name
            parsed = NameParser.parse_name_field(name_str)

            # Track changes
            changes = []

            if name_str.isupper():
                changes.append("normalized from ALL CAPS")

            if parsed.prefix:
                changes.append(f"prefix: '{parsed.prefix}'")

            if parsed.epithets:
                changes.append(f"epithets: {', '.join(repr(e) for e in parsed.epithets)}")

            if parsed.ordinal:
                changes.append(f"ordinal: '{parsed.ordinal}'")

            if parsed.suffix:
                changes.append(f"suffix: '{parsed.suffix}'")

            if parsed.nickname:
                changes.append(f"nickname: '{parsed.nickname}'")

            # Reconstruct normalized form
            parts = []
            if parsed.prefix:
                parts.append(parsed.prefix)
            if parsed.given:
                parts.append(parsed.given)
            given_part = ' '.join(parts) if parts else ''

            surname_part = f"/{parsed.surname}/" if parsed.surname else ''

            suffix_parts = []
            if parsed.ordinal:
                suffix_parts.append(parsed.ordinal)
            if parsed.suffix:
                suffix_parts.append(parsed.suffix)
            suffix_str = ' ' + ', '.join(suffix_parts) if suffix_parts else ''

            normalized = f"{given_part} {surname_part}{suffix_str}".strip()

            if changes or (parsed.given and parsed.surname):
                fixes.append({
                    'person_id': person_id,
                    'original': name_str,
                    'normalized': normalized,
                    'changes': changes,
                    'parsed': parsed
                })

    print(f"\nProcessed {len(individuals)} individuals")
    print(f"Found {len(fixes)} names that need normalization\n")

    # Show examples
    if fixes:
        print("Sample Corrections (showing first 15):")
        print()
        for i, fix in enumerate(fixes[:15]):
            print(f"{i+1}. Person: {fix['person_id']}")
            print(f"   Original:   {fix['original']}")
            print(f"   Normalized: {fix['normalized']}")
            if fix['changes']:
                print(f"   Extracted:  {', '.join(fix['changes'])}")

            # Show parsed components
            p = fix['parsed']
            components = []
            if p.given: components.append(f"given='{p.given}'")
            if p.surname: components.append(f"surname='{p.surname}'")
            if p.prefix: components.append(f"prefix='{p.prefix}'")
            if p.suffix: components.append(f"suffix='{p.suffix}'")
            if p.nickname: components.append(f"nickname='{p.nickname}'")
            if p.epithets: components.append(f"epithets={p.epithets}")
            if p.ordinal: components.append(f"ordinal='{p.ordinal}'")

            if components:
                print(f"   Components: {', '.join(components)}")
            print()

        if len(fixes) > 15:
            print(f"... and {len(fixes) - 15} more fixes not shown")

    return fixes


def find_basic_duplicates(individuals: Dict[str, Person]):
    """Find potential duplicates using simple name matching."""
    echo_section("FINDING POTENTIAL DUPLICATE CANDIDATES")

    print("\nScanning for potential duplicates using name similarity...")

    # Group by surname for basic matching
    surname_groups = {}

    for person_id, person in individuals.items():
        if not person.names:
            continue

        for name_str in person.names:
            parsed = NameParser.parse_name_field(name_str)
            if parsed.surname:
                surname = parsed.surname.lower().strip()
                if surname not in surname_groups:
                    surname_groups[surname] = []
                surname_groups[surname].append((person_id, person, parsed))

    # Find groups with multiple people
    duplicates = []
    for surname, people in surname_groups.items():
        if len(people) > 1:
            # Compare given names within surname group
            for i, (id1, p1, parsed1) in enumerate(people):
                for id2, p2, parsed2 in people[i+1:]:
                    # Simple similarity check
                    if parsed1.given and parsed2.given:
                        g1 = parsed1.given.lower()
                        g2 = parsed2.given.lower()

                        # Check if names are similar
                        if g1 == g2 or g1 in g2 or g2 in g1:
                            duplicates.append({
                                'id1': id1,
                                'id2': id2,
                                'person1': p1,
                                'person2': p2,
                                'surname': surname,
                                'given1': parsed1.given,
                                'given2': parsed2.given,
                            })

    print(f"\nFound {len(duplicates)} potential duplicate pairs based on name similarity\n")

    if duplicates:
        print("Sample Duplicate Candidates (showing first 10):")
        print()

        for i, dup in enumerate(duplicates[:10]):
            print(f"{i+1}. Potential Match:")
            print(f"   Person 1: {dup['id1']}")
            for name in dup['person1'].names:
                print(f"     Name: {name}")
            b1 = dup['person1'].get_birth_year()
            d1 = dup['person1'].get_death_year()
            if b1 or d1:
                print(f"     Birth: {b1 or 'Unknown'}, Death: {d1 or 'Unknown'}")

            print(f"   Person 2: {dup['id2']}")
            for name in dup['person2'].names:
                print(f"     Name: {name}")
            b2 = dup['person2'].get_birth_year()
            d2 = dup['person2'].get_death_year()
            if b2 or d2:
                print(f"     Birth: {b2 or 'Unknown'}, Death: {d2 or 'Unknown'}")

            print(f"   Match Reason: Same surname '{dup['surname']}', similar given names")
            print()

        if len(duplicates) > 10:
            print(f"... and {len(duplicates) - 10} more potential duplicates")

    return duplicates


def main():
    """Main entry point."""
    echo_section("GENEALOGY NAME PARSING & NORMALIZATION TEST")

    # Determine GEDCOM file
    script_dir = Path(__file__).parent
    gedcom_path = script_dir / 'GedMerge' / 'GEDCOM' / 'Joel2020.ged'

    if len(sys.argv) > 1:
        gedcom_path = Path(sys.argv[1])

    if not gedcom_path.exists():
        print(f"\nError: GEDCOM file not found: {gedcom_path}")
        print(f"\nAvailable GEDCOM files:")
        for ged_file in (script_dir / 'GedMerge' / 'GEDCOM').glob('*.ged'):
            print(f"  - {ged_file.name}")
        return 1

    print(f"\nTest file: {gedcom_path.name}")
    print(f"Path: {gedcom_path}")

    # Load data
    echo_section("STEP 1: LOADING GEDCOM DATA")
    parser = GedcomParser()
    individuals, families = parser.load_gedcom(str(gedcom_path))

    stats = parser.get_statistics()
    print(f"\n✓ Loaded {stats['num_individuals']} individuals")
    print(f"✓ Loaded {stats['num_families']} families")
    print(f"✓ Demographics: {stats['num_males']} males, {stats['num_females']} females, {stats['num_unknown_sex']} unknown")
    if 'earliest_year' in stats:
        print(f"✓ Date range: {stats['earliest_year']} - {stats['latest_year']}")

    # Analyze names
    issues = analyze_names(individuals)

    # Apply parsing
    fixes = apply_parsing_and_show_fixes(individuals)

    # Find duplicates
    duplicates = find_basic_duplicates(individuals)

    # Summary
    echo_section("SUMMARY")
    print(f"\n✓ Analyzed {len(individuals)} individuals")
    print(f"✓ Identified {sum(len(v) for v in issues.values())} name structure issues")
    print(f"✓ Prepared {len(fixes)} name normalization fixes")
    print(f"✓ Found {len(duplicates)} potential duplicate pairs")
    print("\nNext Steps:")
    print("  1. Review the name parsing fixes above")
    print("  2. Apply normalization to standardize name fields")
    print("  3. Review duplicate candidates for consolidation")
    print("  4. Use tree-aware sanity checking before merging")
    print()

    return 0


if __name__ == '__main__':
    sys.exit(main())
