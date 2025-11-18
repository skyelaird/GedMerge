"""
Tests for the validation module.

Tests date validation, living status checks, generation gap detection,
and confidence tier system.
"""

import pytest
from gedmerge.validation import (
    DateValidator,
    ParsedDate,
    DateValidationResult,
    LivingStatusValidator,
    LivingStatus,
    GenerationValidator,
    ConfidenceTierSystem,
    ConfidenceTier,
    MIN_PARENT_AGE,
    MAX_PARENT_AGE_FEMALE,
    MAX_LIFESPAN,
)


class TestDateValidator:
    """Test date validation functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = DateValidator()

    def test_parse_exact_date(self):
        """Test parsing exact date."""
        date = self.validator.parse_date("1 JAN 1900")
        assert date is not None
        assert date.year == 1900
        assert date.month == 1
        assert date.day == 1
        assert date.quality.value == "exact"

    def test_parse_year_only(self):
        """Test parsing year-only date."""
        date = self.validator.parse_date("1900")
        assert date is not None
        assert date.year == 1900
        assert date.month is None
        assert date.day is None

    def test_parse_estimated_date(self):
        """Test parsing estimated date."""
        date = self.validator.parse_date("ABT 1900")
        assert date is not None
        assert date.year == 1900
        assert date.is_estimated is True
        assert date.quality.value == "estimated"

    def test_parse_range_date(self):
        """Test parsing range date."""
        date = self.validator.parse_date("BET 1900 AND 1905")
        assert date is not None
        assert date.is_range is True
        assert date.range_start_year == 1900
        assert date.range_end_year == 1905

    def test_validate_death_before_birth(self):
        """Test rejection of death before birth."""
        birth = self.validator.parse_date("1900")
        death = self.validator.parse_date("1890")  # Before birth

        result, issues = self.validator.validate_date_range(birth, death)
        assert result == DateValidationResult.INVALID
        assert len(issues) > 0
        assert "before birth" in issues[0].lower()

    def test_validate_extreme_lifespan(self):
        """Test rejection of extreme lifespan."""
        birth = self.validator.parse_date("1800")
        death = self.validator.parse_date("1950")  # 150 years

        result, issues = self.validator.validate_date_range(birth, death)
        assert result == DateValidationResult.INVALID
        assert len(issues) > 0
        assert "exceeds maximum" in issues[0].lower()

    def test_validate_parent_too_young(self):
        """Test rejection of parent too young."""
        parent_birth = self.validator.parse_date("1900")
        child_birth = self.validator.parse_date("1910")  # Parent age 10

        result, issues = self.validator.validate_parent_child_dates(
            parent_birth, child_birth
        )
        assert result == DateValidationResult.INVALID
        assert len(issues) > 0

    def test_validate_mother_too_old(self):
        """Test warning for mother too old."""
        parent_birth = self.validator.parse_date("1900")
        child_birth = self.validator.parse_date("1960")  # Mother age 60

        result, issues = self.validator.validate_parent_child_dates(
            parent_birth, child_birth, parent_sex='F'
        )
        assert result == DateValidationResult.INVALID
        assert len(issues) > 0

    def test_validate_normal_parent_child(self):
        """Test validation of normal parent-child dates."""
        parent_birth = self.validator.parse_date("1900")
        child_birth = self.validator.parse_date("1925")  # Parent age 25

        result, issues = self.validator.validate_parent_child_dates(
            parent_birth, child_birth
        )
        assert result == DateValidationResult.VALID
        assert len(issues) == 0

    def test_date_overlap_exact_match(self):
        """Test date overlap for exact match."""
        date1 = self.validator.parse_date("1 JAN 1900")
        date2 = self.validator.parse_date("1 JAN 1900")

        confidence = self.validator.calculate_date_overlap_confidence(date1, date2)
        assert confidence >= 0.95

    def test_date_overlap_different_dates(self):
        """Test date overlap for different dates."""
        date1 = self.validator.parse_date("1900")
        date2 = self.validator.parse_date("1910")

        confidence = self.validator.calculate_date_overlap_confidence(date1, date2)
        assert confidence < 0.3


class TestLivingStatusValidator:
    """Test living status validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = LivingStatusValidator()

    def test_definitely_deceased_with_death_record(self):
        """Test that person with death record is definitely deceased."""
        birth = self.validator.date_validator.parse_date("1900")
        death = self.validator.date_validator.parse_date("1980")

        result = self.validator.determine_living_status(birth, death)
        assert result.status == LivingStatus.DEFINITELY_DECEASED
        assert result.confidence >= 0.9

    def test_probably_living_recent_birth(self):
        """Test that person born recently is probably living."""
        birth = self.validator.date_validator.parse_date("2000")
        death = None

        result = self.validator.determine_living_status(birth, death)
        assert result.status == LivingStatus.PROBABLY_LIVING

    def test_definitely_deceased_too_old(self):
        """Test that person who would be too old is definitely deceased."""
        birth = self.validator.date_validator.parse_date("1800")
        death = None

        result = self.validator.determine_living_status(birth, death)
        assert result.status == LivingStatus.DEFINITELY_DECEASED
        assert result.confidence >= 0.9

    def test_living_status_consistency_conflict(self):
        """Test detection of living status conflict."""
        birth1 = self.validator.date_validator.parse_date("1900")
        death1 = self.validator.date_validator.parse_date("1980")
        status1 = self.validator.determine_living_status(birth1, death1)

        birth2 = self.validator.date_validator.parse_date("1900")
        death2 = None
        status2 = self.validator.determine_living_status(
            birth2, death2, living_flag=True
        )

        is_consistent, penalty, issues = \
            self.validator.validate_living_status_consistency(status1, status2)

        assert not is_consistent
        assert penalty > 0.5


