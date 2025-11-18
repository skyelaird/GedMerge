"""Feature extraction for ML models."""

from typing import Dict, List, Tuple, Optional, Any
import numpy as np
from dataclasses import dataclass
from rapidfuzz import fuzz
import re

from ...core.person import Person
from ...matching.scorer import MatchScorer


@dataclass(slots=True)
class PersonFeatures:
    """Features extracted from a Person for ML models."""

    # Name features
    name_length: int
    surname_length: int
    given_name_length: int
    has_multiple_names: bool
    name_complexity: float  # ratio of unique chars

    # Language features
    detected_language: str
    language_confidence: float
    is_multilingual: bool

    # Date features
    has_birth_date: bool
    has_death_date: bool
    birth_year: Optional[int]
    death_year: Optional[int]
    age_at_death: Optional[int]
    date_precision: float  # 1.0 for exact, 0.5 for circa, 0 for missing

    # Place features
    has_birth_place: bool
    has_death_place: bool
    place_count: int
    unique_places: int

    # Relationship features
    num_parents: int
    num_spouses: int
    num_children: int
    family_connectivity: float  # how connected in family tree

    # Data quality features
    has_missing_surname: bool
    has_placeholder_name: bool
    has_title_in_name: bool
    data_completeness: float  # 0-1 score

    # Raw data for embedding
    full_name: str
    primary_surname: str
    primary_given_name: str


@dataclass(slots=True)
class PairwiseFeatures:
    """Features for a pair of persons (for duplicate detection)."""

    # Name similarity features
    name_similarity: float
    phonetic_similarity: float
    surname_similarity: float
    given_name_similarity: float
    exact_name_match: bool

    # Character-level features
    levenshtein_distance: int
    jaro_winkler_similarity: float
    token_set_ratio: float

    # Date features
    birth_date_match: float  # 1.0 for exact, 0.5 for close, 0 for mismatch
    death_date_match: float
    age_difference: Optional[int]
    date_conflict: bool

    # Place features
    birth_place_similarity: float
    death_place_similarity: float
    place_overlap: float

    # Relationship features
    shared_parents: int
    shared_spouses: int
    shared_children: int
    relationship_overlap_score: float

    # Conflict indicators
    sex_conflict: bool
    significant_age_gap: bool  # > 10 years
    different_locations: bool

    # Combined scores
    overall_similarity: float


