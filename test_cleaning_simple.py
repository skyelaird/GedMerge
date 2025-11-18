#!/usr/bin/env python3
"""Simple test script for cleaning utilities (no pytest required)."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Import directly without going through __init__.py to avoid missing dependencies
from gedmerge.utils.place_cleaner import PlaceCleaner
from gedmerge.utils.name_cleaner import NameCleaner
from gedmerge.validation import date_validator


def test_place_cleaner():
    """Test PlaceCleaner functionality."""
    print("\n" + "="*80)
    print("TESTING PlaceCleaner")
    print("="*80)

    # Test 1: UK county normalization
    print("\n1. UK county normalization (Warwick -> Warwickshire):")
    cleaned = PlaceCleaner.clean_place_name("Burton Dassett, Warwick, England")
    print(f"   Original: 'Burton Dassett, Warwick, England'")
    print(f"   Cleaned:  '{cleaned.cleaned}'")
    print(f"   Changes:  {cleaned.changes_made}")
    assert cleaned.cleaned == "Burton Dassett, Warwickshire, England"
    print("   ✓ PASS")

    # Test 2: Remove 'of' prefix
    print("\n2. Remove 'of' prefix:")
    cleaned = PlaceCleaner.clean_place_name("of Seavington Saint Michael, Somerset, England")
    print(f"   Original: 'of Seavington Saint Michael, Somerset, England'")
    print(f"   Cleaned:  '{cleaned.cleaned}'")
    print(f"   Changes:  {cleaned.changes_made}")
    assert cleaned.cleaned == "Seavington Saint Michael, Somerset, England"
    print("   ✓ PASS")

    # Test 3: Postal code removal
    print("\n3. Postal code removal:")
    cleaned = PlaceCleaner.clean_place_name("Ottawa, Ontario, Canada, K1A 0B1")
    print(f"   Original: 'Ottawa, Ontario, Canada, K1A 0B1'")
    print(f"   Cleaned:  '{cleaned.cleaned}'")
    print(f"   Postal:   '{cleaned.postal_code}'")
    assert "K1A 0B1" not in cleaned.cleaned
    assert cleaned.postal_code == "K1A 0B1"
    print("   ✓ PASS")

    # Test 4: All uppercase
    print("\n4. Fix all uppercase:")
    cleaned = PlaceCleaner.clean_place_name("BURTON UPON TRENT, STAFFORDSHIRE, ENGLAND")
    print(f"   Original: 'BURTON UPON TRENT, STAFFORDSHIRE, ENGLAND'")
    print(f"   Cleaned:  '{cleaned.cleaned}'")
    assert cleaned.cleaned == "Burton upon Trent, Staffordshire, England"
    print("   ✓ PASS")

    # Test 5: Duplicate detection
    print("\n5. Duplicate detection (UK counties):")
    should_merge, confidence, reason = PlaceCleaner.suggest_merge_candidates(
        "Burton Dassett, Warwick, England",
        "Burton Dassett, Warwickshire, England"
    )
    print(f"   Place 1: 'Burton Dassett, Warwick, England'")
    print(f"   Place 2: 'Burton Dassett, Warwickshire, England'")
    print(f"   Should merge: {should_merge}")
    print(f"   Confidence: {confidence}")
    print(f"   Reason: {reason}")
    assert should_merge is True
    print("   ✓ PASS")

    print("\n✓ All PlaceCleaner tests passed!")


def test_name_cleaner():
    """Test NameCleaner functionality."""
    print("\n" + "="*80)
    print("TESTING NameCleaner")
    print("="*80)

    # Test 1: Remove 'feu'
    print("\n1. Remove 'feu' (French for deceased):")
    cleaned = NameCleaner.clean_name_components(given="feu Jean")
    print(f"   Original: 'feu Jean'")
    print(f"   Cleaned:  '{cleaned.cleaned_given}'")
    print(f"   Changes:  {cleaned.changes_made}")
    assert cleaned.cleaned_given == "Jean"
    print("   ✓ PASS")

    # Test 2: All uppercase
    print("\n2. Fix all uppercase:")
    cleaned = NameCleaner.clean_name_components(
        given="JEAN-BAPTISTE",
        surname="DE LA FONTAINE"
    )
    print(f"   Original: 'JEAN-BAPTISTE' / 'DE LA FONTAINE'")
    print(f"   Cleaned:  '{cleaned.cleaned_given}' / '{cleaned.cleaned_surname}'")
    assert cleaned.cleaned_given == "Jean-Baptiste"
    assert cleaned.cleaned_surname == "de la Fontaine"
    print("   ✓ PASS")

    # Test 3: Prefix standardization
    print("\n3. Prefix standardization:")
    cleaned = NameCleaner.clean_name_components(prefix="mr")
    print(f"   Original: 'mr'")
    print(f"   Cleaned:  '{cleaned.cleaned_prefix}'")
    assert cleaned.cleaned_prefix == "Mr."
    print("   ✓ PASS")

    # Test 4: Description detection
    print("\n4. Description detection:")
    cleaned = NameCleaner.clean_name_components(given="unknown")
    print(f"   Given name: 'unknown'")
    print(f"   Warnings: {cleaned.warnings}")
    assert any("description" in warning for warning in cleaned.warnings)
    print("   ✓ PASS")

    print("\n✓ All NameCleaner tests passed!")


def test_date_validator():
    """Test DateValidator functionality."""
    print("\n" + "="*80)
    print("TESTING DateValidator (Birth After Death)")
    print("="*80)

    validator = date_validator.DateValidator()

    # Test 1: Birth after death
    print("\n1. Birth after death detection:")
    birth = validator.parse_date("1900")
    death = validator.parse_date("1850")
    is_error, message = validator.validate_birth_after_death(birth, death)
    print(f"   Birth: 1900")
    print(f"   Death: 1850")
    print(f"   Is error: {is_error}")
    print(f"   Message: {message}")
    assert is_error is True
    assert "SUSPICIOUS" in message
    print("   ✓ PASS")

    # Test 2: Normal order
    print("\n2. Normal birth before death:")
    birth = validator.parse_date("1850")
    death = validator.parse_date("1900")
    is_error, message = validator.validate_birth_after_death(birth, death)
    print(f"   Birth: 1850")
    print(f"   Death: 1900")
    print(f"   Is error: {is_error}")
    assert is_error is False
    print("   ✓ PASS")

    print("\n✓ All DateValidator tests passed!")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("RUNNING CLEANING UTILITIES TESTS")
    print("="*80)

    try:
        test_place_cleaner()
        test_name_cleaner()
        test_date_validator()

        print("\n" + "="*80)
        print("ALL TESTS PASSED!")
        print("="*80)
        return 0

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1

    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
