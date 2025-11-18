# Genealogical Data Validation Features

This document describes the new validation features added to GedMerge to improve the accuracy and reliability of duplicate person detection and merging.

## Overview

The validation system provides three-tier confidence assessment for potential duplicate matches:

- **AUTO_MERGE**: High confidence (≥0.85) with all validations passed - safe for automatic merging
- **NEEDS_REVIEW**: Medium confidence (0.50-0.85) or minor issues - flagged for human review
- **REJECT**: Low confidence (<0.50) or validation failures - should not be merged

## Features

### 1. Date Validation with Impossible Date Detection

**Module**: `gedmerge/validation/date_validator.py`

Validates genealogical dates for plausibility:

- **Impossible scenarios rejected**:
  - Death date before birth date
  - Lifespan exceeding 110 years
  - Parent age at child's birth < 12 years or > 80-100 years (depending on sex)
  - Marriage age < 12 years
  - Future dates

- **Date parsing**: Supports GEDCOM date formats
  - Exact dates: "1 JAN 1900"
  - Year only: "1900"
  - Estimated: "ABT 1900", "EST 1900", "CAL 1900"
  - Ranges: "BET 1900 AND 1905", "BEF 1900", "AFT 1900"

- **Date quality scoring**: Adjusts confidence based on date precision
  - Exact dates (day/month/year): 100%
  - Year only: 90%
  - Estimated: 70%
  - Ranges: 60%

**Example rejection**:
```python
# Person 1: Born 1900, Died 1890 ❌ REJECTED
# Reason: Death before birth - impossible
```

### 2. Living Status Validation

**Module**: `gedmerge/validation/living_status.py`

Determines if a person is likely living and validates consistency between records:

- **Detection methods**:
  - Database `living` flag (if available)
  - Death record presence
  - Age calculation (current year - birth year)
  - 110-year rule for maximum lifespan

- **Status levels**:
  - DEFINITELY_LIVING
  - PROBABLY_LIVING
  - UNKNOWN
  - PROBABLY_DECEASED
  - DEFINITELY_DECEASED

- **Consistency checking**:
  - Rejects merges where one record indicates living and another indicates deceased
  - Flags conflicts between database flags
  - Validates age consistency between records

**Example rejection**:
```python
# Record 1: Has death date 1980, living=False
# Record 2: No death date, living=True, recent events
# Result: ❌ REJECTED - Living status conflict
```

### 3. Generation Gap Detection

**Module**: `gedmerge/validation/generation_validator.py`

Validates that birth year differences are plausible for the relationship:

- **Hard limits**:
  - Same person (duplicates): Birth years should match within 2-5 years
  - Parent-child: 12-80 years apart
  - Grandparent-grandchild: 24-160 years apart
  - Extreme rejection: >80-100 years for parent-child

- **Relationship-aware validation**:
  - Uses family relationships from database when available
  - Calculates generation distance
  - Validates birth year gap matches generation distance

- **Plausibility scoring**:
  - Returns 0.0-1.0 score for how plausible the age gap is
  - Accounts for historical variations (child marriages, late fathers, etc.)

**Example rejection**:
```python
# Person 1: Born 1900
# Person 2: Born 1850
# Relationship: Potential duplicates
# Result: ❌ REJECTED - 50 year birth gap impossible for same person
```

### 4. Confidence Tier System

**Module**: `gedmerge/validation/confidence_tier.py`

Integrates all validation rules into a comprehensive assessment:

- **Multi-factor evaluation**:
  - Base similarity score (names, dates, places)
  - Date validation results
  - Living status consistency
  - Generation gap plausibility
  - Family relationship overlap
  - Data quality scores

- **Penalty system**:
  - Major penalties (0.5-0.8): Invalid dates, living conflicts, impossible gaps
  - Minor penalties (0.1-0.3): Warnings, unusual but possible scenarios

- **Boost system**:
  - Family overlap with sparse dates: +10-20% confidence
  - Exact date matches: +10% confidence

- **Validation issues tracking**:
  - Severity levels: ERROR, WARNING, INFO
  - Category tagging: date, living_status, generation_gap, family
  - Human-readable messages for review

**Decision logic**:
```
IF validation_failures (impossible dates, living conflicts, etc.):
    → REJECT
ELIF adjusted_score >= 0.85 AND all_validations_passed:
    → AUTO_MERGE
ELIF adjusted_score >= 0.50:
    → NEEDS_REVIEW
ELSE:
    → REJECT
```

### 5. Family Relationship Overlap Enhancement

