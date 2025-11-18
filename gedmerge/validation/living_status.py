"""
Living status validation for genealogical data.

Determines if a person is likely living and validates consistency
between records being merged.
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum

from .genealogical_rules import (
    MAX_AGE_WITHOUT_DEATH_RECORD,
    LIVING_THRESHOLD_BIRTH_YEAR,
    CURRENT_YEAR,
)
from .date_validator import ParsedDate, DateValidator


class LivingStatus(Enum):
    """Living status determination."""
    DEFINITELY_LIVING = "definitely_living"
    PROBABLY_LIVING = "probably_living"
    UNKNOWN = "unknown"
    PROBABLY_DECEASED = "probably_deceased"
    DEFINITELY_DECEASED = "definitely_deceased"


@dataclass(slots=True)
class LivingStatusResult:
    """Result of living status determination."""
    status: LivingStatus
    confidence: float  # 0.0-1.0
    reasons: List[str]
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    estimated_age: Optional[int] = None
    has_death_event: bool = False
    living_flag: Optional[bool] = None  # From database


class LivingStatusValidator:
    """Validates and determines living status of individuals."""

    def __init__(self):
        """Initialize the living status validator."""
        self.date_validator = DateValidator()

    def determine_living_status(
        self,
        birth_date: Optional[ParsedDate],
        death_date: Optional[ParsedDate],
        living_flag: Optional[bool] = None,
        latest_event_year: Optional[int] = None
    ) -> LivingStatusResult:
        """
        Determine if a person is likely living.

        Args:
            birth_date: Parsed birth date
            death_date: Parsed death date
            living_flag: Living flag from database (if available)
            latest_event_year: Year of most recent event (marriage, child birth, etc.)

        Returns:
            LivingStatusResult with determination and confidence
        """
        reasons = []
        birth_year = birth_date.get_best_year() if birth_date else None
        death_year = death_date.get_best_year() if death_date else None
        has_death_event = death_date is not None

        # Calculate estimated current age if we have birth year
        estimated_age = None
        if birth_year:
            estimated_age = CURRENT_YEAR - birth_year

        # Definite cases
        if has_death_event and death_year:
            reasons.append(f"Has death record from {death_year}")
            return LivingStatusResult(
                status=LivingStatus.DEFINITELY_DECEASED,
                confidence=1.0,
                reasons=reasons,
                birth_year=birth_year,
                death_year=death_year,
                estimated_age=estimated_age,
                has_death_event=True,
                living_flag=living_flag
            )

        # Check living flag from database
        if living_flag is True:
            reasons.append("Database living flag is set to True")
            confidence = 0.9  # High but not absolute
            status = LivingStatus.PROBABLY_LIVING

            # Verify it makes sense
            if estimated_age and estimated_age > MAX_AGE_WITHOUT_DEATH_RECORD:
                reasons.append(
                    f"Age would be {estimated_age}, exceeds maximum ({MAX_AGE_WITHOUT_DEATH_RECORD})"
                )
                status = LivingStatus.DEFINITELY_DECEASED
                confidence = 0.95
                return LivingStatusResult(
                    status=status,
                    confidence=confidence,
                    reasons=reasons,
                    birth_year=birth_year,
                    death_year=death_year,
                    estimated_age=estimated_age,
                    has_death_event=False,
                    living_flag=living_flag
                )

            return LivingStatusResult(
                status=status,
                confidence=confidence,
                reasons=reasons,
                birth_year=birth_year,
                death_year=death_year,
                estimated_age=estimated_age,
                has_death_event=False,
                living_flag=living_flag
            )

        elif living_flag is False:
            reasons.append("Database living flag is set to False")
            return LivingStatusResult(
                status=LivingStatus.DEFINITELY_DECEASED,
                confidence=0.95,
                reasons=reasons,
                birth_year=birth_year,
                death_year=death_year,
                estimated_age=estimated_age,
                has_death_event=False,
                living_flag=living_flag
            )

        # No death record and no living flag - use heuristics
        if not birth_year:
            reasons.append("No birth year available")
            return LivingStatusResult(
                status=LivingStatus.UNKNOWN,
                confidence=0.5,
                reasons=reasons,
                birth_year=birth_year,
                death_year=death_year,
                estimated_age=estimated_age,
                has_death_event=False,
                living_flag=living_flag
            )

        # Use age-based heuristics
        if estimated_age is not None:
            if estimated_age > MAX_AGE_WITHOUT_DEATH_RECORD:
                reasons.append(
                    f"Age would be {estimated_age}, exceeds maximum ({MAX_AGE_WITHOUT_DEATH_RECORD})"
                )
                return LivingStatusResult(
                    status=LivingStatus.DEFINITELY_DECEASED,
                    confidence=0.99,
                    reasons=reasons,
                    birth_year=birth_year,
                    death_year=death_year,
                    estimated_age=estimated_age,
                    has_death_event=False,
                    living_flag=living_flag
                )

            elif estimated_age >= 100:
                reasons.append(f"Age would be {estimated_age}, likely deceased")
                return LivingStatusResult(
                    status=LivingStatus.PROBABLY_DECEASED,
                    confidence=0.9,
                    reasons=reasons,
                    birth_year=birth_year,
                    death_year=death_year,
                    estimated_age=estimated_age,
                    has_death_event=False,
                    living_flag=living_flag
                )

            elif estimated_age >= 90:
                reasons.append(f"Age would be {estimated_age}, probably deceased")
                confidence = 0.7
                status = LivingStatus.PROBABLY_DECEASED

                # Check if we have recent events
                if latest_event_year and latest_event_year >= CURRENT_YEAR - 10:
                    reasons.append(f"Recent event in {latest_event_year}, possibly living")
                    status = LivingStatus.PROBABLY_LIVING
                    confidence = 0.6

                return LivingStatusResult(
                    status=status,
                    confidence=confidence,
                    reasons=reasons,
                    birth_year=birth_year,
                    death_year=death_year,
                    estimated_age=estimated_age,
                    has_death_event=False,
                    living_flag=living_flag
                )

            elif estimated_age >= 0 and estimated_age < 90:
                if birth_year >= LIVING_THRESHOLD_BIRTH_YEAR:
                    reasons.append(
                        f"Born {birth_year}, age would be {estimated_age}, possibly living"
                    )
                    confidence = 0.6 + (0.3 * (90 - estimated_age) / 90)  # Higher confidence for younger
                    return LivingStatusResult(
                        status=LivingStatus.PROBABLY_LIVING,
                        confidence=confidence,
                        reasons=reasons,
                        birth_year=birth_year,
                        death_year=death_year,
                        estimated_age=estimated_age,
                        has_death_event=False,
                        living_flag=living_flag
                    )
                else:
                    reasons.append(f"Born {birth_year}, age would be {estimated_age}")
                    return LivingStatusResult(
                        status=LivingStatus.UNKNOWN,
                        confidence=0.5,
                        reasons=reasons,
                        birth_year=birth_year,
                        death_year=death_year,
                        estimated_age=estimated_age,
                        has_death_event=False,
                        living_flag=living_flag
                    )

            else:  # Negative age - birth in future
                reasons.append(f"Birth year {birth_year} is in the future")
                return LivingStatusResult(
                    status=LivingStatus.UNKNOWN,
                    confidence=0.0,
                    reasons=reasons,
                    birth_year=birth_year,
                    death_year=death_year,
                    estimated_age=estimated_age,
                    has_death_event=False,
                    living_flag=living_flag
                )

        # Default to unknown
        reasons.append("Insufficient information to determine living status")
        return LivingStatusResult(
            status=LivingStatus.UNKNOWN,
            confidence=0.5,
            reasons=reasons,
            birth_year=birth_year,
            death_year=death_year,
            estimated_age=estimated_age,
            has_death_event=False,
            living_flag=living_flag
        )

    def validate_living_status_consistency(
        self,
        status1: LivingStatusResult,
        status2: LivingStatusResult
    ) -> tuple[bool, float, List[str]]:
        """
        Validate that two living status determinations are consistent.

        Args:
            status1: Living status result for first person
            status2: Living status result for second person

        Returns:
            Tuple of (is_consistent, confidence_penalty, issues)
            - is_consistent: True if statuses are compatible
            - confidence_penalty: 0.0-1.0 penalty to apply to match score
            - issues: List of consistency issues found
        """
        issues = []
        confidence_penalty = 0.0

        # Check for direct conflicts
        living_statuses = {LivingStatus.DEFINITELY_LIVING, LivingStatus.PROBABLY_LIVING}
        deceased_statuses = {LivingStatus.DEFINITELY_DECEASED, LivingStatus.PROBABLY_DECEASED}

        status1_living = status1.status in living_statuses
        status2_living = status2.status in living_statuses
        status1_deceased = status1.status in deceased_statuses
        status2_deceased = status2.status in deceased_statuses

        # Definite conflict: one living, one deceased
        if status1_living and status2_deceased:
            issues.append(
                f"Living status conflict: Record 1 appears living, Record 2 appears deceased"
            )
            confidence_penalty = 0.8  # Major penalty
            return False, confidence_penalty, issues

        if status1_deceased and status2_living:
            issues.append(
                f"Living status conflict: Record 1 appears deceased, Record 2 appears living"
            )
            confidence_penalty = 0.8  # Major penalty
            return False, confidence_penalty, issues

        # Check database flags
        if status1.living_flag is not None and status2.living_flag is not None:
            if status1.living_flag != status2.living_flag:
                issues.append(
                    f"Database living flags conflict: {status1.living_flag} vs {status2.living_flag}"
                )
                confidence_penalty = 0.5
                return False, confidence_penalty, issues

        # Check death records
        if status1.has_death_event and status2.has_death_event:
            # Both have death records - check if years are close
            if status1.death_year and status2.death_year:
                year_diff = abs(status1.death_year - status2.death_year)
                if year_diff > 2:
                    issues.append(
                        f"Death years differ significantly: {status1.death_year} vs {status2.death_year}"
                    )
                    confidence_penalty = 0.6
                    return False, confidence_penalty, issues
                elif year_diff == 1:
                    issues.append(
                        f"Death years differ by 1 year: {status1.death_year} vs {status2.death_year}"
                    )
                    confidence_penalty = 0.1  # Minor penalty - could be recording error

        elif status1.has_death_event and not status2.has_death_event:
            # One has death, other doesn't
            if status2_living:
                issues.append("Record 1 has death event, but Record 2 appears living")
                confidence_penalty = 0.7
                return False, confidence_penalty, issues
            else:
                # Record 2 just doesn't have death recorded yet
                issues.append("Record 1 has death event, Record 2 does not")
                confidence_penalty = 0.2  # Minor penalty - incomplete data

        elif status2.has_death_event and not status1.has_death_event:
            # One has death, other doesn't
            if status1_living:
                issues.append("Record 2 has death event, but Record 1 appears living")
                confidence_penalty = 0.7
                return False, confidence_penalty, issues
            else:
                # Record 1 just doesn't have death recorded yet
                issues.append("Record 2 has death event, Record 1 does not")
                confidence_penalty = 0.2  # Minor penalty - incomplete data

        # Check age consistency
        if status1.estimated_age is not None and status2.estimated_age is not None:
            age_diff = abs(status1.estimated_age - status2.estimated_age)
            if age_diff > 5:
                issues.append(
                    f"Estimated ages differ significantly: {status1.estimated_age} vs {status2.estimated_age}"
                )
                confidence_penalty = max(confidence_penalty, 0.3)
            elif age_diff > 2:
                issues.append(
                    f"Estimated ages differ: {status1.estimated_age} vs {status2.estimated_age}"
                )
                confidence_penalty = max(confidence_penalty, 0.1)

        # If we made it here with no major issues, statuses are consistent
        if not issues:
            return True, 0.0, []
        elif confidence_penalty < 0.5:
            return True, confidence_penalty, issues  # Minor inconsistencies
        else:
            return False, confidence_penalty, issues  # Major inconsistencies
