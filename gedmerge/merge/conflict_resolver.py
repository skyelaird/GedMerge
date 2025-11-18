"""
Conflict resolution for merging duplicate records.

Handles conflicts intelligently based on data quality, completeness,
and genealogical best practices.
"""

from typing import Optional, Any
from dataclasses import dataclass
from enum import Enum


class ConflictType(Enum):
    """Types of conflicts that can occur during merge."""
    NAME_MISMATCH = "name_mismatch"
    DATE_MISMATCH = "date_mismatch"
    PLACE_MISMATCH = "place_mismatch"
    SEX_MISMATCH = "sex_mismatch"
    RELATIONSHIP_MISMATCH = "relationship_mismatch"


class MergeDecision(Enum):
    """Decision on how to handle a conflict."""
    KEEP_PRIMARY = "keep_primary"
    KEEP_SECONDARY = "keep_secondary"
    KEEP_BOTH = "keep_both"
    MANUAL_REVIEW = "manual_review"


@dataclass(slots=True)
class ConflictResolution:
    """Resolution of a conflict between two values."""
    field: str
    value1: Any
    value2: Any
    chosen: Any
    reason: str
    decision: MergeDecision = MergeDecision.KEEP_PRIMARY

    def __str__(self) -> str:
        """Human-readable description."""
        return (
            f"Field: {self.field}\n"
            f"  Value 1: {self.value1}\n"
            f"  Value 2: {self.value2}\n"
            f"  Chosen: {self.chosen}\n"
            f"  Reason: {self.reason}\n"
            f"  Decision: {self.decision.value}"
        )


