#!/usr/bin/env python3
"""
Find and Merge Duplicate Person Records

This tool uses phonetic matching, fuzzy string matching, and multilingual
name comparison to detect and merge duplicate person records in a
RootsMagic database.

Features:
- Phonetic matching using Metaphone
- Fuzzy string matching with rapidfuzz
- Multilingual name handling (English, French, German, Italian, Spanish, Latin)
- Honorific suffix normalization
- Date and place proximity matching
- Confidence-based merge decisions
- Interactive or automatic merging

Usage:
    # Find duplicates (dry-run, no changes)
    python find_and_merge_duplicates.py /path/to/database.rmtree --dry-run

    # Find and auto-merge high-confidence duplicates (>= 90%)
    python find_and_merge_duplicates.py /path/to/database.rmtree --auto-merge

    # Interactive mode (review each match)
    python find_and_merge_duplicates.py /path/to/database.rmtree --interactive

    # Find duplicates for specific persons
    python find_and_merge_duplicates.py /path/to/database.rmtree --person-ids 123,456,789

    # Set custom confidence threshold
    python find_and_merge_duplicates.py /path/to/database.rmtree --min-confidence 70
"""

import sys
import argparse
from pathlib import Path
from typing import List, Optional
import sqlite3

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent / 'GedMerge'))

from gedmerge.rootsmagic.adapter import RootsMagicDatabase
from gedmerge.matching import PersonMatcher, MatchCandidate
from gedmerge.merge import PersonMerger, MergeStrategy, MergeResult