class FeatureExtractor:
    """Extract features from Person objects for ML models."""

    def __init__(self, scorer: Optional[MatchScorer] = None):
        """
        Initialize feature extractor.

        Args:
            scorer: Optional MatchScorer for computing similarity scores
        """
        self.scorer = scorer or MatchScorer()

    def extract_person_features(self, person: Person) -> PersonFeatures:
        """
        Extract features from a single person.

        Args:
            person: Person object

        Returns:
            PersonFeatures object
        """
        # Get primary name
        primary_name = person.names[0] if person.names else None
        full_name = str(primary_name) if primary_name else ""
        surname = primary_name.surname if primary_name else ""
        given = primary_name.given if primary_name else ""

        # Language detection
        lang = primary_name.language if primary_name and primary_name.language else "en"
        lang_confidence = 1.0 if primary_name and primary_name.language else 0.5

        # Birth/death info
        birth_event = person.get_birth_event()
        death_event = person.get_death_event()

        birth_year = None
        death_year = None
        age_at_death = None

        if birth_event and birth_event.date:
            birth_year = self._extract_year(birth_event.date)

        if death_event and death_event.date:
            death_year = self._extract_year(death_event.date)

        if birth_year and death_year:
            age_at_death = death_year - birth_year

        # Date precision
        date_precision = 0.0
        if birth_event and birth_event.date:
            date_precision += 0.5
        if death_event and death_event.date:
            date_precision += 0.5

        # Places
        places = [e.place for e in person.events if e.place]
        unique_places = len(set(places))

        # Relationships
        num_parents = len([f for f in person.families_as_child])
        num_spouses = len([f for f in person.families_as_spouse])

        # Count children across all families
        num_children = 0
        for family in person.families_as_spouse:
            if hasattr(family, 'children'):
                num_children += len(family.children)

        # Data quality checks
        has_placeholder = any(
            name_part.lower() in ["unknown", "unnamed", "n.n.", "?", ""]
            for name_part in [surname, given]
        )

        title_pattern = re.compile(r'\b(Mr|Mrs|Dr|Sir|Lady|Lord|Rev|Prof)\b', re.IGNORECASE)
        has_title_in_name = bool(title_pattern.search(full_name))

        # Name complexity (ratio of unique characters)
        name_complexity = len(set(full_name.lower())) / max(len(full_name), 1)

        # Data completeness score
        completeness_items = [
            bool(surname),
            bool(given),
            bool(birth_event),
            bool(death_event),
            bool(person.sex),
            num_parents > 0,
        ]
        data_completeness = sum(completeness_items) / len(completeness_items)

        return PersonFeatures(
            name_length=len(full_name),
            surname_length=len(surname),
            given_name_length=len(given),
            has_multiple_names=len(person.names) > 1,
            name_complexity=name_complexity,
            detected_language=lang,
            language_confidence=lang_confidence,
            is_multilingual=len(set(n.language for n in person.names if n.language)) > 1,
            has_birth_date=birth_event is not None,
            has_death_date=death_event is not None,
            birth_year=birth_year,
            death_year=death_year,
            age_at_death=age_at_death,
            date_precision=date_precision,
            has_birth_place=bool(person.get_birth_place()),
            has_death_place=bool(person.get_death_place()),
            place_count=len(places),
            unique_places=unique_places,
            num_parents=num_parents,
            num_spouses=num_spouses,
            num_children=num_children,
            family_connectivity=min((num_parents + num_spouses + num_children) / 10.0, 1.0),
            has_missing_surname=not bool(surname),
            has_placeholder_name=has_placeholder,
            has_title_in_name=has_title_in_name,
            data_completeness=data_completeness,
            full_name=full_name,
            primary_surname=surname,
            primary_given_name=given,
        )

    def extract_pairwise_features(
        self,
        person1: Person,
        person2: Person
    ) -> PairwiseFeatures:
        """
        Extract features for a pair of persons.

        Args:
            person1: First person
            person2: Second person

        Returns:
            PairwiseFeatures object
        """
        # Get names
        name1 = str(person1.names[0]) if person1.names else ""
        name2 = str(person2.names[0]) if person2.names else ""

        surname1 = person1.names[0].surname if person1.names else ""
        surname2 = person2.names[0].surname if person2.names else ""

        given1 = person1.names[0].given if person1.names else ""
        given2 = person2.names[0].given if person2.names else ""

        # String similarities
        name_sim = fuzz.ratio(name1.lower(), name2.lower()) / 100.0
        surname_sim = fuzz.ratio(surname1.lower(), surname2.lower()) / 100.0
        given_sim = fuzz.ratio(given1.lower(), given2.lower()) / 100.0

        # Use scorer for phonetic similarity
        phonetic_sim = self.scorer.phonetic_similarity(name1, name2)

        # Advanced string metrics
        lev_dist = fuzz.distance(name1.lower(), name2.lower())
        jaro_winkler = fuzz.WRatio(name1.lower(), name2.lower()) / 100.0
        token_set = fuzz.token_set_ratio(name1.lower(), name2.lower()) / 100.0

        # Exact match
        exact_match = name1.lower().strip() == name2.lower().strip()

        # Date matching
        birth1 = person1.get_birth_event()
        birth2 = person2.get_birth_event()
        death1 = person1.get_death_event()
        death2 = person2.get_death_event()

        birth_match = self._compare_dates(birth1, birth2) if birth1 and birth2 else 0.0
        death_match = self._compare_dates(death1, death2) if death1 and death2 else 0.0

        # Age difference
        age1 = self._extract_year(birth1.date) if birth1 else None
        age2 = self._extract_year(birth2.date) if birth2 else None
        age_diff = abs(age1 - age2) if age1 and age2 else None

        # Date conflicts
        date_conflict = False
        if age_diff and age_diff > 5:  # More than 5 years difference
            date_conflict = True

        # Place similarity
        birth_place1 = person1.get_birth_place() or ""
        birth_place2 = person2.get_birth_place() or ""
        birth_place_sim = fuzz.ratio(birth_place1.lower(), birth_place2.lower()) / 100.0

        death_place1 = person1.get_death_place() or ""
        death_place2 = person2.get_death_place() or ""
        death_place_sim = fuzz.ratio(death_place1.lower(), death_place2.lower()) / 100.0

        # Place overlap
        places1 = set(e.place.lower() for e in person1.events if e.place)
        places2 = set(e.place.lower() for e in person2.events if e.place)
        place_overlap = len(places1 & places2) / max(len(places1 | places2), 1)

        # Relationship overlap
        # Count shared parents/spouses (simplified - would need family data)
        shared_parents = 0
        shared_spouses = 0
        shared_children = 0
        relationship_overlap = 0.0

        # Sex conflict
        sex_conflict = False
        if person1.sex and person2.sex and person1.sex != person2.sex:
            sex_conflict = True

        # Significant age gap
        sig_age_gap = age_diff > 10 if age_diff else False

        # Different locations
        diff_locations = False
        if birth_place1 and birth_place2 and birth_place_sim < 0.3:
            diff_locations = True

        # Overall similarity (weighted average)
        weights = {
            'name': 0.35,
            'phonetic': 0.25,
            'date': 0.20,
            'place': 0.10,
            'relationship': 0.08,
            'sex': 0.02,
        }

        overall = (
            weights['name'] * name_sim +
            weights['phonetic'] * phonetic_sim +
            weights['date'] * (birth_match + death_match) / 2 +
            weights['place'] * (birth_place_sim + death_place_sim) / 2 +
            weights['relationship'] * relationship_overlap +
            weights['sex'] * (0.0 if sex_conflict else 1.0)
        )

        return PairwiseFeatures(
            name_similarity=name_sim,
            phonetic_similarity=phonetic_sim,
            surname_similarity=surname_sim,
            given_name_similarity=given_sim,
            exact_name_match=exact_match,
            levenshtein_distance=lev_dist,
            jaro_winkler_similarity=jaro_winkler,
            token_set_ratio=token_set,
            birth_date_match=birth_match,
            death_date_match=death_match,
            age_difference=age_diff,
            date_conflict=date_conflict,
            birth_place_similarity=birth_place_sim,
            death_place_similarity=death_place_sim,
            place_overlap=place_overlap,
            shared_parents=shared_parents,
            shared_spouses=shared_spouses,
            shared_children=shared_children,
            relationship_overlap_score=relationship_overlap,
            sex_conflict=sex_conflict,
            significant_age_gap=sig_age_gap,
            different_locations=diff_locations,
            overall_similarity=overall,
        )

    def to_feature_vector(self, features: PersonFeatures) -> np.ndarray:
        """
        Convert PersonFeatures to numpy array.

        Args:
            features: PersonFeatures object

        Returns:
            Feature vector as numpy array
        """
        return np.array([
            features.name_length,
            features.surname_length,
            features.given_name_length,
            float(features.has_multiple_names),
            features.name_complexity,
            features.language_confidence,
            float(features.is_multilingual),
            float(features.has_birth_date),
            float(features.has_death_date),
            features.birth_year or 0,
            features.death_year or 0,
            features.age_at_death or 0,
            features.date_precision,
            float(features.has_birth_place),
            float(features.has_death_place),
            features.place_count,
            features.unique_places,
            features.num_parents,
            features.num_spouses,
            features.num_children,
            features.family_connectivity,
            float(features.has_missing_surname),
            float(features.has_placeholder_name),
            float(features.has_title_in_name),
            features.data_completeness,
        ], dtype=np.float32)

    def to_pairwise_vector(self, features: PairwiseFeatures) -> np.ndarray:
        """
        Convert PairwiseFeatures to numpy array.

        Args:
            features: PairwiseFeatures object

        Returns:
            Feature vector as numpy array
        """
        return np.array([
            features.name_similarity,
            features.phonetic_similarity,
            features.surname_similarity,
            features.given_name_similarity,
            float(features.exact_name_match),
            features.levenshtein_distance,
            features.jaro_winkler_similarity,
            features.token_set_ratio,
            features.birth_date_match,
            features.death_date_match,
            features.age_difference or 0,
            float(features.date_conflict),
            features.birth_place_similarity,
            features.death_place_similarity,
            features.place_overlap,
            features.shared_parents,
            features.shared_spouses,
            features.shared_children,
            features.relationship_overlap_score,
            float(features.sex_conflict),
            float(features.significant_age_gap),
            float(features.different_locations),
            features.overall_similarity,
        ], dtype=np.float32)

    def _extract_year(self, date_str: str) -> Optional[int]:
        """Extract year from date string."""
        if not date_str:
            return None

        # Try to find 4-digit year
        year_match = re.search(r'\b(1\d{3}|20\d{2})\b', date_str)
        if year_match:
            return int(year_match.group(1))

        return None

    def _compare_dates(self, event1, event2) -> float:
        """
        Compare two events by date.

        Returns:
            1.0 for exact match, 0.5-0.9 for close match, 0.0 for no match
        """
        if not event1 or not event2:
            return 0.0

        year1 = self._extract_year(event1.date) if event1.date else None
        year2 = self._extract_year(event2.date) if event2.date else None

        if not year1 or not year2:
            return 0.0

        if year1 == year2:
            return 1.0

        diff = abs(year1 - year2)
        if diff <= 2:
            return 0.9
        elif diff <= 5:
            return 0.7
        elif diff <= 10:
            return 0.5
        else:
            return 0.0
