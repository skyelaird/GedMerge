"""
Person matching engine with phonetic and fuzzy matching.

Handles multilingual names, honorific suffixes, and relationship analysis.
"""

from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass
from datetime import datetime
import phonetics
from rapidfuzz import fuzz
from ..rootsmagic.models import RMPerson, RMName, RMEvent, RMPlace
from ..rootsmagic.adapter import RootsMagicDatabase
from .scorer import MatchScorer, MatchResult


@dataclass(slots=True)
class MatchCandidate:
    """Represents a potential duplicate match between two persons."""
    person1_id: int
    person2_id: int
    person1: RMPerson
    person2: RMPerson
    match_result: MatchResult

    @property
    def confidence(self) -> float:
        """Overall confidence score (0-100)."""
        return self.match_result.overall_score

    @property
    def is_high_confidence(self) -> bool:
        """True if confidence >= 85 (likely duplicate)."""
        return self.confidence >= 85

    @property
    def is_medium_confidence(self) -> bool:
        """True if 60 <= confidence < 85 (possible duplicate)."""
        return 60 <= self.confidence < 85

    @property
    def is_low_confidence(self) -> bool:
        """True if confidence < 60 (unlikely duplicate)."""
        return self.confidence < 60


class PersonMatcher:
    """
    Matches person records using multiple algorithms.

    Matching Strategies:
    1. Phonetic matching (Metaphone) - handles name variations
    2. Fuzzy string matching - handles typos and spelling differences
    3. Multilingual name comparison - handles different languages
    4. Date proximity - birth/death dates within tolerance
    5. Place matching - birthplace/death place similarity
    6. Relationship analysis - shared family members
    """

    # Multilingual honorific titles to normalize
    HONORIFIC_PREFIXES = {
        'en': {'mr', 'mrs', 'ms', 'miss', 'dr', 'rev', 'sir', 'lady', 'lord', 'dame'},
        'fr': {'m', 'mme', 'mlle', 'dr', 'abbé', 'père', 'sr', 'sœur'},
        'de': {'herr', 'frau', 'fräulein', 'dr', 'prof', 'von'},
        'es': {'sr', 'sra', 'srta', 'don', 'doña', 'dr'},
        'it': {'sig', 'signor', 'signora', 'signorina', 'dr', 'don'},
        'la': {'dominus', 'domina', 'sanctus', 'sancta'},
    }

    HONORIFIC_SUFFIXES = {
        'jr', 'sr', 'ii', 'iii', 'iv', 'v', 'esq', 'md', 'phd',
    }

    def __init__(self, db: RootsMagicDatabase, min_confidence: float = 60.0):
        """
        Initialize the matcher.

        Args:
            db: RootsMagic database connection
            min_confidence: Minimum confidence score to consider (0-100)
        """
        self.db = db
        self.min_confidence = min_confidence
        self.scorer = MatchScorer()

    def find_duplicates(
        self,
        person_ids: Optional[List[int]] = None,
        limit: Optional[int] = None
    ) -> List[MatchCandidate]:
        """
        Find potential duplicate persons.

        Args:
            person_ids: Specific person IDs to check, or None for all
            limit: Maximum number of matches to return

        Returns:
            List of match candidates sorted by confidence (highest first)
        """
        if person_ids is None:
            # Get all persons from database
            persons = self._get_all_persons()
        else:
            persons = [self.db.get_person(pid) for pid in person_ids]
            persons = [p for p in persons if p is not None]

        matches = []

        # Compare each person with all others
        for i, person1 in enumerate(persons):
            for person2 in persons[i+1:]:
                if person1.person_id == person2.person_id:
                    continue

                match_result = self.scorer.calculate_match_score(person1, person2)

                if match_result.overall_score >= self.min_confidence:
                    candidate = MatchCandidate(
                        person1_id=person1.person_id,
                        person2_id=person2.person_id,
                        person1=person1,
                        person2=person2,
                        match_result=match_result
                    )
                    matches.append(candidate)

        # Sort by confidence (highest first)
        matches.sort(key=lambda m: m.confidence, reverse=True)

        if limit:
            matches = matches[:limit]

        return matches

    def find_duplicates_for_person(
        self,
        person: RMPerson,
        max_matches: int = 10
    ) -> List[MatchCandidate]:
        """
        Find potential duplicates for a specific person.

        Args:
            person: The person to find duplicates for
            max_matches: Maximum number of matches to return

        Returns:
            List of match candidates sorted by confidence
        """
        # Get all other persons
        all_persons = self._get_all_persons()
        matches = []

        for other in all_persons:
            if other.person_id == person.person_id:
                continue

            match_result = self.scorer.calculate_match_score(person, other)

            if match_result.overall_score >= self.min_confidence:
                candidate = MatchCandidate(
                    person1_id=person.person_id,
                    person2_id=other.person_id,
                    person1=person,
                    person2=other,
                    match_result=match_result
                )
                matches.append(candidate)

        # Sort by confidence
        matches.sort(key=lambda m: m.confidence, reverse=True)

        return matches[:max_matches]

    def is_likely_duplicate(self, person1: RMPerson, person2: RMPerson) -> bool:
        """
        Quick check if two persons are likely duplicates.

        Args:
            person1: First person
            person2: Second person

        Returns:
            True if confidence >= 85
        """
        match_result = self.scorer.calculate_match_score(person1, person2)
        return match_result.overall_score >= 85

    def _get_all_persons(self) -> List[RMPerson]:
        """Get all persons from database."""
        # Query all person IDs
        cursor = self.db.conn.cursor()
        cursor.execute("SELECT PersonID FROM PersonTable ORDER BY PersonID")
        person_ids = [row[0] for row in cursor.fetchall()]

        # Load person objects
        persons = []
        for pid in person_ids:
            person = self.db.get_person(pid)
            if person:
                persons.append(person)

        return persons

    @staticmethod
    def normalize_name_for_matching(name: str, language: Optional[str] = None) -> str:
        """
        Normalize a name for matching by removing honorifics and standardizing.

        Args:
            name: Name to normalize
            language: Language code (en, fr, de, etc.)

        Returns:
            Normalized name
        """
        if not name:
            return ""

        normalized = name.lower().strip()

        # Remove common punctuation
        for char in ['.', ',', '/', '\\', '(', ')', '[', ']']:
            normalized = normalized.replace(char, ' ')

        # Split into parts
        parts = normalized.split()
        filtered_parts = []

        # Get honorifics for this language (or all if unknown)
        if language and language in PersonMatcher.HONORIFIC_PREFIXES:
            prefixes = PersonMatcher.HONORIFIC_PREFIXES[language]
        else:
            # Combine all languages
            prefixes = set()
            for lang_prefixes in PersonMatcher.HONORIFIC_PREFIXES.values():
                prefixes.update(lang_prefixes)

        suffixes = PersonMatcher.HONORIFIC_SUFFIXES

        # Filter out honorifics
        for part in parts:
            clean_part = part.strip()
            if clean_part and clean_part not in prefixes and clean_part not in suffixes:
                filtered_parts.append(clean_part)

        return ' '.join(filtered_parts)

    @staticmethod
    def get_metaphone(text: str) -> str:
        """
        Get Metaphone phonetic encoding of text.

        Args:
            text: Text to encode

        Returns:
            Metaphone code
        """
        if not text:
            return ""
        return phonetics.metaphone(text)
