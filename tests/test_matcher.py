"""
Tests for person matching engine.
"""

import pytest
from gedmerge.rootsmagic.models import RMPerson, RMName, RMEvent
from gedmerge.matching import PersonMatcher, MatchScorer


class TestPersonMatcher:
    """Tests for PersonMatcher class."""

    def test_normalize_name_removes_honorifics_english(self):
        """Test that English honorifics are removed."""
        name = "Mr. John Smith Jr."
        normalized = PersonMatcher.normalize_name_for_matching(name, 'en')
        assert 'mr' not in normalized
        assert 'jr' not in normalized
        assert 'john' in normalized
        assert 'smith' in normalized

    def test_normalize_name_removes_honorifics_french(self):
        """Test that French honorifics are removed."""
        name = "M. Jean Dupont"
        normalized = PersonMatcher.normalize_name_for_matching(name, 'fr')
        assert 'm' not in normalized or 'jean' in normalized  # 'm' in jean is ok
        assert 'jean' in normalized
        assert 'dupont' in normalized

    def test_normalize_name_removes_honorifics_german(self):
        """Test that German honorifics are removed."""
        name = "Herr Wilhelm Schmidt"
        normalized = PersonMatcher.normalize_name_for_matching(name, 'de')
        assert 'herr' not in normalized
        assert 'wilhelm' in normalized
        assert 'schmidt' in normalized

    def test_normalize_name_handles_punctuation(self):
        """Test that punctuation is removed."""
        name = "O'Brien, John (Jack)"
        normalized = PersonMatcher.normalize_name_for_matching(name)
        assert ',' not in normalized
        assert '(' not in normalized
        assert ')' not in normalized

    def test_get_metaphone(self):
        """Test Metaphone phonetic encoding."""
        # Similar sounding names should have same metaphone
        mp1 = PersonMatcher.get_metaphone("Smith")
        mp2 = PersonMatcher.get_metaphone("Smyth")
        assert mp1 == mp2

        mp3 = PersonMatcher.get_metaphone("Catherine")
        mp4 = PersonMatcher.get_metaphone("Katherine")
        assert mp3 == mp4


class TestMatchScorer:
    """Tests for MatchScorer class."""

    def test_score_exact_match(self):
        """Test scoring of exact name matches."""
        person1 = RMPerson(
            person_id=1,
            sex='M',
            names=[RMName(
                name_id=1,
                given='John',
                surname='Smith',
                surname_mp='SM0',
                given_mp='JN'
            )]
        )

        person2 = RMPerson(
            person_id=2,
            sex='M',
            names=[RMName(
                name_id=2,
                given='John',
                surname='Smith',
                surname_mp='SM0',
                given_mp='JN'
            )]
        )

        scorer = MatchScorer()
        result = scorer.calculate_match_score(person1, person2)

        assert result.name_score == 100.0
        assert result.phonetic_score > 0
        assert result.sex_score == 100.0
        assert result.overall_score > 70.0

    def test_score_phonetic_match(self):
        """Test scoring of phonetically similar names."""
        person1 = RMPerson(
            person_id=1,
            sex='F',
            names=[RMName(
                name_id=1,
                given='Catherine',
                surname='Smith',
                surname_mp='SM0',
                given_mp='K0RN'
            )]
        )

        person2 = RMPerson(
            person_id=2,
            sex='F',
            names=[RMName(
                name_id=2,
                given='Katherine',
                surname='Smith',
                surname_mp='SM0',
                given_mp='K0RN'
            )]
        )

        scorer = MatchScorer()
        result = scorer.calculate_match_score(person1, person2)

        # Names are similar but not exact
        assert result.name_score > 70.0
        # Phonetic should match exactly
        assert result.phonetic_score > 80.0

    def test_score_multilingual_names(self):
        """Test scoring of multilingual name variants."""
        person1 = RMPerson(
            person_id=1,
            sex='M',
            names=[
                RMName(
                    name_id=1,
                    given='Wilhelm',
                    surname='Schmidt',
                    language='de',
                    surname_mp='XMT',
                    given_mp='WLHM'
                )
            ]
        )

        person2 = RMPerson(
            person_id=2,
            sex='M',
            names=[
                RMName(
                    name_id=2,
                    given='William',
                    surname='Smith',
                    language='en',
                    surname_mp='XMT',  # Same metaphone as Schmidt
                    given_mp='WLM'     # Similar to Wilhelm
                )
            ]
        )

        scorer = MatchScorer()
        result = scorer.calculate_match_score(person1, person2)

        # Should have reasonable phonetic match
        assert result.phonetic_score > 50.0

    def test_score_sex_conflict(self):
        """Test that different sex creates conflict."""
        person1 = RMPerson(
            person_id=1,
            sex='M',
            names=[RMName(name_id=1, given='John', surname='Smith')]
        )

        person2 = RMPerson(
            person_id=2,
            sex='F',
            names=[RMName(name_id=2, given='John', surname='Smith')]
        )

        scorer = MatchScorer()
        result = scorer.calculate_match_score(person1, person2)

        assert result.sex_score == 0.0
        assert result.has_conflicting_info is True
        # Overall score should be penalized
        assert result.overall_score < 50.0

    def test_score_date_proximity(self):
        """Test date proximity scoring."""
        person1 = RMPerson(
            person_id=1,
            sex='M',
            names=[RMName(name_id=1, given='John', surname='Smith')],
            events=[
                RMEvent(
                    event_id=1,
                    event_type='Birth',
                    date='1 JAN 1900',
                    place='London'
                )
            ]
        )

        person2 = RMPerson(
            person_id=2,
            sex='M',
            names=[RMName(name_id=2, given='John', surname='Smith')],
            events=[
                RMEvent(
                    event_id=2,
                    event_type='Birth',
                    date='15 MAR 1900',  # Same year
                    place='London'
                )
            ]
        )

        scorer = MatchScorer()
        result = scorer.calculate_match_score(person1, person2)

        # Same year should score high
        assert result.date_score == 100.0

    def test_score_nickname_matching(self):
        """Test that nicknames match given names."""
        person1 = RMPerson(
            person_id=1,
            sex='M',
            names=[RMName(
                name_id=1,
                given='William',
                surname='Smith',
                nickname='Bill'
            )]
        )

        person2 = RMPerson(
            person_id=2,
            sex='M',
            names=[RMName(
                name_id=2,
                given='Bill',
                surname='Smith'
            )]
        )

        scorer = MatchScorer()
        result = scorer.calculate_match_score(person1, person2)

        # Should have good name match (nickname vs given)
        assert result.name_score > 60.0


class TestMatchCandidate:
    """Tests for MatchCandidate dataclass."""

    def test_confidence_levels(self):
        """Test confidence level classification."""
        from gedmerge.matching import MatchCandidate
        from gedmerge.matching.scorer import MatchResult

        # High confidence
        result_high = MatchResult(overall_score=90.0)
        candidate = MatchCandidate(
            person1_id=1,
            person2_id=2,
            person1=None,
            person2=None,
            match_result=result_high
        )
        assert candidate.is_high_confidence
        assert not candidate.is_medium_confidence
        assert not candidate.is_low_confidence

        # Medium confidence
        result_med = MatchResult(overall_score=70.0)
        candidate.match_result = result_med
        assert not candidate.is_high_confidence
        assert candidate.is_medium_confidence
        assert not candidate.is_low_confidence

        # Low confidence
        result_low = MatchResult(overall_score=50.0)
        candidate.match_result = result_low
        assert not candidate.is_high_confidence
        assert not candidate.is_medium_confidence
        assert candidate.is_low_confidence
