"""
Machine Learning module for GedMerge.

This module provides ML-enhanced duplicate detection, name matching,
language detection, and data quality classification.
"""

from .models import (
    DuplicateDetectionModel,
    NameMatchingModel,
    LanguageDetectionModel,
    RelationshipInferenceModel,
    DataQualityClassifier,
)

__all__ = [
    "DuplicateDetectionModel",
    "NameMatchingModel",
    "LanguageDetectionModel",
    "RelationshipInferenceModel",
    "DataQualityClassifier",
]
