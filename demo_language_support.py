#!/usr/bin/env python3
"""
Demonstration of the adaptive multilingual support system.

Shows how to:
1. Normalize multilingual terms to English
2. Detect languages
3. Learn new equivalencies
4. Export comprehensive tables
"""

from gedmerge.data.language_support import (
    get_registry,
    MultilingualTerm,
    Language,
    normalize_term,
    detect_language
)


def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'=' * 80}")
    print(f"{title:^80}")
    print('=' * 80)


def demo_normalization():
    """Demonstrate term normalization."""
    print_section("TERM NORMALIZATION EXAMPLES")

    examples = [
        "Capitaine",
        "Père",
        "Naissance",
        "Hauptmann",
        "Vater",
        "Geburt",
        "Capitán",
        "Padre",
        "Mère",
        "Médecin",
        "Boulanger",
        "Roi"
    ]

    print("\n{:<20} {:<15} {:<40}".format("Original", "Normalized", "Alternates"))
    print("-" * 75)

    for term in examples:
        normalized, alternates = normalize_term(term)
        alt_str = ", ".join(alternates[:3])  # Show first 3 alternates
        if len(alternates) > 3:
            alt_str += "..."
        print(f"{term:<20} {normalized:<15} {alt_str:<40}")


def demo_language_detection():
    """Demonstrate language detection."""
    print_section("LANGUAGE DETECTION EXAMPLES")

    examples = [
        "Capitaine des Milices",
        "Hauptmann der Reserve",
        "Médecin de la famille",
        "Père de trois enfants",
        "Vater von drei Kindern",
        "Comerciante en la ciudad",
        "Cultivateur à Québec",
        "Bauer in Deutschland",
        "Lieutenant dans l'armée",
        "Tenente nell'esercito"
    ]

    print("\n{:<40} {:<15}".format("Text", "Detected Language"))
    print("-" * 55)

    for text in examples:
        lang = detect_language(text)
        print(f"{text:<40} {lang.name:<15}")


def demo_adaptive_learning():
    """Demonstrate adaptive learning of new equivalencies."""
    print_section("ADAPTIVE LEARNING DEMONSTRATION")

    registry = get_registry()

    # Learn some new equivalencies
    new_terms = [
        ("Mason", "Maçon", "occupation"),
        ("Weaver", "Tisserand", "occupation"),
        ("Admiral", "Amiral", "title"),
        ("Godfather", "Parrain", "relationship"),
        ("Godmother", "Marraine", "relationship")
    ]

    print("\nLearning new equivalencies...")
    for english, foreign, category in new_terms:
        success = registry.learn_equivalency(english, foreign, category)
        lang = detect_language(foreign)
        print(f"  ✓ Learned: {english} ↔ {foreign} ({lang.name}, {category})")

    print("\nTesting normalization of newly learned terms:")
    test_terms = ["Maçon", "Tisserand", "Amiral", "Parrain", "Marraine"]
    for term in test_terms:
        normalized, alternates = normalize_term(term)
        print(f"  {term} → {normalized}")


def export_comprehensive_tables():
    """Export comprehensive equivalency tables."""
    print_section("COMPREHENSIVE EQUIVALENCY TABLES")

    registry = get_registry()

    categories = [
        ("title", "TITLES AND HONORIFICS"),
        ("relationship", "FAMILY RELATIONSHIPS"),
        ("event", "EVENT TYPES"),
        ("occupation", "OCCUPATIONS")
    ]

    for category, title in categories:
        print(f"\n### {title} ###\n")
        print(registry.export_table(category))


def analyze_real_data():
    """Analyze some real examples from the GEDCOM data."""
    print_section("REAL DATA EXAMPLES FROM GEDCOM")

    # Real examples found in the data
    real_examples = [
        "maître de poste",
        "Voyageur de commerce pour son pere",
        "Cours commercial",
        "libere de l'armee canadienne outre-mer",
        "Quartier Maitre",
        "Cultivateur",
        "Commerçant"
    ]

    print("\n{:<50} {:<20} {:<15}".format("Original Term", "Normalized", "Language"))
    print("-" * 85)

    registry = get_registry()

    for term in real_examples:
        normalized, lang, alternates = registry.normalize(term)
        print(f"{term:<50} {normalized:<20} {lang.name if lang else 'N/A':<15}")


def summary_statistics():
    """Print summary statistics about the registry."""
    print_section("REGISTRY STATISTICS")

    registry = get_registry()

    total_terms = len(registry.terms)
    categories = {}
    total_translations = 0

    for term in registry.terms.values():
        categories[term.category] = categories.get(term.category, 0) + 1

        # Count non-None translations
        translations = sum(1 for lang in [term.french, term.german, term.spanish,
                                         term.italian, term.portuguese] if lang)
        total_translations += translations

    print(f"\nTotal terms in registry: {total_terms}")
    print(f"Total translations: {total_translations}")
    print(f"Average translations per term: {total_translations / total_terms:.1f}")

    print("\nTerms by category:")
    for category, count in sorted(categories.items()):
        print(f"  {category.capitalize()}: {count}")

    print(f"\nTotal unique forms (including aliases): {len(registry.reverse_index)}")


def main():
    """Run all demonstrations."""
    print("\n" + "█" * 80)
    print("ADAPTIVE MULTILINGUAL SUPPORT SYSTEM FOR GENEALOGY")
    print("█" * 80)

    demo_normalization()
    demo_language_detection()
    demo_adaptive_learning()
    analyze_real_data()
    export_comprehensive_tables()
    summary_statistics()

    print("\n" + "=" * 80)
    print("DEMONSTRATION COMPLETE")
    print("=" * 80)
    print("\nKey Features:")
    print("✓ Automatic language detection (English, French, German, Spanish, Italian, Portuguese)")
    print("✓ Normalization to English canonical forms")
    print("✓ Preservation of alternate names for cross-referencing")
    print("✓ Adaptive learning of new equivalencies")
    print("✓ Extensible category system (titles, relationships, events, occupations)")
    print("✓ JSON persistence for learned terms")
    print("\nUsage in code:")
    print("  from gedmerge.data.language_support import normalize_term, detect_language")
    print("  normalized, alternates = normalize_term('Capitaine')")
    print("  # Returns: ('Captain', ['Capitaine', 'Hauptmann', ...])")


if __name__ == "__main__":
    main()
