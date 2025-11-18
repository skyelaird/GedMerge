#!/usr/bin/env python3
"""Test script for RootsMagic database adapter."""

from gedmerge.rootsmagic import RootsMagicDatabase
from pathlib import Path


def main():
    # Extract the database first
    import zipfile
    zip_path = Path('/home/user/Python-Scripts/GedMerge/Rootsmagic/Joel2020.zip')
    extract_dir = zip_path.parent
    db_path = extract_dir / 'Joel2020.rmtree'

    # Extract if not already extracted
    if not db_path.exists():
        print(f"Extracting {zip_path}...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print(f"Extracted to {db_path}")

    # Open the database
    print(f"\nOpening database: {db_path}")
    with RootsMagicDatabase(db_path) as db:
        # Get statistics
        print("\n=== DATABASE STATISTICS ===")
        stats = db.get_stats()
        for key, value in stats.items():
            print(f"  {key:15s}: {value:,}")

        # Get a few sample persons
        print("\n=== SAMPLE PERSONS ===")
        persons = db.get_all_persons(limit=10)
        for person in persons:
            print(f"\nPersonID {person.person_id}:")
            print(f"  Name: {person}")
            print(f"  Sex: {person.get_sex_string()}")
            print(f"  Living: {person.living}")
            print(f"  Bookmarked: {person.bookmark}")
            if person.color > 0:
                print(f"  Color: {person.color}")

            # Show all names
            if len(person.names) > 1:
                print(f"  Names ({len(person.names)}):")
                for name in person.names:
                    print(f"    - {name.full_name()}" +
                          (" (primary)" if name.is_primary else ""))

            # Show events
            if person.events:
                print(f"  Events ({len(person.events)}):")
                for event in person.events[:3]:  # First 3 events
                    event_types = {1: 'Birth', 2: 'Death', 3: 'Burial'}
                    event_name = event_types.get(event.event_type, f'Type {event.event_type}')
                    print(f"    - {event_name}: {event.date or 'No date'}")

        # Search by name example
        print("\n=== SEARCH BY NAME: 'Morin' ===")
        morins = db.search_persons_by_name(surname='Morin')
        print(f"Found {len(morins)} persons with surname 'Morin'")
        for person in morins[:5]:  # Show first 5
            print(f"  - {person}")

        # Check for potential duplicates (same name)
        print("\n=== CHECKING FOR POTENTIAL NAME DUPLICATES ===")
        name_counts = {}
        all_persons = db.get_all_persons()

        for person in all_persons:
            name = person.get_primary_name()
            if name:
                key = (name.surname, name.given)
                if key not in name_counts:
                    name_counts[key] = []
                name_counts[key].append(person)

        # Find duplicates
        duplicates = {k: v for k, v in name_counts.items() if len(v) > 1}
        print(f"Found {len(duplicates)} name combinations with multiple persons")

        # Show a few examples
        for i, ((surname, given), persons) in enumerate(list(duplicates.items())[:5]):
            print(f"\n{surname}, {given} ({len(persons)} persons):")
            for person in persons:
                birth_year = person.get_birth_year()
                death_year = person.get_death_year()
                years = f"{birth_year or '?'}-{death_year or '?'}"
                print(f"  PersonID {person.person_id}: {years}")

    print("\n✓ Database adapter test completed successfully!")


if __name__ == '__main__':
    main()
