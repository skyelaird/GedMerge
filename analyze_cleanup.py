#!/usr/bin/env python3
"""Analyze and cleanup RootsMagic database - notes, postal codes, and unused places."""

from gedmerge.rootsmagic import RootsMagicDatabase
from pathlib import Path
import re
import zipfile


def extract_database():
    """Extract the RootsMagic database if needed."""
    zip_path = Path('/home/user/Python-Scripts/GedMerge/Rootsmagic/Joel2020.zip')
    extract_dir = zip_path.parent
    db_path = extract_dir / 'Joel2020.rmtree'

    if not db_path.exists():
        print(f"Extracting {zip_path}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print(f"Extracted to {db_path}")

    return db_path


def has_postal_code(place_name):
    """Check if a place name contains what looks like a postal code."""
    if not place_name:
        return False

    # Common postal code patterns
    patterns = [
        r'\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b',  # Canadian postal code (e.g., K1A 0B1)
        r'\b\d{5}(?:-\d{4})?\b',  # US ZIP code (e.g., 12345 or 12345-6789)
        r'\b[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}\b',  # UK postal code
    ]

    for pattern in patterns:
        if re.search(pattern, place_name):
            return True
    return False


def extract_postal_code(place_name):
    """Extract postal code from place name."""
    if not place_name:
        return None

    # Common postal code patterns
    patterns = [
        r'\b([A-Z]\d[A-Z]\s?\d[A-Z]\d)\b',  # Canadian
        r'\b(\d{5}(?:-\d{4})?)\b',  # US ZIP
        r'\b([A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2})\b',  # UK
    ]

    for pattern in patterns:
        match = re.search(pattern, place_name)
        if match:
            return match.group(1)
    return None


def remove_postal_code(place_name):
    """Remove postal code from place name."""
    if not place_name:
        return place_name

    # Common postal code patterns
    patterns = [
        r',?\s*\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b',  # Canadian
        r',?\s*\b\d{5}(?:-\d{4})?\b',  # US ZIP
        r',?\s*\b[A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2}\b',  # UK
    ]

    cleaned = place_name
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned)

    # Clean up extra commas and whitespace
    cleaned = re.sub(r',\s*,', ',', cleaned)
    cleaned = re.sub(r',\s*$', '', cleaned)
    cleaned = re.sub(r'^\s*,', '', cleaned)
    cleaned = cleaned.strip()

    return cleaned


def analyze_database(db_path):
    """Analyze the database for notes, postal codes, and unused places."""
    print(f"\nOpening database: {db_path}")

    db = RootsMagicDatabase(db_path)
    try:
        print("\n=== DATABASE STATISTICS ===")
        stats = db.get_stats()
        for key, value in stats.items():
            print(f"  {key:15s}: {value:,}")

        # Analyze notes
        print("\n=== ANALYZING NOTES ===")
        cursor = db.conn.cursor()

        # Check person notes
        cursor.execute("SELECT COUNT(*) FROM PersonTable WHERE Note IS NOT NULL AND Note != ''")
        person_notes = cursor.fetchone()[0]
        print(f"  Persons with notes: {person_notes}")

        # Check name notes
        cursor.execute("SELECT COUNT(*) FROM NameTable WHERE Note IS NOT NULL AND Note != ''")
        name_notes = cursor.fetchone()[0]
        print(f"  Names with notes: {name_notes}")

        # Check event notes
        cursor.execute("SELECT COUNT(*) FROM EventTable WHERE Note IS NOT NULL AND Note != ''")
        event_notes = cursor.fetchone()[0]
        print(f"  Events with notes: {event_notes}")

        # Check family notes
        cursor.execute("SELECT COUNT(*) FROM FamilyTable WHERE Note IS NOT NULL AND Note != ''")
        family_notes = cursor.fetchone()[0]
        print(f"  Families with notes: {family_notes}")

        # Check place notes
        cursor.execute("SELECT COUNT(*) FROM PlaceTable WHERE Note IS NOT NULL AND Note != ''")
        place_notes = cursor.fetchone()[0]
        print(f"  Places with notes: {place_notes}")

        # Analyze places with postal codes
        print("\n=== ANALYZING POSTAL CODES IN PLACES ===")
        cursor.execute("SELECT PlaceID, Name FROM PlaceTable WHERE Name IS NOT NULL")
        places_with_postal = []

        for row in cursor.fetchall():
            place_id, name = row
            if has_postal_code(name):
                postal = extract_postal_code(name)
                cleaned = remove_postal_code(name)
                places_with_postal.append((place_id, name, postal, cleaned))

        print(f"  Places with postal codes: {len(places_with_postal)}")
        if places_with_postal:
            print("\n  Examples:")
            for place_id, original, postal, cleaned in places_with_postal[:10]:
                print(f"    PlaceID {place_id}:")
                print(f"      Original: {original}")
                print(f"      Postal:   {postal}")
                print(f"      Cleaned:  {cleaned}")

        # Analyze unused places
        print("\n=== ANALYZING UNUSED PLACES ===")
        cursor.execute("""
            SELECT PlaceID FROM PlaceTable
            WHERE PlaceID NOT IN (SELECT DISTINCT PlaceID FROM EventTable WHERE PlaceID IS NOT NULL)
        """)
        unused_places = cursor.fetchall()
        print(f"  Unused places: {len(unused_places)}")

        if unused_places:
            print(f"\n  First 10 unused places:")
            for place_id_tuple in unused_places[:10]:
                place_id = place_id_tuple[0]
                place = db.get_place(place_id)
                if place:
                    print(f"    PlaceID {place_id}: {place.name}")

        result = {
            'person_notes': person_notes,
            'name_notes': name_notes,
            'event_notes': event_notes,
            'family_notes': family_notes,
            'place_notes': place_notes,
            'places_with_postal': places_with_postal,
            'unused_places': [p[0] for p in unused_places]
        }

        return result
    finally:
        db.close()


