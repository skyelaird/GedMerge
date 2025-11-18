#!/usr/bin/env python3
"""Demonstration of multilingual place names functionality.

This script shows how to use the multilingual place names feature
in the GedMerge library for genealogical data.
"""

from gedmerge.core.place import Place
from gedmerge.core.event import Event


def main():
    """Run multilingual places demonstration."""
    print("=" * 70)
    print("Multilingual Place Names Demonstration")
    print("=" * 70)
    print()

    # Example 1: Creating a simple place
    print("Example 1: Simple place (London)")
    print("-" * 70)
    london = Place.from_string("London", language="en")
    print(f"Place name: {london}")
    print(f"Primary language: {london.primary_language}")
    print()

    # Example 2: Place with multiple language variants
    print("Example 2: Place with multiple languages (Munich)")
    print("-" * 70)
    munich = Place(names={
        'en': 'Munich',
        'de': 'München',
        'fr': 'Munich',
        'it': 'Monaco di Baviera'
    }, primary_language='de')

    print(f"English name: {munich.get_name('en')}")
    print(f"German name: {munich.get_name('de')}")
    print(f"French name: {munich.get_name('fr')}")
    print(f"Italian name: {munich.get_name('it')}")
    print(f"Default (primary): {munich.get_name()}")
    print()

    # Example 3: Place with coordinates
    print("Example 3: Place with coordinates (Warsaw)")
    print("-" * 70)
    warsaw = Place(
        names={
            'en': 'Warsaw',
            'pl': 'Warszawa',
            'de': 'Warschau',
            'ru': 'Варшава'
        },
        primary_language='pl',
        latitude=52.2297,
        longitude=21.0122
    )

    print(f"Polish name: {warsaw.get_name('pl')}")
    print(f"English name: {warsaw.get_name('en')}")
    print(f"German name: {warsaw.get_name('de')}")
    print(f"Russian name: {warsaw.get_name('ru')}")
    print(f"Coordinates: ({warsaw.latitude}, {warsaw.longitude})")
    print(f"Has coordinates: {warsaw.has_coordinates()}")
    print()

    # Example 4: Using places in events
    print("Example 4: Place in a birth event")
    print("-" * 70)
    birth_place = Place(
        names={
            'en': 'Prague',
            'cs': 'Praha',
            'de': 'Prag'
        },
        primary_language='cs',
        latitude=50.0755,
        longitude=14.4378
    )

    birth_event = Event(
        type='BIRT',
        date='15 MAR 1885',
        place=birth_place,
        notes='Birth registered at city hall'
    )

    print(f"Event: {birth_event}")
    print(f"Place in English: {birth_event.get_place_name('en')}")
    print(f"Place in Czech: {birth_event.get_place_name('cs')}")
    print(f"Place in German: {birth_event.get_place_name('de')}")
    print()

    # Example 5: Historical place names
    print("Example 5: Historical place name changes (Istanbul)")
    print("-" * 70)
    istanbul = Place(
        names={
            'en': 'Istanbul',
            'tr': 'İstanbul',
            'el': 'Κωνσταντινούπολη',  # Greek: Constantinople
            'la': 'Constantinopolis'   # Latin: Constantinople
        },
        primary_language='tr',
        latitude=41.0082,
        longitude=28.9784,
        notes='Formerly known as Constantinople and Byzantium'
    )

    print(f"Modern Turkish: {istanbul.get_name('tr')}")
    print(f"English: {istanbul.get_name('en')}")
    print(f"Greek (historical): {istanbul.get_name('el')}")
    print(f"Latin (historical): {istanbul.get_name('la')}")
    print(f"Notes: {istanbul.notes}")
    print()

    # Example 6: Place with hierarchy
    print("Example 6: Place with hierarchical structure")
    print("-" * 70)
    brooklyn = Place(
        names={'en': 'Brooklyn'},
        hierarchy=['Brooklyn', 'Kings County', 'New York', 'USA'],
        latitude=40.6782,
        longitude=-73.9442
    )

    print(f"Place name: {brooklyn}")
    print(f"Hierarchy: {' > '.join(brooklyn.hierarchy)}")
    print(f"GEDCOM format: {brooklyn.get_gedcom_format()}")
    print()

    # Example 7: Merging places
    print("Example 7: Merging place information")
    print("-" * 70)
    place1 = Place(
        names={'en': 'St. Petersburg'},
        latitude=59.9343,
        longitude=30.3351
    )

    place2 = Place(
        names={
            'ru': 'Санкт-Петербург',
            'de': 'Sankt Petersburg'
        },
        notes='Formerly Leningrad (1924-1991) and Petrograd (1914-1924)'
    )

    merged = place1.merge_with(place2)
    print(f"English: {merged.get_name('en')}")
    print(f"Russian: {merged.get_name('ru')}")
    print(f"German: {merged.get_name('de')}")
    print(f"Coordinates: ({merged.latitude}, {merged.longitude})")
    print(f"Notes: {merged.notes}")
    print()

    # Example 8: Serialization
    print("Example 8: Serializing and deserializing")
    print("-" * 70)
    original = Place(
        names={
            'en': 'Vienna',
            'de': 'Wien',
            'hu': 'Bécs',
            'cs': 'Vídeň'
        },
        primary_language='de',
        latitude=48.2082,
        longitude=16.3738,
        place_type='city',
        notes='Capital of Austria'
    )

    # Convert to dictionary
    data = original.to_dict()
    print(f"Serialized to dict: {len(data)} fields")

    # Restore from dictionary
    restored = Place.from_dict(data)
    print(f"Restored place: {restored}")
    print(f"Languages available: {list(restored.names.keys())}")
    print()

    print("=" * 70)
    print("Demonstration complete!")
    print("=" * 70)


if __name__ == '__main__':
    main()