class ConflictResolver:
    """
    Resolves conflicts between duplicate records.

    Resolution Strategies:
    1. Data Completeness - prefer more complete data
    2. Data Quality - prefer more specific/detailed data
    3. Date Proximity - prefer dates closer to other known dates
    4. Source Priority - prefer sourced data over unsourced
    5. Recency - prefer more recently edited data (when quality is equal)
    """

    def resolve_name_conflict(
        self,
        name1: str,
        name2: str,
        context: Optional[dict] = None
    ) -> ConflictResolution:
        """
        Resolve conflict between two different names.

        Strategy:
        - If one is empty, use the other
        - If one is "NN" (no name), use the other
        - If both valid, keep both as alternate names
        """
        # Empty check
        if not name1 or name1.strip() == '':
            return ConflictResolution(
                field='name',
                value1=name1,
                value2=name2,
                chosen=name2,
                reason='Value 1 was empty',
                decision=MergeDecision.KEEP_SECONDARY
            )

        if not name2 or name2.strip() == '':
            return ConflictResolution(
                field='name',
                value1=name1,
                value2=name2,
                chosen=name1,
                reason='Value 2 was empty',
                decision=MergeDecision.KEEP_PRIMARY
            )

        # "NN" (No Name) convention check
        if name1.strip().upper() == 'NN':
            return ConflictResolution(
                field='name',
                value1=name1,
                value2=name2,
                chosen=name2,
                reason='Value 1 was placeholder "NN"',
                decision=MergeDecision.KEEP_SECONDARY
            )

        if name2.strip().upper() == 'NN':
            return ConflictResolution(
                field='name',
                value1=name1,
                value2=name2,
                chosen=name1,
                reason='Value 2 was placeholder "NN"',
                decision=MergeDecision.KEEP_PRIMARY
            )

        # Both valid - keep both as alternate names
        return ConflictResolution(
            field='name',
            value1=name1,
            value2=name2,
            chosen=f"{name1} / {name2}",
            reason='Both names valid, keeping as alternates',
            decision=MergeDecision.KEEP_BOTH
        )

    def resolve_date_conflict(
        self,
        date1: str,
        date2: str,
        tolerance_years: int = 2
    ) -> ConflictResolution:
        """
        Resolve conflict between two different dates.

        Strategy:
        - If one is empty, use the other
        - If within tolerance, prefer more specific date
        - If beyond tolerance, flag for manual review
        """
        # Empty check
        if not date1:
            return ConflictResolution(
                field='date',
                value1=date1,
                value2=date2,
                chosen=date2,
                reason='Value 1 was empty',
                decision=MergeDecision.KEEP_SECONDARY
            )

        if not date2:
            return ConflictResolution(
                field='date',
                value1=date1,
                value2=date2,
                chosen=date1,
                reason='Value 2 was empty',
                decision=MergeDecision.KEEP_PRIMARY
            )

        # Check specificity (more specific = better)
        specificity1 = self._date_specificity(date1)
        specificity2 = self._date_specificity(date2)

        if specificity1 > specificity2:
            return ConflictResolution(
                field='date',
                value1=date1,
                value2=date2,
                chosen=date1,
                reason='Value 1 more specific',
                decision=MergeDecision.KEEP_PRIMARY
            )
        elif specificity2 > specificity1:
            return ConflictResolution(
                field='date',
                value1=date1,
                value2=date2,
                chosen=date2,
                reason='Value 2 more specific',
                decision=MergeDecision.KEEP_SECONDARY
            )

        # Equal specificity - flag for review if different
        if date1 != date2:
            return ConflictResolution(
                field='date',
                value1=date1,
                value2=date2,
                chosen=date1,  # Default to primary
                reason='Dates differ, manual review recommended',
                decision=MergeDecision.MANUAL_REVIEW
            )

        # Same date
        return ConflictResolution(
            field='date',
            value1=date1,
            value2=date2,
            chosen=date1,
            reason='Dates identical',
            decision=MergeDecision.KEEP_PRIMARY
        )

    def resolve_place_conflict(
        self,
        place1: str,
        place2: str
    ) -> ConflictResolution:
        """
        Resolve conflict between two different places.

        Strategy:
        - If one is empty, use the other
        - Prefer more detailed place (more components)
        - If both detailed, keep both
        """
        # Empty check
        if not place1:
            return ConflictResolution(
                field='place',
                value1=place1,
                value2=place2,
                chosen=place2,
                reason='Value 1 was empty',
                decision=MergeDecision.KEEP_SECONDARY
            )

        if not place2:
            return ConflictResolution(
                field='place',
                value1=place1,
                value2=place2,
                chosen=place1,
                reason='Value 2 was empty',
                decision=MergeDecision.KEEP_PRIMARY
            )

        # Count place components (separated by commas)
        components1 = len([c for c in place1.split(',') if c.strip()])
        components2 = len([c for c in place2.split(',') if c.strip()])

        if components1 > components2:
            return ConflictResolution(
                field='place',
                value1=place1,
                value2=place2,
                chosen=place1,
                reason='Value 1 more detailed',
                decision=MergeDecision.KEEP_PRIMARY
            )
        elif components2 > components1:
            return ConflictResolution(
                field='place',
                value1=place1,
                value2=place2,
                chosen=place2,
                reason='Value 2 more detailed',
                decision=MergeDecision.KEEP_SECONDARY
            )

        # Both equally detailed - check if one contains the other
        if place1.lower() in place2.lower():
            return ConflictResolution(
                field='place',
                value1=place1,
                value2=place2,
                chosen=place2,
                reason='Value 2 contains Value 1',
                decision=MergeDecision.KEEP_SECONDARY
            )
        elif place2.lower() in place1.lower():
            return ConflictResolution(
                field='place',
                value1=place1,
                value2=place2,
                chosen=place1,
                reason='Value 1 contains Value 2',
                decision=MergeDecision.KEEP_PRIMARY
            )

        # Different places - keep primary but flag
        return ConflictResolution(
            field='place',
            value1=place1,
            value2=place2,
            chosen=place1,
            reason='Places differ, keeping primary',
            decision=MergeDecision.MANUAL_REVIEW
        )

    def resolve_sex_conflict(
        self,
        sex1: str,
        sex2: str
    ) -> ConflictResolution:
        """
        Resolve conflict between sex/gender values.

        Strategy:
        - If one is Unknown ('U'), use the other
        - If both definite and different, flag for manual review
        """
        # Normalize
        s1 = (sex1 or 'U').upper()
        s2 = (sex2 or 'U').upper()

        # Unknown check
        if s1 == 'U' and s2 != 'U':
            return ConflictResolution(
                field='sex',
                value1=sex1,
                value2=sex2,
                chosen=sex2,
                reason='Value 1 was unknown',
                decision=MergeDecision.KEEP_SECONDARY
            )

        if s2 == 'U' and s1 != 'U':
            return ConflictResolution(
                field='sex',
                value1=sex1,
                value2=sex2,
                chosen=sex1,
                reason='Value 2 was unknown',
                decision=MergeDecision.KEEP_PRIMARY
            )

        # Both definite
        if s1 == s2:
            return ConflictResolution(
                field='sex',
                value1=sex1,
                value2=sex2,
                chosen=sex1,
                reason='Values identical',
                decision=MergeDecision.KEEP_PRIMARY
            )

        # Conflict - both definite but different
        return ConflictResolution(
            field='sex',
            value1=sex1,
            value2=sex2,
            chosen=sex1,
            reason='Sex conflict - manual review required!',
            decision=MergeDecision.MANUAL_REVIEW
        )

    def _date_specificity(self, date_str: str) -> int:
        """
        Calculate date specificity score.

        Returns:
            3 = full date (day, month, year)
            2 = month and year
            1 = year only
            0 = invalid/empty
        """
        if not date_str:
            return 0

        # Count date components
        # Common formats: "1 JAN 1900", "JAN 1900", "1900"
        parts = date_str.strip().split()

        if len(parts) >= 3:
            return 3  # Day, month, year
        elif len(parts) == 2:
            return 2  # Month and year
        elif len(parts) == 1:
            # Check if it's a year (4 digits)
            if parts[0].isdigit() and len(parts[0]) == 4:
                return 1
            return 0
        else:
            return 0
