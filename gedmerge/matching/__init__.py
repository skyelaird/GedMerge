"""
Duplicate detection matching engine.

This module provides algorithms for detecting potential duplicate person records
using phonetic matching, fuzzy string matching, and multilingual name comparison.
"""

from .matcher import PersonMatcher, MatchCandidate
from .scorer import MatchScorer, MatchResult

__all__ = ['PersonMatcher', 'MatchCandidate', 'MatchScorer', 'MatchResult']