**Feature**: When dates are sparse or uncertain, family relationship overlap is weighted more heavily.

- **Implementation**:
  - Shared parent families (siblings): +20% boost
  - Shared spouse families: +20% boost
  - Partial family connections: +10% boost

- **Rationale**: Family relationships are generally more reliable than estimated dates

**Example**:
```python
# Record 1: Birth "ABT 1900", parents in Family F1
# Record 2: Birth "EST 1902", parents in Family F1
# Base score: 0.72
# Family overlap boost: +20%
# Final score: 0.86 → AUTO_MERGE ✓
```

## Integration Points

### Scorer Integration

**File**: `gedmerge/matching/scorer.py`

- Enhanced `MatchResult` with confidence tier fields
- Added `ConfidenceTierSystem` initialization
- New `_apply_confidence_assessment()` method called after base scoring
- Validation details stored in `result.details['validation']`

### Merger Integration

**File**: `gedmerge/merge/merger.py`

- Updated `merge_candidates()` to use confidence tiers
- Three-way merge decision:
  - REJECT → Skip with error message
  - AUTO_MERGE → Proceed automatically
  - NEEDS_REVIEW → Depends on MergeStrategy
- Validation issues included in `MergeResult.details`

## Constants and Rules

**File**: `gedmerge/validation/genealogical_rules.py`

Key constants:
```python
MIN_PARENT_AGE = 12              # Biological minimum
MAX_PARENT_AGE_MALE = 100        # Maximum for fathers
MAX_PARENT_AGE_FEMALE = 55       # Maximum for mothers
MIN_GENERATION_GAP = 12          # Parent-child minimum
MAX_GENERATION_GAP = 80          # Parent-child maximum
EXTREME_GENERATION_GAP = 100     # Absolute rejection
MAX_LIFESPAN = 110               # Maximum reasonable age
MIN_MARRIAGE_AGE = 12            # Historical minimum
CURRENT_YEAR = 2025              # For living status checks
```

## Usage

### Basic Usage

The validation system is integrated automatically. No code changes needed:

```python
from gedmerge.matching import MatchScorer

scorer = MatchScorer()  # Automatically includes validation
result = scorer.calculate_match_score(person1, person2)

# Check confidence tier
if result.confidence_tier == ConfidenceTier.AUTO_MERGE:
    print("Safe to auto-merge")
elif result.confidence_tier == ConfidenceTier.NEEDS_REVIEW:
    print("Human review recommended")
    print(f"Issues: {result.details['validation_issues']}")
else:  # REJECT
    print("Should not merge")
```

### Merger Usage

```python
from gedmerge.merge import PersonMerger, MergeStrategy

merger = PersonMerger(db, strategy=MergeStrategy.INTERACTIVE)
results = merger.merge_candidates(
    candidates,
    use_confidence_tiers=True  # Enable validation-based decisions
)

# Review results
for result in results:
    if result.success:
        print(f"Merged {result.removed_person_id} → {result.merged_person_id}")
    else:
        print(f"Skipped: {result.errors}")
        if 'validation_issues' in result.details:
            for issue in result.details['validation_issues']:
                print(f"  - {issue['severity']}: {issue['message']}")
```

### Direct Validation

You can also use the validators directly:

```python
from gedmerge.validation import DateValidator, ConfidenceTierSystem

# Date validation
validator = DateValidator()
birth = validator.parse_date("1 JAN 1900")
death = validator.parse_date("1 JAN 1980")
result, issues = validator.validate_date_range(birth, death)

# Full confidence assessment
system = ConfidenceTierSystem()
assessment = system.assess_merge_confidence(
    base_score=0.85,
    person1_data={...},
    person2_data={...}
)
print(assessment.get_summary())
```

## Testing

**File**: `tests/test_validation.py`

Comprehensive test suite covering:
- Date parsing and validation
- Living status detection
- Generation gap validation
- Confidence tier assignment
- Edge cases and boundary conditions

Run tests:
```bash
cd GedMerge
pytest tests/test_validation.py -v
```

## Benefits

1. **Reduced false positives**: Invalid matches are automatically rejected
2. **Increased confidence**: Valid matches are scored more accurately
3. **Better automation**: High-confidence matches can be auto-merged safely
4. **Improved user experience**: Flagged matches include specific reasons for review
5. **Historical accuracy**: Genealogical rules based on biological and historical reality

## Future Enhancements

Potential improvements:
- Relationship graph traversal for distant relatives
- Historical context awareness (wars, migrations, epidemics)
- Geographic plausibility checking
- Machine learning for pattern detection
- Confidence calibration based on user feedback
