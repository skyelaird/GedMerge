"""
Validation module for genealogical data.

Provides date validation, living status checks, generation gap detection,
and confidence tier assessment for merging records.
"""

from .genealogical_rules import (
    MIN_PARENT_AGE,
    MAX_PARENT_AGE_MALE,
    MAX_PARENT_AGE_FEMALE,
    TYPICAL_GENERATION_YEARS,
    MIN_GENERATION_GAP,
    MAX_GENERATION_GAP,
    MAX_LIFESPAN,
    MIN_MARRIAGE_AGE,
    DateQuality,
    AgeAtEvent,
)

from .date_validator import (
    DateValidator,
    ParsedDate,
    DateValidationResult,
)

from .living_status import (
    LivingStatusValidator,
    LivingStatus,
    LivingStatusResult,
)

from .generation_validator import (
    GenerationValidator,
    GenerationGapResult,
    Relationship,
    RelationshipType,
)

from .confidence_tier import (
    ConfidenceTier,
    ConfidenceTierSystem,
    ConfidenceAssessment,
    ValidationIssue,
)


__all__ = [
    # Constants
    'MIN_PARENT_AGE',
    'MAX_PARENT_AGE_MALE',
    'MAX_PARENT_AGE_FEMALE',
    'TYPICAL_GENERATION_YEARS',
    'MIN_GENERATION_GAP',
    'MAX_GENERATION_GAP',
    'MAX_LIFESPAN',
    'MIN_MARRIAGE_AGE',
    'DateQuality',
    'AgeAtEvent',

    # Date validation
    'DateValidator',
    'ParsedDate',
    'DateValidationResult',

    # Living status
    'LivingStatusValidator',
    'LivingStatus',
    'LivingStatusResult',

    # Generation validation
    'GenerationValidator',
    'GenerationGapResult',
    'Relationship',
    'RelationshipType',

    # Confidence tier system
    'ConfidenceTier',
    'ConfidenceTierSystem',
    'ConfidenceAssessment',
    'ValidationIssue',
]
