"""
Confidence tier system for merge decisions.

Provides three-tier classification:
- AUTO_MERGE: High confidence, safe to merge automatically
- NEEDS_REVIEW: Medium confidence, human review recommended
- REJECT: Low confidence or validation failures, should not merge
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from enum import Enum

from .date_validator import DateValidator, ParsedDate, DateValidationResult
from .living_status import LivingStatusValidator, LivingStatusResult, LivingStatus
from .generation_validator import GenerationValidator, GenerationGapResult, Relationship
from .genealogical_rules import DateQuality


class ConfidenceTier(Enum):
    """Confidence tiers for merge decisions."""
    AUTO_MERGE = "auto_merge"  # High confidence (>= 0.85)
    NEEDS_REVIEW = "needs_review"  # Medium confidence (0.50 - 0.85)
    REJECT = "reject"  # Low confidence (< 0.50) or hard validation failures


@dataclass(slots=True)
class ValidationIssue:
    """A validation issue found during merge evaluation."""
    severity: str  # 'error', 'warning', 'info'
    category: str  # 'date', 'living_status', 'generation_gap', 'name', etc.
    message: str
    confidence_impact: float  # How much this reduces confidence (0.0-1.0)


@dataclass(slots=True)
class ConfidenceAssessment:
    """Complete confidence assessment for a potential merge."""
    tier: ConfidenceTier
    base_score: float  # Original match score (0.0-1.0)
    adjusted_score: float  # Score after validation adjustments (0.0-1.0)
    validation_issues: List[ValidationIssue]
    date_validation_passed: bool
    living_status_consistent: bool
    generation_gap_plausible: bool
    has_family_overlap: bool
    date_quality_score: float
    details: Dict[str, Any]

    def get_recommendation(self) -> str:
        """Get a human-readable recommendation."""
        if self.tier == ConfidenceTier.AUTO_MERGE:
            return "Recommended for automatic merge"
        elif self.tier == ConfidenceTier.NEEDS_REVIEW:
            return "Flagged for human review"
        else:
            return "Not recommended for merge"

    def get_summary(self) -> str:
        """Get a summary of the assessment."""
        lines = [
            f"Confidence Tier: {self.tier.value.upper()}",
            f"Adjusted Score: {self.adjusted_score:.2f} (base: {self.base_score:.2f})",
            f"Recommendation: {self.get_recommendation()}",
        ]

        if self.validation_issues:
            lines.append(f"\nValidation Issues ({len(self.validation_issues)}):")
            for issue in self.validation_issues:
                lines.append(f"  [{issue.severity.upper()}] {issue.message}")

        return "\n".join(lines)


class ConfidenceTierSystem:
    """
    System for evaluating merge confidence and assigning tiers.

    Integrates all validation rules and applies penalties based on:
    - Date validation failures
    - Living status inconsistencies
    - Generation gap issues
    - Data quality
    - Family relationship overlap
    """

    # Thresholds for tier assignment
    AUTO_MERGE_THRESHOLD = 0.85  # Must be >= this for auto-merge
    REJECT_THRESHOLD = 0.50  # Must be >= this to avoid rejection

    def __init__(self):
        """Initialize the confidence tier system."""
        self.date_validator = DateValidator()
        self.living_validator = LivingStatusValidator()
        self.generation_validator = GenerationValidator()

    def assess_merge_confidence(
        self,
        base_match_score: float,
        person1_data: Dict[str, Any],
        person2_data: Dict[str, Any],
        relationships: Optional[List[Relationship]] = None
    ) -> ConfidenceAssessment:
        """
        Assess confidence for merging two person records.

        Args:
            base_match_score: Original similarity score (0.0-1.0)
            person1_data: Data for first person
            person2_data: Data for second person
            relationships: Known relationships between the people

        person_data format:
        {
            'birth_date': ParsedDate or str,
            'death_date': ParsedDate or str,
            'living_flag': bool,
            'parent_family_ids': List[str],
            'spouse_family_ids': List[str],
            'sex': str,
            'latest_event_year': int,
        }

        Returns:
            ConfidenceAssessment with tier and details
        """
        issues = []
        details = {}
        adjusted_score = base_match_score

        # Parse dates if needed
        birth_date1 = self._parse_date_field(person1_data.get('birth_date'))
        death_date1 = self._parse_date_field(person1_data.get('death_date'))
        birth_date2 = self._parse_date_field(person2_data.get('birth_date'))
        death_date2 = self._parse_date_field(person2_data.get('death_date'))

        # 1. Date Validation
        date_validation_passed = True
        date_quality_score = 1.0

        # Validate birth-death ranges for each person
        for i, (birth, death) in enumerate([(birth_date1, death_date1), (birth_date2, death_date2)], 1):
            result, date_issues = self.date_validator.validate_date_range(birth, death)
            if result == DateValidationResult.INVALID:
                issues.append(ValidationIssue(
                    severity='error',
                    category='date',
                    message=f"Person {i}: " + "; ".join(date_issues),
                    confidence_impact=0.5
                ))
                adjusted_score *= 0.5
                date_validation_passed = False
            elif result == DateValidationResult.WARNING:
                issues.append(ValidationIssue(
                    severity='warning',
                    category='date',
                    message=f"Person {i}: " + "; ".join(date_issues),
                    confidence_impact=0.1
                ))
                adjusted_score *= 0.9

        # Validate date overlap between records
        if birth_date1 and birth_date2:
            date_overlap_confidence = self.date_validator.calculate_date_overlap_confidence(
                birth_date1, birth_date2
            )
            details['birth_date_overlap'] = date_overlap_confidence

            if date_overlap_confidence < 0.3:
                issues.append(ValidationIssue(
                    severity='error',
                    category='date',
                    message=f"Birth dates too different (confidence: {date_overlap_confidence:.2f})",
                    confidence_impact=0.4
                ))
                adjusted_score *= 0.6
                date_validation_passed = False
            elif date_overlap_confidence < 0.6:
                issues.append(ValidationIssue(
                    severity='warning',
                    category='date',
                    message=f"Birth dates differ (confidence: {date_overlap_confidence:.2f})",
                    confidence_impact=0.2
                ))
                adjusted_score *= 0.8

        # Calculate date quality score
        date_quality_score = self._calculate_date_quality(
            birth_date1, death_date1, birth_date2, death_date2
        )
        details['date_quality_score'] = date_quality_score

        # 2. Living Status Validation
        living_status_consistent = True

        living1 = self.living_validator.determine_living_status(
            birth_date1,
            death_date1,
            person1_data.get('living_flag'),
            person1_data.get('latest_event_year')
        )
        living2 = self.living_validator.determine_living_status(
            birth_date2,
            death_date2,
            person2_data.get('living_flag'),
            person2_data.get('latest_event_year')
        )

        is_consistent, consistency_penalty, consistency_issues = \
            self.living_validator.validate_living_status_consistency(living1, living2)

        details['living_status1'] = living1.status.value
        details['living_status2'] = living2.status.value
        details['living_status_consistent'] = is_consistent

        if not is_consistent:
            for issue_msg in consistency_issues:
                issues.append(ValidationIssue(
                    severity='error',
                    category='living_status',
                    message=issue_msg,
                    confidence_impact=consistency_penalty
                ))
            adjusted_score *= (1.0 - consistency_penalty)
            living_status_consistent = False
        elif consistency_penalty > 0:
            for issue_msg in consistency_issues:
                issues.append(ValidationIssue(
                    severity='warning',
                    category='living_status',
                    message=issue_msg,
                    confidence_impact=consistency_penalty
                ))
            adjusted_score *= (1.0 - consistency_penalty)

        # 3. Generation Gap Validation
        generation_gap_plausible = True

        if birth_date1 and birth_date2:
            if relationships:
                gen_result = self.generation_validator.validate_generation_gap(
                    birth_date1, birth_date2, relationships
                )
            else:
                # No relationship info - assume potential duplicates (same generation)
                year1 = birth_date1.get_best_year()
                year2 = birth_date2.get_best_year()
                if year1 and year2:
                    gen_result = self.generation_validator.validate_generation_gap_simple(
                        year1, year2, assume_same_generation=True
                    )
                else:
                    gen_result = None

            if gen_result:
                details['generation_gap'] = {
                    'is_plausible': gen_result.is_plausible,
                    'plausibility_score': gen_result.plausibility_score,
                    'birth_year_diff': gen_result.birth_year_diff,
                }

                if not gen_result.is_plausible:
                    for issue_msg in gen_result.issues:
                        issues.append(ValidationIssue(
                            severity='error',
                            category='generation_gap',
                            message=issue_msg,
                            confidence_impact=0.4
                        ))
                    adjusted_score *= 0.6
                    generation_gap_plausible = False
                elif gen_result.plausibility_score < 0.7:
                    for issue_msg in gen_result.issues:
                        issues.append(ValidationIssue(
                            severity='warning',
                            category='generation_gap',
                            message=issue_msg,
                            confidence_impact=0.15
                        ))
                    adjusted_score *= 0.85

                # Apply plausibility score as multiplier
                adjusted_score *= (0.5 + 0.5 * gen_result.plausibility_score)

        # 4. Family Relationship Overlap
        has_family_overlap = False
        family_overlap_score = self.generation_validator.get_relationship_overlap_score(
            person1_data.get('parent_family_ids', []),
            person1_data.get('spouse_family_ids', []),
            person2_data.get('parent_family_ids', []),
            person2_data.get('spouse_family_ids', [])
        )

        details['family_overlap_score'] = family_overlap_score
        has_family_overlap = family_overlap_score > 0

        # Boost confidence if strong family overlap and sparse dates
        if family_overlap_score >= 1.0:
            # Same families - strong evidence
            if date_quality_score < 0.5:
                # Sparse dates - rely more on family overlap
                issues.append(ValidationIssue(
                    severity='info',
                    category='family',
                    message="Strong family overlap compensates for sparse date data",
                    confidence_impact=-0.2  # Negative = boost
                ))
                adjusted_score = min(1.0, adjusted_score * 1.2)
            else:
                # Good dates too - excellent
                adjusted_score = min(1.0, adjusted_score * 1.1)
        elif family_overlap_score > 0 and date_quality_score < 0.5:
            # Some family overlap with sparse dates
            issues.append(ValidationIssue(
                severity='info',
                category='family',
                message="Family overlap helps with sparse date data",
                confidence_impact=-0.1  # Boost
            ))
            adjusted_score = min(1.0, adjusted_score * 1.1)

        # 5. Determine Tier
        tier = self._determine_tier(
            adjusted_score,
            date_validation_passed,
            living_status_consistent,
            generation_gap_plausible
        )

        return ConfidenceAssessment(
            tier=tier,
            base_score=base_match_score,
            adjusted_score=adjusted_score,
            validation_issues=issues,
            date_validation_passed=date_validation_passed,
            living_status_consistent=living_status_consistent,
            generation_gap_plausible=generation_gap_plausible,
            has_family_overlap=has_family_overlap,
            date_quality_score=date_quality_score,
            details=details
        )

    def _parse_date_field(self, date_field: Any) -> Optional[ParsedDate]:
        """Parse a date field that might be a string or already parsed."""
        if isinstance(date_field, ParsedDate):
            return date_field
        elif isinstance(date_field, str):
            return self.date_validator.parse_date(date_field)
        else:
            return None

    def _calculate_date_quality(
        self,
        birth_date1: Optional[ParsedDate],
        death_date1: Optional[ParsedDate],
        birth_date2: Optional[ParsedDate],
        death_date2: Optional[ParsedDate]
    ) -> float:
        """
        Calculate overall date quality score.

        Returns:
            Score 0.0-1.0 indicating quality/completeness of date data
        """
        scores = []

        for date in [birth_date1, death_date1, birth_date2, death_date2]:
            if date:
                scores.append(self.date_validator.get_date_quality_multiplier(date))
            else:
                scores.append(0.0)

        # Average the scores
        if scores:
            return sum(scores) / len(scores)
        else:
            return 0.0

    def _determine_tier(
        self,
        adjusted_score: float,
        date_valid: bool,
        living_consistent: bool,
        generation_plausible: bool
    ) -> ConfidenceTier:
        """
        Determine the confidence tier based on score and validations.

        Hard rejection criteria:
        - Date validation failed (impossible dates)
        - Living status inconsistent
        - Generation gap implausible
        - Score below rejection threshold

        Args:
            adjusted_score: Final adjusted confidence score
            date_valid: Whether date validation passed
            living_consistent: Whether living status is consistent
            generation_plausible: Whether generation gap is plausible

        Returns:
            ConfidenceTier
        """
        # Hard rejections
        if not date_valid:
            return ConfidenceTier.REJECT
        if not living_consistent:
            return ConfidenceTier.REJECT
        if not generation_plausible:
            return ConfidenceTier.REJECT
        if adjusted_score < self.REJECT_THRESHOLD:
            return ConfidenceTier.REJECT

        # Auto-merge if score is high enough
        if adjusted_score >= self.AUTO_MERGE_THRESHOLD:
            return ConfidenceTier.AUTO_MERGE

        # Otherwise needs review
        return ConfidenceTier.NEEDS_REVIEW

    def batch_assess(
        self,
        potential_matches: List[Dict[str, Any]]
    ) -> List[ConfidenceAssessment]:
        """
        Assess multiple potential matches.

        Args:
            potential_matches: List of dicts with:
                {
                    'base_score': float,
                    'person1': dict,
                    'person2': dict,
                    'relationships': List[Relationship] (optional)
                }

        Returns:
            List of ConfidenceAssessment objects
        """
        assessments = []

        for match in potential_matches:
            assessment = self.assess_merge_confidence(
                match['base_score'],
                match['person1'],
                match['person2'],
                match.get('relationships')
            )
            assessments.append(assessment)

        return assessments

    def get_tier_statistics(
        self,
        assessments: List[ConfidenceAssessment]
    ) -> Dict[str, Any]:
        """
        Get statistics about a batch of assessments.

        Returns:
            Dict with counts and percentages for each tier
        """
        total = len(assessments)
        if total == 0:
            return {
                'total': 0,
                'auto_merge': 0,
                'needs_review': 0,
                'reject': 0
            }

        counts = {
            'auto_merge': sum(1 for a in assessments if a.tier == ConfidenceTier.AUTO_MERGE),
            'needs_review': sum(1 for a in assessments if a.tier == ConfidenceTier.NEEDS_REVIEW),
            'reject': sum(1 for a in assessments if a.tier == ConfidenceTier.REJECT),
        }

        return {
            'total': total,
            'auto_merge': counts['auto_merge'],
            'auto_merge_pct': counts['auto_merge'] / total * 100,
            'needs_review': counts['needs_review'],
            'needs_review_pct': counts['needs_review'] / total * 100,
            'reject': counts['reject'],
            'reject_pct': counts['reject'] / total * 100,
        }
