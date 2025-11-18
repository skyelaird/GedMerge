"""
Genealogical rules and constants for validation.

These constants define biologically and historically plausible limits
for genealogical data validation.
"""

from dataclasses import dataclass
from enum import Enum


# Age limits for childbearing
MIN_PARENT_AGE = 12  # Absolute biological minimum (extremely rare, but documented)
TYPICAL_MIN_PARENT_AGE = 15  # More typical minimum
MAX_PARENT_AGE_MALE = 100  # Maximum age for father (rare but possible)
MAX_PARENT_AGE_FEMALE = 55  # Maximum age for mother (rare beyond this)
TYPICAL_MAX_PARENT_AGE_FEMALE = 45  # More typical maximum

# Generation gap limits
TYPICAL_GENERATION_YEARS = 25  # Average years between generations
MIN_GENERATION_GAP = 12  # Minimum years between parent and child birth
MAX_GENERATION_GAP = 80  # Maximum plausible years between parent and child
EXTREME_GENERATION_GAP = 100  # Absolute impossible threshold

# Lifespan limits
MAX_LIFESPAN = 110  # Maximum reasonable lifespan
TYPICAL_MAX_LIFESPAN = 100  # More typical maximum
MIN_LIFESPAN_FOR_WARNING = 0  # Died at birth
MAX_LIFESPAN_FOR_WARNING = 105  # Flag for review if older

# Marriage limits
MIN_MARRIAGE_AGE = 12  # Historical minimum (child marriages in some cultures)
TYPICAL_MIN_MARRIAGE_AGE = 16  # More typical minimum
MAX_MARRIAGE_AGE_DIFFERENCE = 50  # Unusual if spouses differ by more than this

# Living person detection
LIVING_THRESHOLD_BIRTH_YEAR = 1900  # If born after this and no death, likely living
CURRENT_YEAR = 2025  # Update this periodically
MAX_AGE_WITHOUT_DEATH_RECORD = 110  # Assume deceased if would be older than this

# Historical date limits
MIN_REASONABLE_YEAR = 1500  # Most genealogies don't go back further
MAX_REASONABLE_YEAR = CURRENT_YEAR  # Can't be born in the future

# Date confidence thresholds
class DateQuality(Enum):
    """Quality of date information available."""
    EXACT = "exact"  # Full date (DD MMM YYYY)
    YEAR_ONLY = "year_only"  # Year only
    ESTIMATED = "estimated"  # ABT, EST, CAL
    RANGE = "range"  # BET, AFT, BEF
    UNKNOWN = "unknown"  # No date


@dataclass(slots=True)
class AgeAtEvent:
    """Age of person at a specific event."""
    years: int
    event_type: str  # 'birth', 'death', 'marriage', 'parent_birth'
    is_estimated: bool = False

    def is_plausible(self) -> bool:
        """Check if the age is plausible for this event type."""
        if self.event_type == 'death':
            return 0 <= self.years <= MAX_LIFESPAN
        elif self.event_type == 'marriage':
            return MIN_MARRIAGE_AGE <= self.years <= MAX_LIFESPAN
        elif self.event_type == 'parent_birth':
            return MIN_PARENT_AGE <= self.years <= MAX_PARENT_AGE_MALE
        return True

    def get_plausibility_score(self) -> float:
        """
        Return a score 0.0-1.0 indicating how plausible this age is.
        1.0 = typical, 0.5 = unusual but possible, 0.0 = impossible
        """
        if not self.is_plausible():
            return 0.0

        if self.event_type == 'death':
            if self.years <= 0:
                return 0.1  # Stillbirth/infant death
            elif self.years <= 5:
                return 0.5  # Child death (sadly common historically)
            elif self.years <= 18:
                return 0.7  # Youth death
            elif 18 < self.years <= TYPICAL_MAX_LIFESPAN:
                return 1.0  # Normal lifespan
            elif TYPICAL_MAX_LIFESPAN < self.years <= MAX_LIFESPAN:
                return 0.6  # Very old but possible
            else:
                return 0.0  # Impossible

        elif self.event_type == 'marriage':
            if MIN_MARRIAGE_AGE <= self.years < TYPICAL_MIN_MARRIAGE_AGE:
                return 0.5  # Child marriage (historical)
            elif TYPICAL_MIN_MARRIAGE_AGE <= self.years <= 40:
                return 1.0  # Normal marriage age
            elif 40 < self.years <= 60:
                return 0.8  # Later marriage
            elif 60 < self.years:
                return 0.6  # Late marriage or remarriage

        elif self.event_type == 'parent_birth':
            # Age when child was born
            if self.years < MIN_PARENT_AGE:
                return 0.0  # Biologically impossible
            elif MIN_PARENT_AGE <= self.years < TYPICAL_MIN_PARENT_AGE:
                return 0.3  # Extremely young parent
            elif TYPICAL_MIN_PARENT_AGE <= self.years <= 35:
                return 1.0  # Typical childbearing age
            elif 35 < self.years <= 45:
                return 0.9  # Older parent
            elif 45 < self.years <= TYPICAL_MAX_PARENT_AGE_FEMALE:
                return 0.5  # Late parent (more common for fathers)
            elif TYPICAL_MAX_PARENT_AGE_FEMALE < self.years <= MAX_PARENT_AGE_MALE:
                return 0.3  # Very late father (extremely rare for mothers)
            else:
                return 0.0  # Biologically impossible

        return 1.0