class DuplicateDetector:
    """Main class for finding and merging duplicates."""

    def __init__(
        self,
        db_path: str,
        min_confidence: float = 60.0,
        dry_run: bool = True
    ):
        """
        Initialize the detector.

        Args:
            db_path: Path to RootsMagic database
            min_confidence: Minimum confidence score (0-100)
            dry_run: If True, don't make changes
        """
        self.db_path = db_path
        self.min_confidence = min_confidence
        self.dry_run = dry_run
        self.db = RootsMagicDatabase(db_path)
        self.matcher = PersonMatcher(self.db, min_confidence=min_confidence)
        self.merger = None  # Created when needed

    def find_duplicates(
        self,
        person_ids: Optional[List[int]] = None,
        limit: Optional[int] = None
    ) -> List[MatchCandidate]:
        """
        Find potential duplicate persons.

        Args:
            person_ids: Specific person IDs to check, or None for all
            limit: Maximum number of matches to return

        Returns:
            List of match candidates sorted by confidence
        """
        print(f"\n{'='*80}")
        print("FINDING DUPLICATE PERSONS")
        print(f"{'='*80}")
        print(f"Database: {self.db_path}")
        print(f"Minimum confidence: {self.min_confidence}%")

        if person_ids:
            print(f"Checking {len(person_ids)} specific persons")
        else:
            print("Checking all persons in database")

        print(f"\nSearching for duplicates...\n")

        matches = self.matcher.find_duplicates(
            person_ids=person_ids,
            limit=limit
        )

        return matches

    def display_matches(self, matches: List[MatchCandidate]) -> None:
        """Display match candidates in a readable format."""
        if not matches:
            print("No potential duplicates found.")
            return

        print(f"\nFound {len(matches)} potential duplicate pairs:\n")
        print(f"{'='*80}")

        for i, match in enumerate(matches, 1):
            self._display_match(i, match)
            print(f"{'-'*80}")

    def _display_match(self, index: int, match: MatchCandidate) -> None:
        """Display a single match candidate."""
        p1 = match.person1
        p2 = match.person2

        # Confidence level
        if match.is_high_confidence:
            level = "HIGH"
            symbol = "✓✓✓"
        elif match.is_medium_confidence:
            level = "MEDIUM"
            symbol = "✓✓"
        else:
            level = "LOW"
            symbol = "✓"

        print(f"\n{symbol} Match #{index} - Confidence: {match.confidence:.1f}% ({level})")
        print()

        # Person 1
        print(f"  Person 1 (ID: {p1.person_id}):")
        if p1.names:
            for name in p1.names[:2]:  # Show first 2 names
                lang = f"[{name.language}]" if name.language else ""
                print(f"    Name: {name.given} /{name.surname}/ {lang}")
        if p1.events:
            for event in p1.events[:2]:  # Show first 2 events
                event_types = {1: 'Birth', 2: 'Death', 3: 'Burial', 4: 'Marriage', 5: 'Divorce'}
                event_name = event_types.get(event.event_type, f'Event{event.event_type}')
                # Events have place_id, not place string
                print(f"    {event_name}: {event.date or '?'}")
        print(f"    Sex: {p1.sex or 'Unknown'}")
        print()

        # Person 2
        print(f"  Person 2 (ID: {p2.person_id}):")
        if p2.names:
            for name in p2.names[:2]:
                lang = f"[{name.language}]" if name.language else ""
                print(f"    Name: {name.given} /{name.surname}/ {lang}")
        if p2.events:
            for event in p2.events[:2]:
                event_types = {1: 'Birth', 2: 'Death', 3: 'Burial', 4: 'Marriage', 5: 'Divorce'}
                event_name = event_types.get(event.event_type, f'Event{event.event_type}')
                # Events have place_id, not place string
                print(f"    {event_name}: {event.date or '?'}")
        print(f"    Sex: {p2.sex or 'Unknown'}")
        print()

        # Score breakdown
        result = match.match_result
        print(f"  Score Breakdown:")
        print(f"    Name similarity:      {result.name_score:5.1f}%")
        print(f"    Phonetic matching:    {result.phonetic_score:5.1f}%")
        print(f"    Date proximity:       {result.date_score:5.1f}%")
        print(f"    Place matching:       {result.place_score:5.1f}%")
        print(f"    Relationship overlap: {result.relationship_score:5.1f}%")
        print(f"    Sex match:            {result.sex_score:5.1f}%")

        # Flags
        flags = []
        if result.is_exact_name_match:
            flags.append("Exact name match")
        if result.is_exact_date_match:
            flags.append("Exact date match")
        if result.has_conflicting_info:
            flags.append("⚠ Conflicting information")

        if flags:
            print(f"\n  Flags: {', '.join(flags)}")

    def merge_matches(
        self,
        matches: List[MatchCandidate],
        strategy: MergeStrategy = MergeStrategy.INTERACTIVE,
        auto_threshold: float = 90.0
    ) -> List[MergeResult]:
        """
        Merge match candidates.

        Args:
            matches: List of match candidates to merge
            strategy: Merge strategy to use
            auto_threshold: Confidence threshold for automatic merging

        Returns:
            List of merge results
        """
        if self.dry_run:
            print("\n" + "="*80)
            print("DRY-RUN MODE - No changes will be made")
            print("="*80)
            print(f"\nWould merge {len(matches)} candidate pairs")
            return []

        print("\n" + "="*80)
        print("MERGING DUPLICATES")
        print("="*80)
        print(f"Strategy: {strategy.value}")
        print(f"Auto-merge threshold: {auto_threshold}%")
        print()

        # Create merger
        self.merger = PersonMerger(self.db, strategy=strategy)

        # Merge candidates
        results = self.merger.merge_candidates(
            matches,
            auto_merge_threshold=auto_threshold
        )

        # Display results
        self._display_merge_results(results)

        return results

    def _display_merge_results(self, results: List[MergeResult]) -> None:
        """Display merge results."""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]

        print(f"\n{'='*80}")
        print("MERGE RESULTS")
        print(f"{'='*80}")
        print(f"Successful: {len(successful)}")
        print(f"Failed:     {len(failed)}")
        print()

        if successful:
            print("\nSuccessful Merges:")
            for i, result in enumerate(successful, 1):
                print(f"\n  {i}. {result}")

        if failed:
            print("\nFailed Merges:")
            for i, result in enumerate(failed, 1):
                print(f"\n  {i}. {result}")

    def close(self) -> None:
        """Close database connection."""
        if self.db:
            self.db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Find and merge duplicate person records",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        'database',
        help='Path to RootsMagic database (.rmtree file)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Find duplicates but do not merge (default)'
    )

    parser.add_argument(
        '--auto-merge',
        action='store_true',
        help='Automatically merge high-confidence duplicates'
    )

    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Review each match before merging'
    )

    parser.add_argument(
        '--min-confidence',
        type=float,
        default=60.0,
        help='Minimum confidence score to consider (0-100, default: 60)'
    )

    parser.add_argument(
        '--auto-threshold',
        type=float,
        default=90.0,
        help='Confidence threshold for automatic merging (default: 90)'
    )

    parser.add_argument(
        '--person-ids',
        type=str,
        help='Comma-separated list of person IDs to check (e.g., "123,456,789")'
    )

    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of matches to return'
    )

    args = parser.parse_args()

    # Validate database path
    db_path = Path(args.database)
    if not db_path.exists():
        print(f"Error: Database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    # Parse person IDs
    person_ids = None
    if args.person_ids:
        try:
            person_ids = [int(pid.strip()) for pid in args.person_ids.split(',')]
        except ValueError:
            print("Error: Invalid person IDs format", file=sys.stderr)
            sys.exit(1)

    # Determine mode
    dry_run = not (args.auto_merge or args.interactive)
    if args.auto_merge and args.interactive:
        print("Error: Cannot use both --auto-merge and --interactive", file=sys.stderr)
        sys.exit(1)

    strategy = MergeStrategy.AUTOMATIC if args.auto_merge else MergeStrategy.INTERACTIVE

    # Run detector
    detector = DuplicateDetector(
        db_path=str(db_path),
        min_confidence=args.min_confidence,
        dry_run=dry_run
    )

    try:
        # Find duplicates
        matches = detector.find_duplicates(
            person_ids=person_ids,
            limit=args.limit
        )

        # Display matches
        detector.display_matches(matches)

        # Merge if requested
        if not dry_run and matches:
            print("\n" + "="*80)
            response = input("Proceed with merging? (yes/no): ").strip().lower()
            if response in ('yes', 'y'):
                detector.merge_matches(
                    matches,
                    strategy=strategy,
                    auto_threshold=args.auto_threshold
                )
            else:
                print("Merge cancelled.")
        elif dry_run and matches:
            print("\n" + "="*80)
            print("Run with --auto-merge or --interactive to merge duplicates")
            print("="*80)

    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        detector.close()


if __name__ == '__main__':
    main()
