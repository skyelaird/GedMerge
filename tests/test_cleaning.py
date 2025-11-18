"""Tests for place and name cleaning utilities."""

import pytest
from gedmerge.utils.place_cleaner import PlaceCleaner
from gedmerge.utils.name_cleaner import NameCleaner
from gedmerge.validation.date_validator import DateValidator, ParsedDate


class TestPlaceCleaner:
    """Test PlaceCleaner functionality."""

    def test_uk_county_normalization(self):
        """Test UK county normalization (Warwick -> Warwickshire)."""
        # Test case from user's issues
        cleaned = PlaceCleaner.clean_place_name("Burton Dassett, Warwick, England")
        assert cleaned.cleaned == "Burton Dassett, Warwickshire, England"
        assert "Normalized UK county: Warwick -> Warwickshire" in cleaned.changes_made

    def test_duplicate_detection_uk_counties(self):
        """Test that UK county variations are detected as duplicates."""
        should_merge, confidence, reason = PlaceCleaner.suggest_merge_candidates(
            "Burton Dassett, Warwick, England",
            "Burton Dassett, Warwickshire, England"
        )
        assert should_merge is True
        assert confidence >= 0.95
        assert "UK county variation" in reason

    def test_remove_of_prefix(self):
        """Test removal of 'of' prefix from place names."""
        cleaned = PlaceCleaner.clean_place_name("of Seavington Saint Michael, Somerset, England")
        assert cleaned.cleaned == "Seavington Saint Michael, Somerset, England"
        assert "Removed 'of' prefix" in cleaned.changes_made

    def test_postal_code_removal(self):
        """Test postal code removal."""
        # Canadian postal code
        cleaned = PlaceCleaner.clean_place_name("Ottawa, Ontario, Canada, K1A 0B1")
        assert "K1A 0B1" not in cleaned.cleaned
        assert cleaned.postal_code == "K1A 0B1"

        # US ZIP code
        cleaned = PlaceCleaner.clean_place_name("New York, NY, USA, 10001")
        assert "10001" not in cleaned.cleaned
        assert cleaned.postal_code == "10001"

    def test_all_uppercase_fixing(self):
        """Test fixing of all uppercase place names."""
        cleaned = PlaceCleaner.clean_place_name("BURTON UPON TRENT, STAFFORDSHIRE, ENGLAND")
        assert cleaned.cleaned == "Burton upon Trent, Staffordshire, England"
        assert "Converted from all uppercase" in cleaned.changes_made

    def test_abbreviation_expansion(self):
        """Test expansion of abbreviations."""
        cleaned = PlaceCleaner.clean_place_name("St. Louis, MO")
        assert "Saint Louis" in cleaned.cleaned

        cleaned = PlaceCleaner.clean_place_name("Mt. Vernon, NY")
        assert "Mount Vernon" in cleaned.cleaned

    def test_spacing_and_punctuation(self):
        """Test fixing of spacing and punctuation issues."""
        # Multiple spaces
        cleaned = PlaceCleaner.clean_place_name("Paris,  France")
        assert cleaned.cleaned == "Paris, France"
        assert "Fixed multiple spaces" in cleaned.changes_made

        # Space before comma
        cleaned = PlaceCleaner.clean_place_name("London , England")
        assert cleaned.cleaned == "London, England"
        assert "Removed space before comma" in cleaned.changes_made

    def test_blank_hierarchy_pieces(self):
        """Test removal of blank hierarchy pieces."""
        cleaned = PlaceCleaner.clean_place_name("Paris, , France")
        assert cleaned.cleaned == "Paris, France"
        assert "Removed 1 blank hierarchy pieces" in cleaned.changes_made

    def test_hierarchy_parsing(self):
        """Test hierarchy parsing."""
        cleaned = PlaceCleaner.clean_place_name("Canterbury, Kent, England")
        assert cleaned.normalized_hierarchy == ["Canterbury", "Kent", "England"]

    def test_misplaced_details_warning(self):
        """Test warning for misplaced place details."""
        cleaned = PlaceCleaner.clean_place_name("Canterbury Cathedral, Canterbury, Kent, England")
        # Should warn that Cathedral might need separate hierarchy
        assert any("Place detail" in warning for warning in cleaned.warnings)


