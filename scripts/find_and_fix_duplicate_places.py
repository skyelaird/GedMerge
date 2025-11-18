#!/usr/bin/env python3
"""Find and fix duplicate places in RootsMagic database.

This script:
1. Finds duplicate places using the PlaceCleaner utility
2. Reports duplicates with merge suggestions
3. Optionally merges duplicates (updates all events to use canonical place ID)
4. Cleans up place names (removes postal codes, fixes formatting, etc.)
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import sqlite3
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gedmerge.rootsmagic import RootsMagicDatabase
from gedmerge.utils.place_cleaner import PlaceCleaner, CleanedPlace


class DuplicatePlaceFixer:
    """Find and fix duplicate places in RootsMagic database."""

    def __init__(self, db_path: str):
        """Initialize with database path."""
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found: {self.db_path}")

    def analyze_duplicates(self, normalize_uk_counties: bool = True) -> Dict[str, List[Tuple[int, str]]]:
        """Analyze database for duplicate places.

        Args:
            normalize_uk_counties: Whether to normalize UK county variations

        Returns:
            Dictionary mapping normalized names to list of (place_id, original_name) tuples
        """
        print(f"\nAnalyzing database: {self.db_path}")
        print("="*80)

        with RootsMagicDatabase(self.db_path) as db:
            cursor = db.conn.cursor()

            # Get all places
            cursor.execute("SELECT PlaceID, Name FROM PlaceTable WHERE Name IS NOT NULL ORDER BY PlaceID")
            places = cursor.fetchall()

            print(f"Total places in database: {len(places)}")

            # Find duplicates using PlaceCleaner
            print("\nFinding duplicates...")
            duplicates = {}
            place_to_cleaned = {}  # Map place_id to CleanedPlace

            for place_id, place_name in places:
                cleaned = PlaceCleaner.clean_place_name(
                    place_name,
                    normalize_uk_counties=normalize_uk_counties,
                    remove_postal_codes=True,
                    expand_abbreviations=True
                )

                place_to_cleaned[place_id] = cleaned
                normalized_key = cleaned.cleaned.lower().strip()

                if normalized_key not in duplicates:
                    duplicates[normalized_key] = []

                duplicates[normalized_key].append((place_id, place_name, cleaned))

            # Filter to only actual duplicates (2+ places)
            actual_duplicates = {
                key: places_list
                for key, places_list in duplicates.items()
                if len(places_list) > 1
            }

            print(f"Found {len(actual_duplicates)} groups of duplicate places")
            print(f"Total duplicate place records: {sum(len(p) for p in actual_duplicates.values())}")

            return actual_duplicates, place_to_cleaned

    def report_duplicates(self, duplicates: Dict[str, List[Tuple[int, str, CleanedPlace]]],
                         place_to_cleaned: Dict[int, CleanedPlace],
                         max_groups: int = 50):
        """Report duplicate places with merge suggestions.

        Args:
            duplicates: Dictionary of duplicate groups
            place_to_cleaned: Map of place_id to CleanedPlace
            max_groups: Maximum number of duplicate groups to display
        """
        print("\n" + "="*80)
        print("DUPLICATE PLACES REPORT")
        print("="*80)

        sorted_groups = sorted(duplicates.items(), key=lambda x: len(x[1]), reverse=True)

        for i, (normalized_name, places_list) in enumerate(sorted_groups[:max_groups], 1):
            print(f"\n{i}. Normalized: '{normalized_name}'")
            print(f"   Found {len(places_list)} duplicates:")

            # Determine canonical place (lowest ID, or one with most events)
            with RootsMagicDatabase(self.db_path) as db:
                cursor = db.conn.cursor()
                place_event_counts = {}

                for place_id, original_name, cleaned in places_list:
                    cursor.execute(
                        "SELECT COUNT(*) FROM EventTable WHERE PlaceID = ?",
                        (place_id,)
                    )
                    event_count = cursor.fetchone()[0]
                    place_event_counts[place_id] = event_count

            # Sort by event count (descending), then by place_id (ascending)
            sorted_places = sorted(
                places_list,
                key=lambda x: (-place_event_counts[x[0]], x[0])
            )

            canonical_id = sorted_places[0][0]

            for j, (place_id, original_name, cleaned) in enumerate(sorted_places, 1):
                is_canonical = place_id == canonical_id
                marker = " [CANONICAL]" if is_canonical else ""
                event_count = place_event_counts[place_id]

                print(f"   {j}. PlaceID {place_id}{marker} ({event_count} events)")
                print(f"      Original: '{original_name}'")
                print(f"      Cleaned:  '{cleaned.cleaned}'")

                if cleaned.changes_made and cleaned.changes_made != ['No changes needed']:
                    print(f"      Changes:  {', '.join(cleaned.changes_made)}")

                if cleaned.warnings:
                    print(f"      Warnings: {', '.join(cleaned.warnings)}")

            # Show merge suggestion
            other_ids = [p[0] for p in sorted_places if p[0] != canonical_id]
            if other_ids:
                print(f"\n   SUGGESTION: Merge {other_ids} -> {canonical_id}")

        if len(sorted_groups) > max_groups:
            print(f"\n... and {len(sorted_groups) - max_groups} more duplicate groups")

    def clean_all_places(self, dry_run: bool = True) -> Dict[int, CleanedPlace]:
        """Clean all place names in the database.

        Args:
            dry_run: If True, don't make changes, just report what would be done

        Returns:
            Dictionary mapping place_id to CleanedPlace
        """
        print("\n" + "="*80)
        print("CLEANING ALL PLACES")
        print("="*80)

        place_updates = {}
        changes_count = 0

        with RootsMagicDatabase(self.db_path) as db:
            cursor = db.conn.cursor()

            # Get all places
            cursor.execute("SELECT PlaceID, Name FROM PlaceTable WHERE Name IS NOT NULL")
            places = cursor.fetchall()

            print(f"Processing {len(places)} places...")

            for place_id, place_name in places:
                cleaned = PlaceCleaner.clean_place_name(
                    place_name,
                    normalize_uk_counties=True,
                    remove_postal_codes=True,
                    expand_abbreviations=True
                )

                if cleaned.original != cleaned.cleaned:
                    place_updates[place_id] = cleaned
                    changes_count += 1

                    if changes_count <= 20:  # Show first 20 changes
                        print(f"\nPlaceID {place_id}:")
                        print(f"  Original: '{cleaned.original}'")
                        print(f"  Cleaned:  '{cleaned.cleaned}'")
                        print(f"  Changes:  {', '.join(cleaned.changes_made)}")

            print(f"\nTotal places to update: {changes_count} out of {len(places)}")

            if not dry_run and changes_count > 0:
                print("\nApplying changes to database...")
                for place_id, cleaned in place_updates.items():
                    cursor.execute(
                        "UPDATE PlaceTable SET Name = ? WHERE PlaceID = ?",
                        (cleaned.cleaned, place_id)
                    )

                db.conn.commit()
                print(f"✓ Updated {changes_count} places")
            elif dry_run:
                print("\n[DRY RUN] No changes made to database")

        return place_updates

    def merge_duplicate_places(self, duplicates: Dict[str, List[Tuple[int, str, CleanedPlace]]],
                               dry_run: bool = True) -> int:
        """Merge duplicate places by updating event references.

        Args:
            duplicates: Dictionary of duplicate groups
            dry_run: If True, don't make changes, just report what would be done

        Returns:
            Number of places merged
        """
        print("\n" + "="*80)
        print("MERGING DUPLICATE PLACES")
        print("="*80)

        merge_count = 0

        with RootsMagicDatabase(self.db_path) as db:
            cursor = db.conn.cursor()

            for normalized_name, places_list in duplicates.items():
                # Get event counts for each place
                place_event_counts = {}
                for place_id, original_name, cleaned in places_list:
                    cursor.execute(
                        "SELECT COUNT(*) FROM EventTable WHERE PlaceID = ?",
                        (place_id,)
                    )
                    event_count = cursor.fetchone()[0]
                    place_event_counts[place_id] = event_count

                # Determine canonical place (most events, then lowest ID)
                sorted_places = sorted(
                    places_list,
                    key=lambda x: (-place_event_counts[x[0]], x[0])
                )
                canonical_id = sorted_places[0][0]
                canonical_name = sorted_places[0][1]

                # Merge others into canonical
                for place_id, original_name, cleaned in sorted_places[1:]:
                    event_count = place_event_counts[place_id]

                    print(f"\nMerging PlaceID {place_id} -> {canonical_id}")
                    print(f"  '{original_name}' ({event_count} events)")
                    print(f"  -> '{canonical_name}'")

                    if not dry_run:
                        # Update all events using this place to use canonical place
                        cursor.execute(
                            "UPDATE EventTable SET PlaceID = ? WHERE PlaceID = ?",
                            (canonical_id, place_id)
                        )

                        # Delete the duplicate place
                        cursor.execute(
                            "DELETE FROM PlaceTable WHERE PlaceID = ?",
                            (place_id,)
                        )

                        merge_count += 1

            if not dry_run:
                db.conn.commit()
                print(f"\n✓ Merged {merge_count} duplicate places")
            else:
                print(f"\n[DRY RUN] Would merge {len([p for places in duplicates.values() for p in places[1:]])} places")

        return merge_count


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Find and fix duplicate places in RootsMagic database"
    )
    parser.add_argument(
        'db_path',
        help='Path to RootsMagic .rmtree database file'
    )
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean all place names (fix formatting, remove postal codes, etc.)'
    )
    parser.add_argument(
        '--merge',
        action='store_true',
        help='Merge duplicate places (updates events to use canonical place ID)'
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Actually apply changes (default is dry-run mode)'
    )
    parser.add_argument(
        '--max-groups',
        type=int,
        default=50,
        help='Maximum number of duplicate groups to display (default: 50)'
    )

    args = parser.parse_args()

    dry_run = not args.apply

    if dry_run:
        print("\n" + "="*80)
        print("DRY RUN MODE - No changes will be made")
        print("Use --apply to actually make changes")
        print("="*80)

    fixer = DuplicatePlaceFixer(args.db_path)

    # Always analyze duplicates
    duplicates, place_to_cleaned = fixer.analyze_duplicates(normalize_uk_counties=True)
    fixer.report_duplicates(duplicates, place_to_cleaned, max_groups=args.max_groups)

    # Clean places if requested
    if args.clean:
        fixer.clean_all_places(dry_run=dry_run)

    # Merge duplicates if requested
    if args.merge:
        fixer.merge_duplicate_places(duplicates, dry_run=dry_run)

    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Duplicate groups found: {len(duplicates)}")
    print(f"Total duplicate places: {sum(len(p) for p in duplicates.values())}")

    if args.clean or args.merge:
        if dry_run:
            print("\nDRY RUN - no changes were made")
            print("Use --apply to actually make changes")
        else:
            print("\nChanges have been applied to the database")


if __name__ == '__main__':
    main()