def cleanup_database(db_path, analysis_results):
    """Cleanup the database based on analysis results."""
    print("\n=== STARTING CLEANUP ===")

    # Create a fresh connection for cleanup
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Register RMNOCASE collation
    def rmnocase_collation(s1: str, s2: str) -> int:
        """Case-insensitive collation for RootsMagic."""
        s1_upper = s1.upper() if s1 else ''
        s2_upper = s2.upper() if s2 else ''
        return (s1_upper > s2_upper) - (s1_upper < s2_upper)

    conn.create_collation("RMNOCASE", rmnocase_collation)

    cursor = conn.cursor()

    # Fix database integrity issues by reindexing
    print("\nRebuilding database indices...")
    cursor.execute("REINDEX")
    conn.commit()
    print("  ✓ Indices rebuilt")

    try:
        # 1. Clean up postal codes from places
        print(f"\nCleaning postal codes from {len(analysis_results['places_with_postal'])} places...")
        updated_count = 0
        for place_id, original, postal, cleaned in analysis_results['places_with_postal']:
            if cleaned != original:
                try:
                    cursor.execute("""
                        UPDATE PlaceTable SET Name = ? WHERE PlaceID = ?
                    """, (cleaned, place_id))
                    updated_count += 1
                    if updated_count <= 10:  # Show first 10 updates
                        print(f"  Updated PlaceID {place_id}: {original} -> {cleaned}")
                except Exception as e:
                    print(f"  ✗ Error updating PlaceID {place_id}: {e}")
                    print(f"    Original: {original}")
                    print(f"    Cleaned: {cleaned}")
                    raise

        conn.commit()
        print(f"  ✓ Updated {len(analysis_results['places_with_postal'])} places")

        # 2. Delete unused places
        print(f"\nDeleting {len(analysis_results['unused_places'])} unused places...")
        for place_id in analysis_results['unused_places']:
            cursor.execute("DELETE FROM PlaceTable WHERE PlaceID = ?", (place_id,))

        conn.commit()
        print(f"  ✓ Deleted {len(analysis_results['unused_places'])} places")

        # 3. Notes are already in place - GEDCOM export will handle them
        # Notes exist on Person, Name, Event, Family, and Place records
        # The GEDCOM exporter should preserve them when exporting
        print("\nNotes are already preserved in the database:")
        print(f"  - {analysis_results['person_notes']} person notes")
        print(f"  - {analysis_results['name_notes']} name notes")
        print(f"  - {analysis_results['event_notes']} event notes")
        print(f"  - {analysis_results['family_notes']} family notes")
        print(f"  - {analysis_results['place_notes']} place notes")
        print("  These will be exported to GEDCOM when converting.")

        print("\n✓ Cleanup completed successfully!")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ Error during cleanup: {e}")
        raise
    finally:
        conn.close()


def main():
    """Main function."""
    import sys

    db_path = extract_database()

    # Analyze
    analysis_results = analyze_database(db_path)

    # Ask for confirmation
    print("\n" + "="*60)
    print("CLEANUP SUMMARY")
    print("="*60)
    print(f"  1. Will clean postal codes from {len(analysis_results['places_with_postal'])} places")
    print(f"  2. Will delete {len(analysis_results['unused_places'])} unused places")
    print(f"  3. Notes are already preserved ({analysis_results['event_notes']} event notes)")
    print("="*60)

    # Auto-proceed if --auto flag is passed
    if '--auto' in sys.argv:
        cleanup_database(db_path, analysis_results)
    else:
        response = input("\nProceed with cleanup? (y/n): ")
        if response.lower() == 'y':
            cleanup_database(db_path, analysis_results)
        else:
            print("Cleanup cancelled.")


if __name__ == '__main__':
    main()