def calculate_generation_gap_plausibility(birth_year_diff: int, generation_distance: int) -> float:
    """
    Calculate how plausible a birth year difference is for a given generation gap.

    Args:
        birth_year_diff: Difference in birth years (absolute value)
        generation_distance: Number of generations apart (1=parent/child, 2=grandparent/grandchild)

    Returns:
        Plausibility score 0.0-1.0
    """
    if generation_distance == 0:
        # Same generation (siblings, cousins)
        if birth_year_diff <= 20:
            return 1.0
        elif birth_year_diff <= 30:
            return 0.8  # Possible but unusual
        elif birth_year_diff <= 40:
            return 0.5  # Rare (e.g., half-siblings from very late remarriage)
        else:
            return 0.2  # Highly suspicious

    elif generation_distance == 1:
        # Parent/child relationship
        expected_min = MIN_GENERATION_GAP
        expected_max = MAX_GENERATION_GAP
        typical_range = (TYPICAL_MIN_PARENT_AGE, TYPICAL_MAX_PARENT_AGE_FEMALE)

        if birth_year_diff < expected_min:
            return 0.0  # Impossible
        elif birth_year_diff < typical_range[0]:
            return 0.4  # Very young parent
        elif typical_range[0] <= birth_year_diff <= typical_range[1]:
            return 1.0  # Normal
        elif typical_range[1] < birth_year_diff <= expected_max:
            return 0.6  # Older parent (more common for fathers)
        elif expected_max < birth_year_diff < EXTREME_GENERATION_GAP:
            return 0.2  # Extremely rare
        else:
            return 0.0  # Impossible

    elif generation_distance == 2:
        # Grandparent/grandchild relationship
        expected_min = MIN_GENERATION_GAP * 2
        expected_max = MAX_GENERATION_GAP * 2

        if birth_year_diff < expected_min:
            return 0.0
        elif birth_year_diff < 30:
            return 0.3  # Very young grandparent
        elif 30 <= birth_year_diff <= 70:
            return 1.0  # Normal
        elif 70 < birth_year_diff <= expected_max:
            return 0.5  # Older grandparent
        else:
            return 0.0  # Impossible

    else:
        # More distant relationships
        expected_min = MIN_GENERATION_GAP * generation_distance
        expected_max = MAX_GENERATION_GAP * generation_distance

        if expected_min <= birth_year_diff <= expected_max:
            return 0.8  # Plausible
        elif birth_year_diff < expected_min:
            return 0.0  # Too close
        elif birth_year_diff < EXTREME_GENERATION_GAP * generation_distance:
            return 0.3  # Possible but unlikely
        else:
            return 0.0  # Impossible


def get_expected_year_range_for_relationship(
    anchor_birth_year: int,
    relationship: str
) -> tuple[int, int]:
    """
    Get expected birth year range for a person based on relationship to anchor person.

    Args:
        anchor_birth_year: Birth year of the known person
        relationship: Type of relationship ('parent', 'child', 'spouse', 'sibling')

    Returns:
        Tuple of (min_year, max_year) for plausible birth years
    """
    if relationship == 'parent':
        return (
            anchor_birth_year - MAX_GENERATION_GAP,
            anchor_birth_year - MIN_GENERATION_GAP
        )
    elif relationship == 'child':
        return (
            anchor_birth_year + MIN_GENERATION_GAP,
            anchor_birth_year + MAX_GENERATION_GAP
        )
    elif relationship == 'spouse':
        return (
            anchor_birth_year - MAX_MARRIAGE_AGE_DIFFERENCE,
            anchor_birth_year + MAX_MARRIAGE_AGE_DIFFERENCE
        )
    elif relationship == 'sibling':
        return (
            anchor_birth_year - 30,  # Half-siblings from early/late marriages
            anchor_birth_year + 30
        )
    else:
        # Unknown relationship - very wide range
        return (
            anchor_birth_year - 100,
            anchor_birth_year + 100
        )
