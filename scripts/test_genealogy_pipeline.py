#!/usr/bin/env python3
"""
Test script to demonstrate genealogy data processing pipeline:
1. Load GEDCOM data
2. Show original name data
3. Apply intelligent name parsing and normalization
4. Run duplicate detection with tree-aware sanity checking
5. Show consolidation candidates
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Set

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from GedMerge.gedmerge.core.gedcom_parser import GedcomParser
from GedMerge.gedmerge.core.person import Person
from GedMerge.gedmerge.core.family import Family
from GedMerge.gedmerge.utils.name_parser import NameParser
from GedMerge.gedmerge.matching.matcher import PersonMatcher
from GedMerge.gedmerge.matching.scorer import MatchScorer


class PipelineTester:
    """Test the genealogy processing pipeline."""

    def __init__(self, gedcom_path: str):
        """Initialize with GEDCOM file path."""
        self.gedcom_path = gedcom_path
        self.individuals: Dict[str, Person] = {}
        self.families: Dict[str, Family] = {}
        self.fixes_applied: List[Dict] = []

    def load_data(self):
        """Load GEDCOM data."""
        print("=" * 80)
        print("STEP 1: LOADING GEDCOM DATA")
        print("=" * 80)

        parser = GedcomParser()
        self.individuals, self.families = parser.load_gedcom(self.gedcom_path)

        stats = parser.get_statistics()
        print(f"\nLoaded {stats['num_individuals']} individuals")
        print(f"Loaded {stats['num_families']} families")
        print(f"Males: {stats['num_males']}, Females: {stats['num_females']}, Unknown: {stats['num_unknown_sex']}")
        if 'earliest_year' in stats:
            print(f"Date range: {stats['earliest_year']} - {stats['latest_year']}")

    def analyze_original_names(self):
        """Analyze and show issues with original name data."""
        print("\n" + "=" * 80)
        print("STEP 2: ANALYZING ORIGINAL NAME DATA")
        print("=" * 80)

        issues = {
            'all_caps': [],
            'embedded_variants': [],
            'misplaced_titles': [],
            'missing_given': [],
            'particles_in_wrong_place': [],
            'epithets': [],
            'ordinals': [],
        }

        for person_id, person in self.individuals.items():
            if not person.names:
                continue

            for name_str in person.names:
                # Check for all caps
                if name_str.isupper() and len(name_str) > 3:
                    issues['all_caps'].append((person_id, name_str))

                # Check for embedded language variants [xxx]
                if '[' in name_str and ']' in name_str:
                    issues['embedded_variants'].append((person_id, name_str))

                # Check for titles that might be misplaced
                title_words = ['Sir', 'Lady', 'Lord', 'Baron', 'Duke', 'Count', 'Earl']
                for title in title_words:
                    if title in name_str:
                        issues['misplaced_titles'].append((person_id, name_str))
                        break

                # Check for surname particles
                particles = ['von', 'van', 'de', 'du', 'della', 'di']
                for particle in particles:
                    if particle in name_str.lower():
                        issues['particles_in_wrong_place'].append((person_id, name_str))
                        break

                # Check for epithets in quotes
                if '"' in name_str or "'" in name_str:
                    issues['epithets'].append((person_id, name_str))

                # Check for ordinals (II, III, IV)
                if any(ord_str in name_str for ord_str in [' II', ' III', ' IV', ' V', ' VI']):
                    issues['ordinals'].append((person_id, name_str))

        # Display findings (limited to first 5 of each type)
        print("\nIssues found in name data:")
        for issue_type, examples in issues.items():
            if examples:
                print(f"\n{issue_type.upper().replace('_', ' ')}: {len(examples)} found")
                for i, (person_id, name) in enumerate(examples[:5]):
                    print(f"  - {person_id}: {name}")
                if len(examples) > 5:
                    print(f"  ... and {len(examples) - 5} more")

        return issues

    def apply_name_parsing(self):
        """Apply intelligent name parsing and normalization."""
        print("\n" + "=" * 80)
        print("STEP 3: APPLYING INTELLIGENT NAME PARSING")
        print("=" * 80)

        self.fixes_applied = []

        for person_id, person in self.individuals.items():
            if not person.names:
                continue

            for i, name_str in enumerate(person.names):
                original = name_str

                # Parse the name
                parsed = NameParser.parse_name(name_str)

                # Track what changed
                changes = []

                # Check if normalization would help
                if name_str.isupper():
                    changes.append("converted from ALL CAPS")

                if parsed.suffix:
                    changes.append(f"extracted suffix: '{parsed.suffix}'")

                if parsed.prefix:
                    changes.append(f"extracted prefix: '{parsed.prefix}'")

                if parsed.epithet:
                    changes.append(f"extracted epithet: '{parsed.epithet}'")

                if parsed.ordinal:
                    changes.append(f"extracted ordinal: '{parsed.ordinal}'")

                if parsed.particle:
                    changes.append(f"identified particle: '{parsed.particle}'")

                # Build normalized form
                normalized = parsed.to_gedcom()

                if normalized != original:
                    self.fixes_applied.append({
                        'person_id': person_id,
                        'original': original,
                        'normalized': normalized,
                        'changes': changes,
                        'parsed': parsed
                    })

        print(f"\nApplied parsing to {len(self.individuals)} individuals")
        print(f"Found {len(self.fixes_applied)} names requiring normalization\n")

        # Show examples of fixes
        print("Sample fixes (first 10):")
        for i, fix in enumerate(self.fixes_applied[:10]):
            print(f"\n{i+1}. {fix['person_id']}")
            print(f"   Original:   {fix['original']}")
            print(f"   Normalized: {fix['normalized']}")
            if fix['changes']:
                print(f"   Changes:    {', '.join(fix['changes'])}")

        if len(self.fixes_applied) > 10:
            print(f"\n... and {len(self.fixes_applied) - 10} more fixes")

    def find_duplicates(self, confidence_threshold: int = 70):
        """Find potential duplicate persons with tree-aware checking."""
        print("\n" + "=" * 80)
        print("STEP 4: FINDING DUPLICATE CANDIDATES")
        print("=" * 80)
        print(f"\nUsing confidence threshold: {confidence_threshold}%")

        # Create matcher
        matcher = PersonMatcher(self.individuals, self.families)
        scorer = MatchScorer(self.families)

        # Find all duplicates
        duplicates = []
        checked_pairs: Set[Tuple[str, str]] = set()

        print("\nScanning for duplicates...")
        for person_id, person in self.individuals.items():
            if not person.names:
                continue

            # Find potential matches
            matches = matcher.find_matches(person_id, limit=10)

            for match_id, score in matches:
                # Skip self-matches
                if match_id == person_id:
                    continue

                # Skip if we already checked this pair
                pair = tuple(sorted([person_id, match_id]))
                if pair in checked_pairs:
                    continue
                checked_pairs.add(pair)

                # Get detailed score
                detailed_score = scorer.score_match(person, self.individuals[match_id])

                if detailed_score.total_score >= confidence_threshold:
                    duplicates.append({
                        'person1_id': person_id,
                        'person2_id': match_id,
                        'score': detailed_score.total_score,
                        'confidence': detailed_score.confidence,
                        'person1': person,
                        'person2': self.individuals[match_id],
                        'details': detailed_score
                    })

        # Sort by score descending
        duplicates.sort(key=lambda x: x['score'], reverse=True)

        print(f"\nFound {len(duplicates)} potential duplicate pairs")

        return duplicates

    def analyze_duplicates_with_tree_context(self, duplicates: List[Dict]):
        """Analyze duplicates with family tree context for sanity checking."""
        print("\n" + "=" * 80)
        print("STEP 5: TREE-AWARE DUPLICATE ANALYSIS")
        print("=" * 80)

        print("\nAnalyzing family tree context for sanity checking...")

        for i, dup in enumerate(duplicates[:20]):  # Show first 20
            p1_id = dup['person1_id']
            p2_id = dup['person2_id']
            p1 = dup['person1']
            p2 = dup['person2']

            print(f"\n{'─' * 80}")
            print(f"DUPLICATE CANDIDATE #{i+1} - Confidence: {dup['confidence']} ({dup['score']:.1f}%)")
            print(f"{'─' * 80}")

            # Show basic info
            print(f"\nPerson 1: {p1_id}")
            for name in p1.names:
                print(f"  Name: {name}")
            print(f"  Sex: {p1.sex}")
            print(f"  Birth: {p1.get_birth_date() or 'Unknown'}")
            print(f"  Death: {p1.get_death_date() or 'Unknown'}")

            print(f"\nPerson 2: {p2_id}")
            for name in p2.names:
                print(f"  Name: {name}")
            print(f"  Sex: {p2.sex}")
            print(f"  Birth: {p2.get_birth_date() or 'Unknown'}")
            print(f"  Death: {p2.get_death_date() or 'Unknown'}")

            # Analyze family context
            print(f"\nFamily Tree Context:")

            # Check parents
            p1_parents = self._get_parents(p1)
            p2_parents = self._get_parents(p2)

            if p1_parents or p2_parents:
                print(f"  Person 1 parents: {len(p1_parents)} known")
                for parent_id in p1_parents:
                    parent = self.individuals.get(parent_id)
                    if parent and parent.names:
                        print(f"    - {parent.names[0]}")

                print(f"  Person 2 parents: {len(p2_parents)} known")
                for parent_id in p2_parents:
                    parent = self.individuals.get(parent_id)
                    if parent and parent.names:
                        print(f"    - {parent.names[0]}")

            # Check children
            p1_children = self._get_children(p1)
            p2_children = self._get_children(p2)

            if p1_children or p2_children:
                print(f"  Person 1 children: {len(p1_children)} known")
                for child_id in p1_children[:3]:  # Show first 3
                    child = self.individuals.get(child_id)
                    if child and child.names:
                        print(f"    - {child.names[0]}")
                if len(p1_children) > 3:
                    print(f"    ... and {len(p1_children) - 3} more")

                print(f"  Person 2 children: {len(p2_children)} known")
                for child_id in p2_children[:3]:  # Show first 3
                    child = self.individuals.get(child_id)
                    if child and child.names:
                        print(f"    - {child.names[0]}")
                if len(p2_children) > 3:
                    print(f"    ... and {len(p2_children) - 3} more")

            # Check spouses
            p1_spouses = self._get_spouses(p1)
            p2_spouses = self._get_spouses(p2)

            if p1_spouses or p2_spouses:
                print(f"  Person 1 spouses: {len(p1_spouses)} known")
                for spouse_id in p1_spouses:
                    spouse = self.individuals.get(spouse_id)
                    if spouse and spouse.names:
                        print(f"    - {spouse.names[0]}")

                print(f"  Person 2 spouses: {len(p2_spouses)} known")
                for spouse_id in p2_spouses:
                    spouse = self.individuals.get(spouse_id)
                    if spouse and spouse.names:
                        print(f"    - {spouse.names[0]}")

            # Sanity check: are they in the same family?
            if self._are_related(p1_id, p2_id):
                print("\n  ⚠️  WARNING: These individuals appear in the same family tree!")
                print("      This may indicate they are related, not duplicates.")

            # Show scoring details
            print(f"\nMatch Scoring:")
            print(f"  Name similarity: {dup['details'].name_score:.1f}%")
            print(f"  Date proximity: {dup['details'].date_score:.1f}%")
            print(f"  Place match: {dup['details'].place_score:.1f}%")

        if len(duplicates) > 20:
            print(f"\n... and {len(duplicates) - 20} more duplicate candidates")

    def _get_parents(self, person: Person) -> List[str]:
        """Get parent IDs for a person."""
        parents = []
        for fam_id in person.families_as_child:
            family = self.families.get(fam_id)
            if family:
                if family.husband_id:
                    parents.append(family.husband_id)
                if family.wife_id:
                    parents.append(family.wife_id)
        return parents

    def _get_children(self, person: Person) -> List[str]:
        """Get child IDs for a person."""
        children = []
        for fam_id in person.families_as_spouse:
            family = self.families.get(fam_id)
            if family:
                children.extend(family.children_ids)
        return children

    def _get_spouses(self, person: Person) -> List[str]:
        """Get spouse IDs for a person."""
        spouses = []
        for fam_id in person.families_as_spouse:
            family = self.families.get(fam_id)
            if family:
                if family.husband_id and family.husband_id != person.id:
                    spouses.append(family.husband_id)
                if family.wife_id and family.wife_id != person.id:
                    spouses.append(family.wife_id)
        return spouses

    def _are_related(self, person1_id: str, person2_id: str, max_depth: int = 3) -> bool:
        """Check if two people appear in the same family tree (simple check)."""
        # Get immediate family members for both
        p1_family = set()
        p1_family.update(self._get_parents(self.individuals[person1_id]))
        p1_family.update(self._get_children(self.individuals[person1_id]))
        p1_family.update(self._get_spouses(self.individuals[person1_id]))

        p2_family = set()
        p2_family.update(self._get_parents(self.individuals[person2_id]))
        p2_family.update(self._get_children(self.individuals[person2_id]))
        p2_family.update(self._get_spouses(self.individuals[person2_id]))

        # Check if person2 is in person1's immediate family or vice versa
        if person2_id in p1_family or person1_id in p2_family:
            return True

        # Check if they share any immediate family members
        if p1_family.intersection(p2_family):
            return True

        return False

    def run_full_pipeline(self):
        """Run the complete pipeline."""
        self.load_data()
        self.analyze_original_names()
        self.apply_name_parsing()
        duplicates = self.find_duplicates(confidence_threshold=70)
        self.analyze_duplicates_with_tree_context(duplicates)

        print("\n" + "=" * 80)
        print("PIPELINE COMPLETE")
        print("=" * 80)
        print(f"\nSummary:")
        print(f"  - Loaded {len(self.individuals)} individuals")
        print(f"  - Applied {len(self.fixes_applied)} name parsing fixes")
        print(f"  - Found {len(duplicates)} potential duplicate pairs")
        print(f"\nNext steps:")
        print(f"  - Review duplicate candidates above")
        print(f"  - Run consolidation on confirmed duplicates")
        print(f"  - Apply name normalization fixes to database")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Test genealogy processing pipeline')
    parser.add_argument('gedcom', nargs='?',
                       default='GedMerge/GEDCOM/Joel2020.ged',
                       help='Path to GEDCOM file')
    parser.add_argument('--threshold', type=int, default=70,
                       help='Confidence threshold for duplicates (default: 70)')

    args = parser.parse_args()

    # Make path relative to script location
    script_dir = Path(__file__).parent
    gedcom_path = script_dir / args.gedcom

    if not gedcom_path.exists():
        print(f"Error: GEDCOM file not found: {gedcom_path}")
        print(f"\nAvailable GEDCOM files:")
        for ged_file in (script_dir / 'GedMerge' / 'GEDCOM').glob('*.ged'):
            print(f"  - {ged_file.relative_to(script_dir)}")
        return 1

    print(f"Testing with GEDCOM file: {gedcom_path}")
    print()

    tester = PipelineTester(str(gedcom_path))
    tester.run_full_pipeline()

    return 0


if __name__ == '__main__':
    sys.exit(main())
