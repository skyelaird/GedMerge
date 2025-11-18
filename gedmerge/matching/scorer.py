"""
Match scoring engine with confidence-based decisions.

Calculates similarity scores across multiple dimensions and combines
them into an overall confidence score with validation-based confidence tiers.
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from rapidfuzz import fuzz
import phonetics
from ..rootsmagic.models import RMPerson, RMName, RMEvent
from ..validation import (
    ConfidenceTier,
    ConfidenceTierSystem,
    ConfidenceAssessment,
    DateValidator,
    ParsedDate,
)


@dataclass(slots=True)
class MatchResult:
    """Results of matching two person records."""

    # Individual component scores (0-100)
    name_score: float = 0.0
    phonetic_score: float = 0.0
    date_score: float = 0.0
    place_score: float = 0.0
    relationship_score: float = 0.0
    sex_score: float = 0.0

    # Overall confidence (0-100)
    overall_score: float = 0.0

    # Detailed breakdown
    details: Dict[str, any] = field(default_factory=dict)

    # Flags
    is_exact_name_match: bool = False
    is_exact_date_match: bool = False
    has_conflicting_info: bool = False

    # Confidence tier assessment (added for validation)
    confidence_tier: Optional[ConfidenceTier] = None
    confidence_assessment: Optional[ConfidenceAssessment] = None

    def __str__(self) -> str:
        """Human-readable description."""
        base_str = (
            f"Match Score: {self.overall_score:.1f}%\n"
            f"  Name: {self.name_score:.1f}%\n"
            f"  Phonetic: {self.phonetic_score:.1f}%\n"
            f"  Dates: {self.date_score:.1f}%\n"
            f"  Places: {self.place_score:.1f}%\n"
            f"  Relationships: {self.relationship_score:.1f}%\n"
            f"  Sex: {self.sex_score:.1f}%"
        )

        if self.confidence_tier:
            tier_str = f"\n  Confidence Tier: {self.confidence_tier.value.upper()}"
            if self.confidence_assessment:
                tier_str += f" (adjusted: {self.confidence_assessment.adjusted_score * 100:.1f}%)"
            base_str += tier_str

        return base_str


class MatchScorer:
    """
    Calculates match scores between person records.

    Scoring weights:
    - Name similarity: 35%
    - Phonetic matching: 25%
    - Date proximity: 20%
    - Place matching: 10%
    - Relationship overlap: 8%
    - Sex match: 2%

    Integrates confidence tier system for validation-based assessment:
    - AUTO_MERGE: High confidence (>= 0.85) with all validations passed
    - NEEDS_REVIEW: Medium confidence (0.50 - 0.85) or minor issues
    - REJECT: Low confidence (< 0.50) or validation failures
    """

    # Scoring weights (must sum to 1.0)
    WEIGHTS = {
        'name': 0.35,
        'phonetic': 0.25,
        'date': 0.20,
        'place': 0.10,
        'relationship': 0.08,
        'sex': 0.02,
    }

    def __init__(self):
        """Initialize the match scorer with validation system."""
        self.confidence_system = ConfidenceTierSystem()
        self.date_validator = DateValidator()

    # Date tolerance (years)
    DATE_EXACT_TOLERANCE = 0  # Same year = exact
    DATE_CLOSE_TOLERANCE = 2  # Within 2 years = close
    DATE_LIKELY_TOLERANCE = 5  # Within 5 years = possible

    # Multilingual language equivalents
    LANGUAGE_GROUPS = {
        'germanic': {'en', 'de', 'nl', 'sv', 'no', 'da'},
        'romance': {'fr', 'es', 'it', 'pt', 'ro', 'la'},
        'slavic': {'ru', 'pl', 'cs', 'uk', 'sr', 'hr'},
    }

    def calculate_match_score(
        self,
        person1: RMPerson,
        person2: RMPerson
    ) -> MatchResult:
        """
        Calculate overall match score between two persons.

        Args:
            person1: First person
            person2: Second person

        Returns:
            MatchResult with scores and details
        """
        result = MatchResult()

        # Calculate individual component scores
        result.name_score = self._score_names(person1, person2, result)
        result.phonetic_score = self._score_phonetic(person1, person2, result)
        result.date_score = self._score_dates(person1, person2, result)
        result.place_score = self._score_places(person1, person2, result)
        result.relationship_score = self._score_relationships(person1, person2, result)
        result.sex_score = self._score_sex(person1, person2, result)

        # Calculate weighted overall score
        result.overall_score = (
            result.name_score * self.WEIGHTS['name'] +
            result.phonetic_score * self.WEIGHTS['phonetic'] +
            result.date_score * self.WEIGHTS['date'] +
            result.place_score * self.WEIGHTS['place'] +
            result.relationship_score * self.WEIGHTS['relationship'] +
            result.sex_score * self.WEIGHTS['sex']
        )

        # Apply penalties for conflicting information
        if result.has_conflicting_info:
            result.overall_score *= 0.5  # 50% penalty
            result.details['penalty'] = 'Conflicting information detected'

        # Apply confidence tier assessment with validation
        result = self._apply_confidence_assessment(person1, person2, result)

        return result

    def _score_names(
        self,
        person1: RMPerson,
        person2: RMPerson,
        result: MatchResult
    ) -> float:
        """
        Score name similarity using fuzzy matching.

        Handles:
        - Multiple name variations per person
        - Multilingual names (same person, different languages)
        - Given name vs nickname matching
        - Surname variations
        """
        if not person1.names or not person2.names:
            return 0.0

        max_score = 0.0
        best_match = None

        # Compare all name combinations
        for name1 in person1.names:
            for name2 in person2.names:
                score = self._compare_names(name1, name2)
                if score > max_score:
                    max_score = score
                    best_match = (name1, name2)

        # Store details
        if best_match:
            result.details['name_match'] = {
                'name1': f"{best_match[0].given} /{best_match[0].surname}/",
                'name2': f"{best_match[1].given} /{best_match[1].surname}/",
                'score': max_score,
            }

            if max_score == 100:
                result.is_exact_name_match = True

        return max_score

    def _compare_names(self, name1: RMName, name2: RMName) -> float:
        """
        Compare two name records.

        Returns score 0-100.
        """
        scores = []

        # Compare surnames (most important)
        if name1.surname and name2.surname:
            surname_score = fuzz.ratio(
                name1.surname.lower(),
                name2.surname.lower()
            )
            scores.append(surname_score * 1.2)  # Weight surnames more

        # Compare given names
        if name1.given and name2.given:
            given_score = fuzz.ratio(
                name1.given.lower(),
                name2.given.lower()
            )
            scores.append(given_score)

        # Compare nicknames if present
        if name1.nickname and name2.nickname:
            nickname_score = fuzz.ratio(
                name1.nickname.lower(),
                name2.nickname.lower()
            )
            scores.append(nickname_score)

        # Cross-check: nickname vs given name
        if name1.nickname and name2.given:
            cross_score = fuzz.ratio(
                name1.nickname.lower(),
                name2.given.lower()
            )
            scores.append(cross_score * 0.9)  # Slightly lower weight

        if name1.given and name2.nickname:
            cross_score = fuzz.ratio(
                name1.given.lower(),
                name2.nickname.lower()
            )
            scores.append(cross_score * 0.9)

        if not scores:
            return 0.0

        # Return average of all comparisons, capped at 100
        avg_score = sum(scores) / len(scores)
        return min(avg_score, 100.0)

    def _score_phonetic(
        self,
        person1: RMPerson,
        person2: RMPerson,
        result: MatchResult
    ) -> float:
        """
        Score phonetic similarity using Metaphone.

        Handles spelling variations and pronunciation-based matching.
        """
        if not person1.names or not person2.names:
            return 0.0

        max_score = 0.0

        for name1 in person1.names:
            for name2 in person2.names:
                score = self._compare_phonetic(name1, name2)
                max_score = max(max_score, score)

        return max_score

    def _compare_phonetic(self, name1: RMName, name2: RMName) -> float:
        """Compare phonetic encodings of names."""
        matches = 0
        total = 0

        # Compare surname phonetics
        if name1.surname_mp and name2.surname_mp:
            total += 1
            if name1.surname_mp == name2.surname_mp:
                matches += 2  # Surnames count double

        # Compare given name phonetics
        if name1.given_mp and name2.given_mp:
            total += 1
            if name1.given_mp == name2.given_mp:
                matches += 1

        # Compare nickname phonetics
        if name1.nickname_mp and name2.nickname_mp:
            total += 1
            if name1.nickname_mp == name2.nickname_mp:
                matches += 1

        if total == 0:
            return 0.0

        # Normalize to 0-100
        return (matches / (total + 1)) * 100  # +1 to account for double weight

    def _score_dates(
        self,
        person1: RMPerson,
        person2: RMPerson,
        result: MatchResult
    ) -> float:
        """
        Score date proximity for birth and death dates.

        Scoring:
        - Same year: 100%
        - Within 2 years: 80%
        - Within 5 years: 50%
        - Beyond 5 years: 0%
        """
        scores = []

        # Compare birth dates (event_type=1 for Birth)
        birth1 = self._get_event_year(person1, 1)
        birth2 = self._get_event_year(person2, 1)

        if birth1 and birth2:
            birth_score = self._compare_years(birth1, birth2)
            scores.append(birth_score)

            if birth1 == birth2:
                result.details['birth_match'] = 'exact'
            elif abs(birth1 - birth2) <= self.DATE_CLOSE_TOLERANCE:
                result.details['birth_match'] = 'close'

        # Compare death dates (event_type=2 for Death)
        death1 = self._get_event_year(person1, 2)
        death2 = self._get_event_year(person2, 2)

        if death1 and death2:
            death_score = self._compare_years(death1, death2)
            scores.append(death_score)

            if death1 == death2:
                result.details['death_match'] = 'exact'
            elif abs(death1 - death2) <= self.DATE_CLOSE_TOLERANCE:
                result.details['death_match'] = 'close'

        # Check for conflicts (dates too far apart)
        if birth1 and birth2 and abs(birth1 - birth2) > 10:
            result.has_conflicting_info = True
        if death1 and death2 and abs(death1 - death2) > 10:
            result.has_conflicting_info = True

        if not scores:
            return 50.0  # Neutral score if no dates available

        # If both dates match exactly
        if len(scores) == 2 and all(s == 100 for s in scores):
            result.is_exact_date_match = True

        return sum(scores) / len(scores)

    def _compare_years(self, year1: int, year2: int) -> float:
        """Compare two years and return similarity score."""
        diff = abs(year1 - year2)

        if diff == self.DATE_EXACT_TOLERANCE:
            return 100.0
        elif diff <= self.DATE_CLOSE_TOLERANCE:
            return 80.0
        elif diff <= self.DATE_LIKELY_TOLERANCE:
            return 50.0
        else:
            return 0.0

    def _score_places(
        self,
        person1: RMPerson,
        person2: RMPerson,
        result: MatchResult
    ) -> float:
        """
        Score place similarity for birth and death places.

        Handles multilingual place names.
        """
        scores = []

        # Compare birth places (event_type=1 for Birth)
        birth_place1 = self._get_event_place(person1, 1)
        birth_place2 = self._get_event_place(person2, 1)

        if birth_place1 and birth_place2:
            place_score = self._compare_places(birth_place1, birth_place2)
            scores.append(place_score)

        # Compare death places (event_type=2 for Death)
        death_place1 = self._get_event_place(person1, 2)
        death_place2 = self._get_event_place(person2, 2)

        if death_place1 and death_place2:
            place_score = self._compare_places(death_place1, death_place2)
            scores.append(place_score)

        if not scores:
            return 50.0  # Neutral score

        return sum(scores) / len(scores)

    def _compare_places(self, place1: str, place2: str) -> float:
        """Compare two place names using fuzzy matching."""
        if not place1 or not place2:
            return 0.0

        # Direct fuzzy match
        score = fuzz.token_sort_ratio(place1.lower(), place2.lower())

        return float(score)

    def _score_relationships(
        self,
        person1: RMPerson,
        person2: RMPerson,
        result: MatchResult
    ) -> float:
        """
        Score relationship overlap.

        If two persons share the same parents or spouses, they're more
        likely to be duplicates.
        """
        # Check for shared spouses (using simple IDs for now)
        # TODO: Load full family relationships from database
        spouse1 = person1.spouse_id if hasattr(person1, 'spouse_id') else None
        spouse2 = person2.spouse_id if hasattr(person2, 'spouse_id') else None
        shared_spouse = (spouse1 and spouse2 and spouse1 == spouse2)

        # Check for shared parents
        parent1 = person1.parent_id if hasattr(person1, 'parent_id') else None
        parent2 = person2.parent_id if hasattr(person2, 'parent_id') else None
        shared_parent = (parent1 and parent2 and parent1 == parent2)

        # Calculate score
        score = 0.0

        if shared_parent:
            score += 60.0  # Same parents = strong indicator
            result.details['shared_parent'] = parent1

        if shared_spouse:
            score += 40.0  # Same spouse = strong indicator
            result.details['shared_spouse'] = spouse1

        return min(score, 100.0)

    def _score_sex(
        self,
        person1: RMPerson,
        person2: RMPerson,
        result: MatchResult
    ) -> float:
        """
        Score sex/gender match.

        Same sex: 100%
        Unknown sex: 50% (neutral)
        Different sex: 0% (strong conflict)

        Sex codes: 0=Unknown, 1=Male, 2=Female (or 'U', 'M', 'F' strings)
        """
        # Get sex values (handle both int and string formats)
        sex1 = person1.sex if hasattr(person1, 'sex') else 0
        sex2 = person2.sex if hasattr(person2, 'sex') else 0

        # Normalize to integers
        if isinstance(sex1, str):
            sex1 = {'U': 0, 'M': 1, 'F': 2}.get(sex1.upper(), 0)
        if isinstance(sex2, str):
            sex2 = {'U': 0, 'M': 1, 'F': 2}.get(sex2.upper(), 0)

        # If either is unknown (0)
        if sex1 == 0 or sex2 == 0:
            return 50.0

        # If same
        if sex1 == sex2:
            return 100.0

        # If different (strong conflict)
        result.has_conflicting_info = True
        sex_names = {0: 'U', 1: 'M', 2: 'F'}
        result.details['sex_conflict'] = f"{sex_names.get(sex1, '?')} vs {sex_names.get(sex2, '?')}"
        return 0.0

    def _get_event_year(self, person: RMPerson, event_type: int) -> Optional[int]:
        """
        Extract year from event.

        Args:
            person: Person to get event from
            event_type: Event type code (1=Birth, 2=Death, etc.)

        Returns:
            Year as integer, or None
        """
        if not person.events:
            return None

        for event in person.events:
            if event.event_type == event_type and event.date:
                # Try to extract year from date string
                try:
                    # Handle various date formats
                    # Simple year extraction: look for 4-digit number
                    import re
                    match = re.search(r'\b(\d{4})\b', event.date)
                    if match:
                        return int(match.group(1))
                except:
                    pass

        return None

    def _get_event_place(self, person: RMPerson, event_type: int) -> Optional[str]:
        """
        Extract place from event.

        Args:
            person: Person to get event from
            event_type: Event type code (1=Birth, 2=Death, etc.)

        Returns:
            Place string, or None
        """
        if not person.events:
            return None

        for event in person.events:
            # Handle both place attribute and place_id
            if event.event_type == event_type:
                # Try place attribute first
                if hasattr(event, 'place') and event.place:
                    return event.place
                # TODO: Could look up place_id from PlaceTable if needed

        return None

    def _apply_confidence_assessment(
        self,
        person1: RMPerson,
        person2: RMPerson,
        result: MatchResult
    ) -> MatchResult:
        """
        Apply confidence tier assessment with validation.

        This integrates the validation system to check for:
        - Impossible date scenarios
        - Living status inconsistencies
        - Generation gap issues
        - Family relationship overlap

        Args:
            person1: First person
            person2: Second person
            result: Current match result with base scores

        Returns:
            Updated MatchResult with confidence tier and assessment
        """
        # Extract dates using our date validator
        birth_date1_str = None
        death_date1_str = None
        birth_date2_str = None
        death_date2_str = None

        for event in person1.events:
            if event.event_type == 1:  # Birth
                birth_date1_str = event.date
            elif event.event_type == 2:  # Death
                death_date1_str = event.date

        for event in person2.events:
            if event.event_type == 1:  # Birth
                birth_date2_str = event.date
            elif event.event_type == 2:  # Death
                death_date2_str = event.date

        # Parse dates
        birth_date1 = self.date_validator.parse_date(birth_date1_str)
        death_date1 = self.date_validator.parse_date(death_date1_str)
        birth_date2 = self.date_validator.parse_date(birth_date2_str)
        death_date2 = self.date_validator.parse_date(death_date2_str)

        # Find latest event year for living status determination
        latest_event_year1 = self._get_latest_event_year(person1)
        latest_event_year2 = self._get_latest_event_year(person2)

        # Build person data dicts for confidence system
        person1_data = {
            'birth_date': birth_date1,
            'death_date': death_date1,
            'living_flag': person1.living if hasattr(person1, 'living') else None,
            'parent_family_ids': person1.parent_family_ids if hasattr(person1, 'parent_family_ids') else [],
            'spouse_family_ids': person1.spouse_family_ids if hasattr(person1, 'spouse_family_ids') else [],
            'sex': self._get_sex_string(person1.sex),
            'latest_event_year': latest_event_year1,
        }

        person2_data = {
            'birth_date': birth_date2,
            'death_date': death_date2,
            'living_flag': person2.living if hasattr(person2, 'living') else None,
            'parent_family_ids': person2.parent_family_ids if hasattr(person2, 'parent_family_ids') else [],
            'spouse_family_ids': person2.spouse_family_ids if hasattr(person2, 'spouse_family_ids') else [],
            'sex': self._get_sex_string(person2.sex),
            'latest_event_year': latest_event_year2,
        }

        # Assess confidence with validation
        # Convert overall_score from 0-100 to 0-1 scale
        base_score = result.overall_score / 100.0

        assessment = self.confidence_system.assess_merge_confidence(
            base_score,
            person1_data,
            person2_data,
            relationships=None  # TODO: Could extract relationships if needed
        )

        # Update result with confidence tier
        result.confidence_tier = assessment.tier
        result.confidence_assessment = assessment

        # Store validation details in result
        result.details['validation'] = {
            'tier': assessment.tier.value,
            'adjusted_score': assessment.adjusted_score,
            'date_validation_passed': assessment.date_validation_passed,
            'living_status_consistent': assessment.living_status_consistent,
            'generation_gap_plausible': assessment.generation_gap_plausible,
            'has_family_overlap': assessment.has_family_overlap,
            'date_quality_score': assessment.date_quality_score,
            'issues_count': len(assessment.validation_issues),
        }

        if assessment.validation_issues:
            result.details['validation_issues'] = [
                {
                    'severity': issue.severity,
                    'category': issue.category,
                    'message': issue.message,
                }
                for issue in assessment.validation_issues
            ]

        return result

    def _get_latest_event_year(self, person: RMPerson) -> Optional[int]:
        """Get the year of the most recent event for a person."""
        latest_year = None

        if person.events:
            for event in person.events:
                if event.date:
                    year = self._get_event_year(person, event.event_type)
                    if year and (latest_year is None or year > latest_year):
                        latest_year = year

        return latest_year

    def _get_sex_string(self, sex: int) -> str:
        """Convert RootsMagic sex code to string."""
        if sex == 1:
            return 'M'
        elif sex == 2:
            return 'F'
        else:
            return 'U'
