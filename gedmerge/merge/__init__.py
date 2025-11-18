"""
Person record merging with intelligent conflict resolution.

This module provides functionality for merging duplicate person records
while preserving data quality and resolving conflicts.
"""

from .merger import PersonMerger, MergeStrategy, MergeResult
from .conflict_resolver import (
    ConflictResolver,
    ConflictResolution,
    ConflictType,
    MergeDecision
)

__all__ = [
    'PersonMerger',
    'MergeStrategy',
    'MergeResult',
    'ConflictResolver',
    'ConflictResolution',
    'ConflictType',
    'MergeDecision',
]
