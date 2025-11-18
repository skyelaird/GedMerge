#!/usr/bin/env python3
"""Simple test script to demonstrate name parsing functionality."""

import sys
sys.path.insert(0, '/home/user/Python-Scripts/GedMerge/gedmerge/utils')

from name_parser import NameParser

def print_parsed_name(parsed, indent="  "):
    """Pretty print a ParsedName object."""
    if parsed.prefix:
        print(f"{indent}Prefix: {parsed.prefix}")
    if parsed.given:
        print(f"{indent}Given: {parsed.given}")
    if parsed.ordinal:
        print(f"{indent}Ordinal: {parsed.ordinal}")
    if parsed.surname:
        print(f"{indent}Surname: {parsed.surname}")
    if parsed.nickname:
        print(f"{indent}Nickname: {parsed.nickname}")
    if parsed.epithets:
        print(f"{indent}Epithets: {', '.join(parsed.epithets)}")
    if parsed.suffix:
        print(f"{indent}Suffix: {parsed.suffix}")

def main():
    print("="*80)
    print("NAME PARSING TESTS - User Examples")
    print("="*80)

    # Test 1: User's first example
    print("\n1. Parsing GIVN field: \"Thomas II 'The Wise' 1st Baron\"")
    print("   Expected:")
    print("     - Given: Thomas II")
    print("     - Nickname: The Wise")
    print("     - Suffix: 1st Baron")
    result = NameParser.parse_givn_field("Thomas II 'The Wise' 1st Baron")
    print("   Result:")
    print_parsed_name(result, "     - ")

    # Test 2: User's second example
    print("\n2. Parsing NICK field: \"Frau Gerberga von Franconia\"")
    print("   (This should NOT be a nickname - contains surname particle)")
    print("   Expected:")
    print("     - Prefix: Frau")
    print("     - Given: Gerberga")
    print("     - Surname: von Franconia")
    result = NameParser.parse_field_with_surname_particle("Frau Gerberga von Franconia", "NICK")
    print("   Result:")
    print_parsed_name(result, "     - ")

    # Test 3: Variation with "de France"
    print("\n3. Parsing field: \"Dame Marie de France\"")
    print("   Expected:")
    print("     - Prefix: Dame")
    print("     - Given: Marie")
    print("     - Surname: de France")
    result = NameParser.parse_field_with_surname_particle("Dame Marie de France", "NICK")
    print("   Result:")
    print_parsed_name(result, "     - ")

    # Test 4: Variation with "de Francie" (French spelling)
    print("\n4. Parsing field: \"Gerberga de Francie\"")
    print("   Expected:")
    print("     - Given: Gerberga")
    print("     - Surname: de Francie")
    result = NameParser.parse_field_with_surname_particle("Gerberga de Francie", "NICK")
    print("   Result:")
    print_parsed_name(result, "     - ")

    # Test 5: Normalizing misclassified fields
    print("\n5. Normalizing misclassified nickname: \"von Franconia\"")
    print("   (Nickname field containing only surname particle)")
    print("   Expected:")
    print("     - Surname: von Franconia (moved from nickname)")
    print("     - Nickname: None")
    result = NameParser.normalize_name_components(
        given="Gerberga",
        nickname="von Franconia"
    )
    print("   Result:")
    print_parsed_name(result, "     - ")

    # Test 6: Full NAME field parsing
    print("\n6. Parsing NAME field: \"Sir Thomas II 'The Wise' /Smith/ 1st Baron\"")
    print("   Expected:")
    print("     - Prefix: Sir")
    print("     - Given: Thomas II")
    print("     - Ordinal: II")
    print("     - Surname: Smith")
    print("     - Nickname: The Wise")
    print("     - Suffix: 1st Baron")
    result = NameParser.parse_name_field("Sir Thomas II 'The Wise' /Smith/ 1st Baron")
    print("   Result:")
    print_parsed_name(result, "     - ")

    # Test 7: Surname particle detection
    print("\n7. Surname Particle Detection")
    print("   Testing various particles:")
    particles = ["von", "de", "van", "du", "van der", "von und zu"]
    non_particles = ["Franconia", "France", "Smith", "Thomas"]

    for word in particles:
        is_particle = NameParser.is_surname_particle(word)
        print(f"     - \"{word}\": {is_particle} (should be True)")

    for word in non_particles:
        is_particle = NameParser.is_surname_particle(word)
        print(f"     - \"{word}\": {is_particle} (should be False)")

    # Test 8: Prefix detection
    print("\n8. Prefix Detection")
    print("   Testing various prefixes:")
    prefixes = ["Frau", "Herr", "Sir", "Lady", "Dame", "Lord"]
    non_prefixes = ["Thomas", "Gerberga", "von", "Smith"]

    for word in prefixes:
        is_prefix = NameParser.is_prefix(word)
        print(f"     - \"{word}\": {is_prefix} (should be True)")

    for word in non_prefixes:
        is_prefix = NameParser.is_prefix(word)
        print(f"     - \"{word}\": {is_prefix} (should be False)")

    # Test 9: Tagged name field parsing
    print("\n9. Parsing tagged name field: \"Geoffroi 'Bocourt' [GIVN] de Limoges Vicomte de Limoges [Surname]\"")
    print("   Expected:")
    print("     - Given: Geoffroi")
    print("     - Nickname: Bocourt")
    print("     - Surname: de Limoges Vicomte de Limoges")
    result = NameParser.parse_tagged_name_field("Geoffroi 'Bocourt' [GIVN] de Limoges Vicomte de Limoges [Surname]")
    print("   Result:")
    print_parsed_name(result, "     - ")

    # Test 10: ALLCAPS name with particles
    print("\n10. Smart title casing: \"DE CHANAC DE TURENNE-D'ANGOULEME\"")
    print("   Expected: de Chanac de Turenne-d'Angouleme")
    result = NameParser.smart_title_case("DE CHANAC DE TURENNE-D'ANGOULEME")
    print(f"   Result: {result}")

    # Test 11: ALLCAPS simple name
    print("\n11. Smart title casing: \"GEOFFROI DE LIMOGES\"")
    print("   Expected: Geoffroi de Limoges")
    result = NameParser.smart_title_case("GEOFFROI DE LIMOGES")
    print(f"   Result: {result}")

    # Test 12: Text ordinals
    print("\n12. Parsing text ordinal: \"Thomas the First\"")
    print("   Expected:")
    print("     - Given: Thomas the First")
    print("     - Ordinal: the First")
    result = NameParser.parse_givn_field("Thomas the First")
    print("   Result:")
    print_parsed_name(result, "     - ")

    # Test 13: Combined ALLCAPS tagged field
    print("\n13. Parsing ALLCAPS tagged field: \"GEOFFROI [GIVN] DE LIMOGES [Surname]\"")
    print("   Expected:")
    print("     - Given: Geoffroi")
    print("     - Surname: de Limoges")
    result = NameParser.parse_tagged_name_field("GEOFFROI [GIVN] DE LIMOGES [Surname]")
    print("   Result:")
    print_parsed_name(result, "     - ")

    # Test 14: Ordinal with nickname and title
    print("\n14. Parsing complex GIVN: \"Richard II 'Lionheart'\"")
    print("   Expected:")
    print("     - Given: Richard II")
    print("     - Ordinal: II")
    print("     - Nickname: Lionheart")
    result = NameParser.parse_givn_field("Richard II 'Lionheart'")
    print("   Result:")
    print_parsed_name(result, "     - ")

    print("\n" + "="*80)
    print("TESTS COMPLETE")
    print("="*80)

if __name__ == '__main__':
    main()
