#!/usr/bin/env python3
"""Test script to verify French name parsing fixes."""

import sys
import os

# Add the GedMerge directory to path and import directly
sys.path.insert(0, '/home/user/Python-Scripts/GedMerge/gedmerge/utils')
from name_parser import NameParser


def test_m_marie_for_females():
    """Test that M. is replaced with Marie for female names."""
    print("\n=== Testing M. -> Marie for female names ===")

    # Test 1: M. Anne (female) should become "Marie Anne"
    result = NameParser.parse_givn_field("M. Anne", sex='F')
    print(f"Input: 'M. Anne' (sex='F')")
    print(f"  Given: {result.given}")
    print(f"  Prefix: {result.prefix}")
    assert result.given == "Marie Anne", f"Expected 'Marie Anne', got '{result.given}'"
    assert result.prefix is None, f"Expected no prefix, got '{result.prefix}'"
    print("  ✓ PASS")

    # Test 2: M. in NAME field
    result = NameParser.parse_name_field("M. Anne /de Bréval/", sex='F')
    print(f"\nInput: 'M. Anne /de Bréval/' (sex='F')")
    print(f"  Given: {result.given}")
    print(f"  Surname: {result.surname}")
    print(f"  Prefix: {result.prefix}")
    assert result.given == "Marie Anne", f"Expected 'Marie Anne', got '{result.given}'"
    assert result.surname == "de Bréval", f"Expected 'de Bréval', got '{result.surname}'"
    assert result.prefix is None, f"Expected no prefix, got '{result.prefix}'"
    print("  ✓ PASS")

    # Test 3: M. should still work as prefix for males
    result = NameParser.parse_givn_field("M. Jean", sex='M')
    print(f"\nInput: 'M. Jean' (sex='M')")
    print(f"  Given: {result.given}")
    print(f"  Prefix: {result.prefix}")
    assert result.given == "Jean", f"Expected 'Jean', got '{result.given}'"
    assert result.prefix == "M.", f"Expected 'M.' prefix, got '{result.prefix}'"
    print("  ✓ PASS")


def test_seigneur_as_suffix():
    """Test that Seigneur is treated as a suffix, not a prefix."""
    print("\n=== Testing Seigneur as suffix ===")

    # Test: "Seigneur d'Amboise et Chaumont" should be a suffix
    result = NameParser.parse_field_with_surname_particle("Pierre Seigneur d'Amboise et Chaumont")
    print(f"Input: 'Pierre Seigneur d'Amboise et Chaumont'")
    print(f"  Given: {result.given}")
    print(f"  Surname: {result.surname}")
    print(f"  Suffix: {result.suffix}")
    print(f"  Prefix: {result.prefix}")
    assert result.given == "Pierre", f"Expected 'Pierre', got '{result.given}'"
    assert "Seigneur" in result.suffix, f"Expected Seigneur in suffix, got suffix='{result.suffix}'"
    assert result.prefix is None or "Seigneur" not in (result.prefix or ""), \
        f"Seigneur should not be in prefix, got '{result.prefix}'"
    print("  ✓ PASS")


def test_de_particles_in_surnames():
    """Test that 'de' and similar particles stay with surnames."""
    print("\n=== Testing 'de' particles in surnames ===")

    # Test 1: "de Bréval"
    result = NameParser.parse_name_field("Anne /de Bréval/")
    print(f"Input: 'Anne /de Bréval/'")
    print(f"  Given: {result.given}")
    print(f"  Surname: {result.surname}")
    assert result.given == "Anne", f"Expected 'Anne', got '{result.given}'"
    assert result.surname == "de Bréval", f"Expected 'de Bréval', got '{result.surname}'"
    print("  ✓ PASS")

    # Test 2: Chadalhoh von OGIERS-ISENGAU
    result = NameParser.extract_surname_with_particle("Chadalhoh von OGIERS-ISENGAU")
    print(f"\nInput: 'Chadalhoh von OGIERS-ISENGAU'")
    print(f"  Remaining: {result[0]}")
    print(f"  Surname: {result[1]}")
    assert result[0] == "Chadalhoh", f"Expected 'Chadalhoh', got '{result[0]}'"
    assert result[1] == "von OGIERS-ISENGAU", f"Expected 'von OGIERS-ISENGAU', got '{result[1]}'"
    print("  ✓ PASS")

    # Test 3: NAME field with von particle
    result = NameParser.parse_name_field("Chadalhoh /von Ogiers-Isengau/")
    print(f"\nInput: 'Chadalhoh /von Ogiers-Isengau/'")
    print(f"  Given: {result.given}")
    print(f"  Surname: {result.surname}")
    assert result.given == "Chadalhoh", f"Expected 'Chadalhoh', got '{result.given}'"
    assert result.surname == "von Ogiers-Isengau", f"Expected 'von Ogiers-Isengau', got '{result.surname}'"
    print("  ✓ PASS")


def test_combined_french_name():
    """Test a complex French female name with all fixes."""
    print("\n=== Testing combined French name ===")

    # M. Marie de France (female)
    result = NameParser.parse_name_field("M. Marie /de France/", sex='F')
    print(f"Input: 'M. Marie /de France/' (sex='F')")
    print(f"  Given: {result.given}")
    print(f"  Surname: {result.surname}")
    print(f"  Prefix: {result.prefix}")
    assert result.given == "Marie Marie", f"Expected 'Marie Marie', got '{result.given}'"
    assert result.surname == "de France", f"Expected 'de France', got '{result.surname}'"
    assert result.prefix is None, f"Expected no prefix, got '{result.prefix}'"
    print("  ✓ PASS")


def main():
    """Run all tests."""
    print("=" * 60)
    print("FRENCH NAME PARSING FIXES - TEST SUITE")
    print("=" * 60)

    try:
        test_m_marie_for_females()
        test_seigneur_as_suffix()
        test_de_particles_in_surnames()
        test_combined_french_name()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED! ✓")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
