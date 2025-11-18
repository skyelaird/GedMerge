#!/usr/bin/env python3
"""
Generate comprehensive equivalency tables from the language support system.
"""

import sys
from pathlib import Path

# Add the gedmerge data directory to path
data_dir = Path(__file__).parent / "gedmerge" / "data"
sys.path.insert(0, str(Path(__file__).parent))

# Import directly from the language_support module
exec(open(data_dir / "language_support.py").read())

def main():
    """Generate and display equivalency tables."""

    print("=" * 100)
    print(" " * 30 + "COMPREHENSIVE EQUIVALENCY TABLES")
    print("=" * 100)

    # Create registry
    registry = MultilingualRegistry()

    categories = [
        ("title", "TITLES AND HONORIFICS"),
        ("relationship", "FAMILY RELATIONSHIPS"),
        ("event", "EVENT TYPES"),
        ("occupation", "OCCUPATIONS")
    ]

    for category, title in categories:
        print(f"\n{'─' * 100}")
        print(f"  {title}")
        print(f"{'─' * 100}\n")
        print(registry.export_table(category))

    # Print summary
    print(f"\n{'=' * 100}")
    print(" " * 40 + "SUMMARY")
    print(f"{'=' * 100}\n")

    total_terms = len(registry.terms)
    categories_count = {}
    total_translations = 0

    for term in registry.terms.values():
        categories_count[term.category] = categories_count.get(term.category, 0) + 1
        translations = sum(1 for lang in [term.french, term.german, term.spanish,
                                         term.italian, term.portuguese] if lang)
        total_translations += translations

    print(f"Total canonical terms:        {total_terms}")
    print(f"Total translations:           {total_translations}")
    print(f"Average translations/term:    {total_translations / total_terms:.1f}")
    print(f"Total unique forms:           {len(registry.reverse_index)}")

    print("\nTerms by category:")
    for category, count in sorted(categories_count.items()):
        print(f"  {category.capitalize():15} {count:3} terms")

    # Demonstrate normalization
    print(f"\n{'=' * 100}")
    print(" " * 35 + "NORMALIZATION EXAMPLES")
    print(f"{'=' * 100}\n")

    examples = [
        "Capitaine", "Père", "Naissance", "Hauptmann", "Vater",
        "Médecin", "Commerçant", "Roi", "Duc", "Mariage"
    ]

    print(f"{'Original':<20} {'Normalized to English':<25} {'Language':<15} {'Category':<15}")
    print("-" * 75)

    detector = LanguageDetector()
    for example in examples:
        normalized, lang, alternates = registry.normalize(example, detect_language=True)
        # Find the term to get category
        canonical = registry.reverse_index.get(example.lower(), example.lower())
        term_obj = registry.terms.get(canonical)
        category = term_obj.category if term_obj else "unknown"

        print(f"{example:<20} {normalized:<25} {lang.name if lang else 'N/A':<15} {category:<15}")

    # Show adaptive learning capability
    print(f"\n{'=' * 100}")
    print(" " * 30 + "ADAPTIVE LEARNING DEMONSTRATION")
    print(f"{'=' * 100}\n")

    print("The system can learn new equivalencies dynamically:\n")
    print("  registry.learn_equivalency('Mason', 'Maçon', 'occupation')")
    print("  registry.learn_equivalency('Admiral', 'Amiral', 'title')")
    print("  registry.learn_equivalency('Godfather', 'Parrain', 'relationship')")

    # Actually learn them
    new_terms = [
        ("Mason", "Maçon", "occupation"),
        ("Admiral", "Amiral", "title"),
        ("Godfather", "Parrain", "relationship")
    ]

    print("\nLearning new terms...")
    for english, foreign, category in new_terms:
        registry.learn_equivalency(english, foreign, category)
        print(f"  ✓ {english} ↔ {foreign} ({category})")

    print("\nNow testing the newly learned terms:")
    for _, foreign, _ in new_terms:
        normalized, _, _ = registry.normalize(foreign)
        print(f"  '{foreign}' normalizes to '{normalized}'")

    print(f"\n{'=' * 100}")
    print(" " * 40 + "KEY FEATURES")
    print(f"{'=' * 100}\n")

    print("✓ Supports 6 languages: English, French, German, Spanish, Italian, Portuguese")
    print("✓ Automatic language detection using pattern matching")
    print("✓ Normalization to English canonical forms")
    print("✓ Preservation of alternate names for cross-referencing")
    print("✓ Adaptive learning of new equivalencies from data")
    print("✓ Category-based organization (titles, relationships, events, occupations)")
    print("✓ JSON persistence for saving/loading learned terms")
    print("✓ Extensible architecture - easy to add new languages or categories")

    print(f"\n{'=' * 100}\n")


if __name__ == "__main__":
    main()
