"""
Date validation for genealogical data.

Provides validation for impossible date scenarios, date quality assessment,
and genealogically plausible date ranges.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple
from enum import Enum

from .genealogical_rules import (
    MIN_REASONABLE_YEAR,
    MAX_REASONABLE_YEAR,
    MAX_LIFESPAN,
    MIN_PARENT_AGE,
    MAX_PARENT_AGE_MALE,
    MAX_PARENT_AGE_FEMALE,
    MIN_MARRIAGE_AGE,
    DateQuality,
    AgeAtEvent,
    CURRENT_YEAR,
)


class DateValidationResult(Enum):
    """Result of date validation."""
    VALID = "valid"
    WARNING = "warning"  # Unusual but possible
    INVALID = "invalid"  # Impossible


@dataclass(slots=True)
class ParsedDate:
    """Parsed genealogical date with quality information."""
    original: str
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    is_estimated: bool = False
    is_range: bool = False
    is_before: bool = False
    is_after: bool = False
    range_start_year: Optional[int] = None
    range_end_year: Optional[int] = None
    quality: DateQuality = DateQuality.UNKNOWN

    def get_best_year(self) -> Optional[int]:
        """Get the best estimate of the year."""
        if self.year:
            return self.year
        if self.range_start_year and self.range_end_year:
            return (self.range_start_year + self.range_end_year) // 2
        if self.range_start_year:
            return self.range_start_year
        if self.range_end_year:
            return self.range_end_year
        return None

    def get_year_range(self) -> Tuple[Optional[int], Optional[int]]:
        """Get the possible year range for this date."""
        if self.is_before and self.year:
            return (MIN_REASONABLE_YEAR, self.year)
        elif self.is_after and self.year:
            return (self.year, MAX_REASONABLE_YEAR)
        elif self.is_range:
            return (self.range_start_year, self.range_end_year)
        elif self.year:
            return (self.year, self.year)
        return (None, None)


class DateValidator:
    """Validates dates and date combinations for genealogical plausibility."""

    # GEDCOM date prefixes and modifiers
    DATE_MODIFIERS = {
        'ABT': 'estimated',  # About
        'EST': 'estimated',  # Estimated
        'CAL': 'estimated',  # Calculated
        'BEF': 'before',     # Before
        'AFT': 'after',      # After
        'BET': 'range',      # Between (followed by date AND date)
    }

    MONTHS = {
        'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
        'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12
    }

    def __init__(self):
        """Initialize the date validator."""
        pass

    def parse_date(self, date_str: Optional[str]) -> Optional[ParsedDate]:
        """
        Parse a GEDCOM date string into a structured format.

        Supports formats:
        - "1 JAN 1900" (exact)
        - "JAN 1900" (month and year)
        - "1900" (year only)
        - "ABT 1900" (estimated)
        - "BEF 1900" (before)
        - "AFT 1900" (after)
        - "BET 1900 AND 1905" (range)

        Args:
            date_str: GEDCOM date string

        Returns:
            ParsedDate object or None if unparseable
        """
        if not date_str or not date_str.strip():
            return None

        date_str = date_str.strip().upper()
        parsed = ParsedDate(original=date_str)

        # Check for modifiers
        modifier = None
        for mod, mod_type in self.DATE_MODIFIERS.items():
            if date_str.startswith(mod):
                modifier = mod_type
                date_str = date_str[len(mod):].strip()
                break

        # Handle BET ... AND ... format
        if modifier == 'range':
            and_match = re.search(r'\bAND\b', date_str)
            if and_match:
                start_str = date_str[:and_match.start()].strip()
                end_str = date_str[and_match.end():].strip()
                start_year = self._extract_year(start_str)
                end_year = self._extract_year(end_str)
                if start_year and end_year:
                    parsed.is_range = True
                    parsed.range_start_year = start_year
                    parsed.range_end_year = end_year
                    parsed.year = (start_year + end_year) // 2
                    parsed.quality = DateQuality.RANGE
                    return parsed

        # Parse the date components
        year = self._extract_year(date_str)
        month = self._extract_month(date_str)
        day = self._extract_day(date_str)

        if year:
            parsed.year = year
            parsed.month = month
            parsed.day = day

            # Set quality
            if day and month:
                parsed.quality = DateQuality.EXACT
            elif month:
                parsed.quality = DateQuality.YEAR_ONLY  # We have year and month
            else:
                parsed.quality = DateQuality.YEAR_ONLY

            # Apply modifiers
            if modifier == 'estimated':
                parsed.is_estimated = True
                parsed.quality = DateQuality.ESTIMATED
            elif modifier == 'before':
                parsed.is_before = True
                parsed.quality = DateQuality.RANGE
            elif modifier == 'after':
                parsed.is_after = True
                parsed.quality = DateQuality.RANGE

            return parsed

        return None

    def _extract_year(self, date_str: str) -> Optional[int]:
        """Extract a 4-digit year from a date string."""
        match = re.search(r'\b(\d{4})\b', date_str)
        if match:
            year = int(match.group(1))
            # Basic sanity check
            if MIN_REASONABLE_YEAR <= year <= MAX_REASONABLE_YEAR + 10:
                return year
        return None

    def _extract_month(self, date_str: str) -> Optional[int]:
        """Extract month from a date string."""
        for month_name, month_num in self.MONTHS.items():
            if month_name in date_str:
                return month_num
        return None

    def _extract_day(self, date_str: str) -> Optional[int]:
        """Extract day from a date string."""
        # Look for 1-2 digit day before month
        match = re.search(r'\b(\d{1,2})\s+[A-Z]{3}\b', date_str)
        if match:
            day = int(match.group(1))
            if 1 <= day <= 31:
                return day
        return None

    def validate_birth_after_death(
        self,
        birth_date: Optional[ParsedDate],
        death_date: Optional[ParsedDate]
    ) -> Tuple[bool, str]:
        """
        Check if birth date is after death date (data entry error).

        This is a specific check for the common data entry error where
        birth and death dates are swapped or incorrectly entered.

        Args:
            birth_date: Person's birth date
            death_date: Person's death date

        Returns:
            Tuple of (is_error, error_message)
        """
        if not birth_date or not death_date:
            return False, ''

        birth_year = birth_date.get_best_year()
        death_year = death_date.get_best_year()

        if not birth_year or not death_year:
            return False, ''

        if birth_year > death_year:
            return True, f"SUSPICIOUS: Birth year ({birth_year}) is after death year ({death_year})"
        elif birth_year == death_year:
            # Check if we have more specific dates
            if birth_date.month and death_date.month:
                if birth_date.month > death_date.month:
                    return True, f"SUSPICIOUS: Birth month ({birth_date.month}) is after death month ({death_date.month}) in year {birth_year}"
                elif birth_date.month == death_date.month and birth_date.day and death_date.day:
                    if birth_date.day > death_date.day:
                        return True, f"SUSPICIOUS: Birth day is after death day in same month/year"

        return False, ''

    def validate_date_range(
        self,
        birth_date: Optional[ParsedDate],
        death_date: Optional[ParsedDate]
    ) -> Tuple[DateValidationResult, List[str]]:
        """
        Validate that birth and death dates are plausible.

        This checks for:
        - Birth after death (INVALID)
        - Excessive lifespan (INVALID or WARNING)

        Returns:
            Tuple of (validation_result, list of issues)
        """
        issues = []

        if not birth_date or not death_date:
            return DateValidationResult.VALID, issues

        birth_year = birth_date.get_best_year()
        death_year = death_date.get_best_year()

        if not birth_year or not death_year:
            return DateValidationResult.VALID, issues

        # Check for birth after death (data entry error)
        is_error, error_msg = self.validate_birth_after_death(birth_date, death_date)
        if is_error:
            issues.append(error_msg)
            return DateValidationResult.INVALID, issues

        # Check lifespan
        lifespan = death_year - birth_year
        if lifespan > MAX_LIFESPAN:
            issues.append(f"Lifespan of {lifespan} years exceeds maximum of {MAX_LIFESPAN}")
            return DateValidationResult.INVALID, issues
        elif lifespan > 105:
            issues.append(f"Lifespan of {lifespan} years is unusually long")
            return DateValidationResult.WARNING, issues

        return DateValidationResult.VALID, issues

    def validate_parent_child_dates(
        self,
        parent_birth_date: Optional[ParsedDate],
        child_birth_date: Optional[ParsedDate],
        parent_sex: Optional[str] = None
    ) -> Tuple[DateValidationResult, List[str]]:
        """
        Validate that parent and child birth dates are plausible.

        Args:
            parent_birth_date: Parent's birth date
            child_birth_date: Child's birth date
            parent_sex: 'M' or 'F' for more specific validation

        Returns:
            Tuple of (validation_result, list of issues)
        """
        issues = []

        if not parent_birth_date or not child_birth_date:
            return DateValidationResult.VALID, issues

        parent_year = parent_birth_date.get_best_year()
        child_year = child_birth_date.get_best_year()

        if not parent_year or not child_year:
            return DateValidationResult.VALID, issues

        age_at_child_birth = child_year - parent_year

        # Child must be born after parent
        if age_at_child_birth < MIN_PARENT_AGE:
            issues.append(
                f"Parent age at child's birth ({age_at_child_birth}) is below minimum ({MIN_PARENT_AGE})"
            )
            return DateValidationResult.INVALID, issues

        # Check maximum age
        max_age = MAX_PARENT_AGE_FEMALE if parent_sex == 'F' else MAX_PARENT_AGE_MALE
        if age_at_child_birth > max_age:
            issues.append(
                f"Parent age at child's birth ({age_at_child_birth}) exceeds maximum ({max_age})"
            )
            return DateValidationResult.INVALID, issues

        # Warnings for unusual ages
        if age_at_child_birth < 15:
            issues.append(f"Parent age at child's birth ({age_at_child_birth}) is unusually young")
            return DateValidationResult.WARNING, issues
        elif parent_sex == 'F' and age_at_child_birth > 45:
            issues.append(f"Mother age at child's birth ({age_at_child_birth}) is unusually old")
            return DateValidationResult.WARNING, issues
        elif age_at_child_birth > 70:
            issues.append(f"Parent age at child's birth ({age_at_child_birth}) is unusually old")
            return DateValidationResult.WARNING, issues

        return DateValidationResult.VALID, issues

    def validate_marriage_date(
        self,
        person_birth_date: Optional[ParsedDate],
        marriage_date: Optional[ParsedDate]
    ) -> Tuple[DateValidationResult, List[str]]:
        """
        Validate that marriage date is plausible given birth date.

        Returns:
            Tuple of (validation_result, list of issues)
        """
        issues = []

        if not person_birth_date or not marriage_date:
            return DateValidationResult.VALID, issues

        birth_year = person_birth_date.get_best_year()
        marriage_year = marriage_date.get_best_year()

        if not birth_year or not marriage_year:
            return DateValidationResult.VALID, issues

        age_at_marriage = marriage_year - birth_year

        if age_at_marriage < MIN_MARRIAGE_AGE:
            issues.append(f"Age at marriage ({age_at_marriage}) is below minimum ({MIN_MARRIAGE_AGE})")
            return DateValidationResult.INVALID, issues

        if age_at_marriage < 16:
            issues.append(f"Age at marriage ({age_at_marriage}) is unusually young")
            return DateValidationResult.WARNING, issues
        elif age_at_marriage > 80:
            issues.append(f"Age at marriage ({age_at_marriage}) is unusually old")
            return DateValidationResult.WARNING, issues

        return DateValidationResult.VALID, issues

    def validate_year_in_range(self, year: Optional[int]) -> Tuple[DateValidationResult, List[str]]:
        """
        Validate that a year is in a reasonable range.

        Returns:
            Tuple of (validation_result, list of issues)
        """
        issues = []

        if not year:
            return DateValidationResult.VALID, issues

        if year < MIN_REASONABLE_YEAR:
            issues.append(f"Year {year} is before reasonable range ({MIN_REASONABLE_YEAR})")
            return DateValidationResult.INVALID, issues

        if year > MAX_REASONABLE_YEAR:
            issues.append(f"Year {year} is in the future (>{MAX_REASONABLE_YEAR})")
            return DateValidationResult.INVALID, issues

        return DateValidationResult.VALID, issues

    def calculate_date_overlap_confidence(
        self,
        date1: Optional[ParsedDate],
        date2: Optional[ParsedDate]
    ) -> float:
        """
        Calculate confidence that two dates refer to the same event.

        Returns:
            Confidence score 0.0-1.0
        """
        if not date1 or not date2:
            return 0.5  # Unknown

        year1 = date1.get_best_year()
        year2 = date2.get_best_year()

        if not year1 or not year2:
            return 0.5  # Unknown

        year_diff = abs(year1 - year2)

        # Exact match
        if year_diff == 0:
            # Check for more specific matches
            if date1.day and date2.day and date1.month and date2.month:
                if date1.day == date2.day and date1.month == date2.month:
                    return 1.0  # Exact date match
                else:
                    return 0.1  # Same year but different dates - likely different events

            if date1.month and date2.month:
                if date1.month == date2.month:
                    return 0.9  # Same month and year
                else:
                    return 0.6  # Same year, different months

            # Both quality matters
            if date1.quality == DateQuality.EXACT and date2.quality == DateQuality.EXACT:
                return 0.95
            elif date1.is_estimated or date2.is_estimated:
                return 0.8
            else:
                return 0.85

        # Close years
        elif year_diff == 1:
            # Could be estimation error or recording error
            if date1.is_estimated or date2.is_estimated:
                return 0.7
            else:
                return 0.4

        elif year_diff <= 3:
            if date1.is_estimated or date2.is_estimated:
                return 0.5
            else:
                return 0.2

        elif year_diff <= 5:
            if date1.is_estimated and date2.is_estimated:
                return 0.3  # Both estimated, might be same
            else:
                return 0.1

        else:
            return 0.0  # Too far apart

    def get_date_quality_multiplier(self, date: Optional[ParsedDate]) -> float:
        """
        Get a quality multiplier for scoring based on date quality.

        Returns:
            Multiplier 0.5-1.0 (lower quality = lower multiplier)
        """
        if not date:
            return 0.5

        quality_scores = {
            DateQuality.EXACT: 1.0,
            DateQuality.YEAR_ONLY: 0.9,
            DateQuality.ESTIMATED: 0.7,
            DateQuality.RANGE: 0.6,
            DateQuality.UNKNOWN: 0.5,
        }

        return quality_scores.get(date.quality, 0.5)