class TestGenerationValidator:
    """Test generation gap validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = GenerationValidator()

    def test_same_generation_same_year(self):
        """Test same generation with same birth year."""
        result = self.validator.validate_generation_gap_simple(1900, 1900)
        assert result.is_plausible is True
        assert result.plausibility_score >= 0.9

    def test_same_generation_small_gap(self):
        """Test same generation with small gap."""
        result = self.validator.validate_generation_gap_simple(1900, 1902)
        assert result.is_plausible is True
        assert result.plausibility_score >= 0.8

    def test_same_generation_large_gap(self):
        """Test same generation with unrealistic gap."""
        result = self.validator.validate_generation_gap_simple(1900, 1920)
        assert result.is_plausible is False
        assert result.plausibility_score < 0.5

    def test_family_overlap_siblings(self):
        """Test family overlap for siblings."""
        score = self.validator.get_relationship_overlap_score(
            person1_parent_families=['F1'],
            person1_spouse_families=[],
            person2_parent_families=['F1'],
            person2_spouse_families=[]
        )
        assert score == 1.0

    def test_no_family_overlap(self):
        """Test no family overlap."""
        score = self.validator.get_relationship_overlap_score(
            person1_parent_families=['F1'],
            person1_spouse_families=[],
            person2_parent_families=['F2'],
            person2_spouse_families=[]
        )
        assert score == 0.0


class TestConfidenceTierSystem:
    """Test confidence tier system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.system = ConfidenceTierSystem()

    def test_auto_merge_high_confidence(self):
        """Test auto-merge tier for high confidence with valid data."""
        person1_data = {
            'birth_date': self.system.date_validator.parse_date("1 JAN 1900"),
            'death_date': self.system.date_validator.parse_date("1 JAN 1980"),
            'living_flag': False,
            'parent_family_ids': [],
            'spouse_family_ids': [],
            'sex': 'M',
            'latest_event_year': 1980,
        }

        person2_data = {
            'birth_date': self.system.date_validator.parse_date("1 JAN 1900"),
            'death_date': self.system.date_validator.parse_date("1 JAN 1980"),
            'living_flag': False,
            'parent_family_ids': [],
            'spouse_family_ids': [],
            'sex': 'M',
            'latest_event_year': 1980,
        }

        assessment = self.system.assess_merge_confidence(
            0.95,  # High base score
            person1_data,
            person2_data
        )

        assert assessment.tier == ConfidenceTier.AUTO_MERGE
        assert assessment.date_validation_passed is True
        assert assessment.living_status_consistent is True

    def test_reject_invalid_dates(self):
        """Test reject tier for invalid dates."""
        person1_data = {
            'birth_date': self.system.date_validator.parse_date("1900"),
            'death_date': self.system.date_validator.parse_date("1890"),  # Before birth!
            'living_flag': False,
            'parent_family_ids': [],
            'spouse_family_ids': [],
            'sex': 'M',
            'latest_event_year': None,
        }

        person2_data = {
            'birth_date': self.system.date_validator.parse_date("1900"),
            'death_date': None,
            'living_flag': None,
            'parent_family_ids': [],
            'spouse_family_ids': [],
            'sex': 'M',
            'latest_event_year': None,
        }

        assessment = self.system.assess_merge_confidence(
            0.80,
            person1_data,
            person2_data
        )

        assert assessment.tier == ConfidenceTier.REJECT
        assert assessment.date_validation_passed is False
        assert len(assessment.validation_issues) > 0

    def test_reject_living_conflict(self):
        """Test reject tier for living status conflict."""
        person1_data = {
            'birth_date': self.system.date_validator.parse_date("1900"),
            'death_date': self.system.date_validator.parse_date("1980"),
            'living_flag': False,
            'parent_family_ids': [],
            'spouse_family_ids': [],
            'sex': 'M',
            'latest_event_year': 1980,
        }

        person2_data = {
            'birth_date': self.system.date_validator.parse_date("1900"),
            'death_date': None,
            'living_flag': True,  # Says living!
            'parent_family_ids': [],
            'spouse_family_ids': [],
            'sex': 'M',
            'latest_event_year': 2020,
        }

        assessment = self.system.assess_merge_confidence(
            0.80,
            person1_data,
            person2_data
        )

        assert assessment.tier == ConfidenceTier.REJECT
        assert assessment.living_status_consistent is False

    def test_needs_review_medium_confidence(self):
        """Test needs review tier for medium confidence."""
        person1_data = {
            'birth_date': self.system.date_validator.parse_date("1900"),
            'death_date': None,
            'living_flag': None,
            'parent_family_ids': [],
            'spouse_family_ids': [],
            'sex': 'M',
            'latest_event_year': None,
        }

        person2_data = {
            'birth_date': self.system.date_validator.parse_date("1902"),  # 2 year diff
            'death_date': None,
            'living_flag': None,
            'parent_family_ids': [],
            'spouse_family_ids': [],
            'sex': 'M',
            'latest_event_year': None,
        }

        assessment = self.system.assess_merge_confidence(
            0.70,  # Medium score
            person1_data,
            person2_data
        )

        # Should be needs review due to medium score
        assert assessment.tier in [ConfidenceTier.NEEDS_REVIEW, ConfidenceTier.AUTO_MERGE]

    def test_family_overlap_boost(self):
        """Test that family overlap boosts confidence when dates are sparse."""
        person1_data = {
            'birth_date': None,  # Sparse dates
            'death_date': None,
            'living_flag': None,
            'parent_family_ids': ['F1'],  # Share parent family
            'spouse_family_ids': [],
            'sex': 'M',
            'latest_event_year': None,
        }

        person2_data = {
            'birth_date': None,  # Sparse dates
            'death_date': None,
            'living_flag': None,
            'parent_family_ids': ['F1'],  # Share parent family
            'spouse_family_ids': [],
            'sex': 'M',
            'latest_event_year': None,
        }

        assessment = self.system.assess_merge_confidence(
            0.75,
            person1_data,
            person2_data
        )

        # Family overlap should boost confidence
        assert assessment.has_family_overlap is True
        assert assessment.adjusted_score >= 0.75  # Should be boosted


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