class TestNameCleaner:
    """Test NameCleaner functionality."""

    def test_remove_feu(self):
        """Test removal of French 'feu' (deceased)."""
        cleaned = NameCleaner.clean_name_components(given="feu Jean")
        assert cleaned.cleaned_given == "Jean"
        assert "Removed 'feu' (French for deceased)" in cleaned.changes_made

        cleaned = NameCleaner.clean_name_components(given="Feue Marie")
        assert cleaned.cleaned_given == "Marie"

    def test_all_uppercase_fixing(self):
        """Test fixing of all uppercase names."""
        cleaned = NameCleaner.clean_name_components(
            given="JEAN-BAPTISTE",
            surname="DE LA FONTAINE"
        )
        assert cleaned.cleaned_given == "Jean-Baptiste"
        assert cleaned.cleaned_surname == "de la Fontaine"

    def test_spacing_fixing(self):
        """Test fixing of spacing issues."""
        cleaned = NameCleaner.clean_name_components(given="Jean  Baptiste")
        assert cleaned.cleaned_given == "Jean Baptiste"
        assert "Fixed multiple spaces" in cleaned.changes_made

    def test_prefix_standardization(self):
        """Test standardization of prefixes."""
        cleaned = NameCleaner.clean_name_components(prefix="mr")
        assert cleaned.cleaned_prefix == "Mr."

        cleaned = NameCleaner.clean_name_components(prefix="mrs")
        assert cleaned.cleaned_prefix == "Mrs."

    def test_suffix_standardization(self):
        """Test standardization of suffixes."""
        cleaned = NameCleaner.clean_name_components(suffix="jr")
        assert cleaned.cleaned_suffix == "Jr."

        cleaned = NameCleaner.clean_name_components(suffix="iii")
        assert cleaned.cleaned_suffix == "III"

    def test_description_detection(self):
        """Test detection of descriptions rather than names."""
        cleaned = NameCleaner.clean_name_components(given="unknown")
        assert any("appears to be a description" in warning for warning in cleaned.warnings)

        cleaned = NameCleaner.clean_name_components(surname="deceased")
        assert any("appears to be a description" in warning for warning in cleaned.warnings)

    def test_alternate_name_detection(self):
        """Test detection of alternate name patterns."""
        cleaned = NameCleaner.clean_name_components(given="Jean (John)")
        assert any("alternate name pattern" in warning for warning in cleaned.warnings)

    def test_surname_particle_in_nickname_warning(self):
        """Test warning when nickname contains surname particles."""
        cleaned = NameCleaner.clean_name_components(nickname="von Franconia")
        assert any("surname particle" in warning for warning in cleaned.warnings)

    def test_cross_field_issues(self):
        """Test detection of cross-field issues."""
        # Same given and surname
        cleaned = NameCleaner.clean_name_components(given="Smith", surname="Smith")
        assert any("identical" in warning for warning in cleaned.warnings)

    def test_wife_shares_husband_surname(self):
        """Test detection of wife sharing husband's surname error."""
        is_error, explanation = NameCleaner.detect_wife_shares_husband_surname(
            wife_given="John Smith",
            wife_surname="Smith",
            husband_given="John",
            husband_surname="Smith"
        )
        assert is_error is True
        assert "husband's surname" in explanation


class TestDateValidator:
    """Test DateValidator functionality."""

    def test_birth_after_death_detection(self):
        """Test detection of birth after death error."""
        validator = DateValidator()

        birth = validator.parse_date("1900")
        death = validator.parse_date("1850")

        is_error, message = validator.validate_birth_after_death(birth, death)
        assert is_error is True
        assert "SUSPICIOUS" in message
        assert "1900" in message
        assert "1850" in message

    def test_birth_after_death_same_year_different_months(self):
        """Test birth after death in same year but different months."""
        validator = DateValidator()

        birth = validator.parse_date("10 JUN 1900")
        death = validator.parse_date("5 JAN 1900")

        is_error, message = validator.validate_birth_after_death(birth, death)
        assert is_error is True
        assert "SUSPICIOUS" in message

    def test_normal_birth_death_order(self):
        """Test normal birth before death."""
        validator = DateValidator()

        birth = validator.parse_date("1850")
        death = validator.parse_date("1900")

        is_error, message = validator.validate_birth_after_death(birth, death)
        assert is_error is False
        assert message == ''

    def test_validate_date_range_with_birth_after_death(self):
        """Test that validate_date_range catches birth after death."""
        validator = DateValidator()

        birth = validator.parse_date("1900")
        death = validator.parse_date("1850")

        result, issues = validator.validate_date_range(birth, death)
        assert result == validator.DateValidationResult.INVALID if hasattr(validator, 'DateValidationResult') else result.name == 'INVALID'
        assert len(issues) > 0
        assert "SUSPICIOUS" in issues[0]


class TestPlaceDuplicateFinding:
    """Test duplicate place finding functionality."""

    def test_find_duplicates_simple(self):
        """Test finding simple duplicates."""
        places = [
            (1, "Paris, France"),
            (2, "PARIS, FRANCE"),
            (3, "Paris,France"),  # Missing space
        ]

        duplicates = PlaceCleaner.find_duplicate_places(places)
        assert "paris, france" in duplicates
        assert len(duplicates["paris, france"]) == 3

    def test_find_duplicates_uk_counties(self):
        """Test finding duplicates with UK county variations."""
        places = [
            (1, "Burton Dassett, Warwick, England"),
            (2, "Burton Dassett, Warwickshire, England"),
        ]

        duplicates = PlaceCleaner.find_duplicate_places(places, normalize_uk_counties=True)
        # After normalization, both should map to the same place
        assert len(duplicates) == 1
        normalized_key = list(duplicates.keys())[0]
        assert len(duplicates[normalized_key]) == 2

    def test_find_duplicates_postal_codes(self):
        """Test finding duplicates ignoring postal codes."""
        places = [
            (1, "Ottawa, Ontario, Canada"),
            (2, "Ottawa, Ontario, Canada, K1A 0B1"),
        ]

        duplicates = PlaceCleaner.find_duplicate_places(places, normalize_uk_counties=True)
        # After removing postal code, should be duplicates
        assert len(duplicates) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
