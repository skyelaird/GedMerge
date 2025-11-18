# Duplicate Detection and Merging System

## Overview

This system provides intelligent duplicate detection and merging for genealogy person records in RootsMagic databases. It uses multiple matching algorithms and handles multilingual names, including honorific suffixes.

## Features

### 1. **Matching Engine** (`gedmerge/matching/`)

The matching engine uses multiple algorithms to detect potential duplicates:

#### Phonetic Matching
- Uses **Metaphone** algorithm for phonetic encoding
- Handles spelling variations (Smith vs. Smyth, Catherine vs. Katherine)
- Leverages existing `surname_mp`, `given_mp`, `nickname_mp` fields in RootsMagic database
- Particularly effective for:
  - Transcription errors
  - Spelling variations across languages
  - Historical spelling inconsistencies

#### Fuzzy String Matching
- Uses **rapidfuzz** library for similarity scoring
- Handles:
  - Typos and OCR errors
  - Incomplete names
  - Name variants (Bill vs. William)
- Token-based matching for multi-word names

#### Multilingual Name Comparison
- Supports multiple languages:
  - **English** (en): John, Margaret, Elizabeth, William
  - **French** (fr): Jean, Marie, Pierre, Marguerite
  - **German** (de): Wilhelm, Friedrich, Heinrich, Johann
  - **Italian** (it): variants marked with "detto"
  - **Spanish** (es): common Hispanic names
  - **Latin** (la): historical records

#### Honorific Suffix Handling
- **Automatically normalizes** honorific titles and suffixes:

**English:**
- Prefixes: Mr, Mrs, Ms, Miss, Dr, Rev, Sir, Lady, Lord, Dame
- Suffixes: Jr, Sr, II, III, IV, V, Esq, MD, PhD

**French:**
- Prefixes: M, Mme, Mlle, Dr, Abbé, Père, Sr, Sœur

**German:**
- Prefixes: Herr, Frau, Fräulein, Dr, Prof, von

**Spanish:**
- Prefixes: Sr, Sra, Srta, Don, Doña, Dr

**Italian:**
- Prefixes: Sig, Signor, Signora, Signorina, Dr, Don

**Latin:**
- Prefixes: Dominus, Domina, Sanctus, Sancta

#### Additional Matching Factors
- **Date Proximity**: Birth/death dates within configurable tolerance (default: 2-5 years)
- **Place Matching**: Fuzzy matching of birthplace and death place
- **Relationship Analysis**: Shared parents or spouses increase confidence
- **Sex Validation**: Conflicting sex reduces confidence dramatically

### 2. **Confidence-Based Scoring** (`gedmerge/matching/scorer.py`)

Each match receives a confidence score (0-100%) based on weighted components:

| Component | Weight | Description |
|-----------|--------|-------------|
| Name similarity | 35% | Fuzzy string matching on names |
| Phonetic matching | 25% | Metaphone comparison |
| Date proximity | 20% | Birth/death date closeness |
| Place matching | 10% | Location similarity |
| Relationship overlap | 8% | Shared family members |
| Sex match | 2% | Gender consistency |

#### Confidence Levels

- **HIGH (≥85%)**: Likely duplicate, safe for automatic merging
  - Exact or very close name match
  - Matching dates and/or locations
  - No conflicting information

- **MEDIUM (60-84%)**: Possible duplicate, review recommended
  - Similar names with minor differences
  - Dates within tolerance
  - May have some missing data

- **LOW (<60%)**: Unlikely duplicate
  - Weak name similarity
  - Significant date differences
  - Conflicting information

#### Conflict Detection

The system automatically detects and flags conflicts:
- Different sex/gender (strong conflict)
- Birth dates >10 years apart (strong conflict)
- Death dates >10 years apart (strong conflict)

**Penalty**: Conflicting information reduces overall score by 50%

### 3. **Merge Workflow** (`gedmerge/merge/`)

#### Merge Strategies

Three merge strategies are available:

1. **AUTOMATIC**: Auto-merge all matches above threshold (default: 90%)
   - Best for: High-quality databases with many obvious duplicates
   - Risk: Very low (only merges high-confidence matches)

2. **INTERACTIVE**: Auto-merge high confidence, prompt for medium
   - Best for: Most use cases (default recommended)
   - Balances efficiency with safety

3. **MANUAL**: Prompt for every match
   - Best for: Critical databases requiring full human review
   - Slowest but safest

#### Merge Process

1. **Select Primary Record**
   - More complete data (more names, events) preferred
   - Earlier PersonID (older, more vetted record) preferred
   - Primary name over alternate name preferred

2. **Resolve Conflicts** (automatic)
   - Empty vs. value → keep value
   - "NN" placeholder vs. real name → keep real name
   - Both valid names → keep both as alternates
   - More specific date → keep more specific
   - More detailed place → keep more detailed
   - Unknown sex vs. definite → keep definite
   - Conflicting definite values → flag for manual review

3. **Merge Data**
   - **Names**: Combine all unique name variations
   - **Events**: Merge events, remove duplicates
   - **Relationships**: Combine family relationships
   - **Sources**: Preserve all citations
   - **Notes**: Combine notes

4. **Update Database** (transactional)
   - Update primary record with merged data
   - Transfer all relationships to primary
   - Delete secondary record
   - Commit or rollback on error

#### Conflict Resolution Examples

```
Scenario: Empty given name
  Person 1: "NN /Smith/"
  Person 2: "John /Smith/"
  → Resolution: Keep "John" (real name over placeholder)

Scenario: Different languages
  Person 1: "Wilhelm /Schmidt/" [de]
  Person 2: "William /Smith/" [en]
  → Resolution: Keep both as alternate names (multilingual variants)

Scenario: Date specificity
  Person 1: Birth "1900"
  Person 2: Birth "15 JAN 1900"
  → Resolution: Keep "15 JAN 1900" (more specific)

Scenario: Place detail
  Person 1: Birth "London"
  Person 2: Birth "London, Middlesex, England"
  → Resolution: Keep "London, Middlesex, England" (more detailed)

Scenario: Sex conflict
  Person 1: Sex = 'M'
  Person 2: Sex = 'F'
  → Resolution: Flag for MANUAL REVIEW (strong conflict)
```

## Usage

### Command-Line Interface

```bash
# Find duplicates (dry-run, no changes)
python find_and_merge_duplicates.py /path/to/database.rmtree --dry-run

# Find duplicates with custom confidence threshold
python find_and_merge_duplicates.py /path/to/database.rmtree --dry-run --min-confidence 70

# Auto-merge high-confidence duplicates (≥90%)
python find_and_merge_duplicates.py /path/to/database.rmtree --auto-merge

# Interactive mode (review medium-confidence matches)
python find_and_merge_duplicates.py /path/to/database.rmtree --interactive

# Find duplicates for specific persons
python find_and_merge_duplicates.py /path/to/database.rmtree --person-ids 123,456,789 --dry-run

# Custom auto-merge threshold
python find_and_merge_duplicates.py /path/to/database.rmtree --auto-merge --auto-threshold 85
```

### Python API

```python
from gedmerge.rootsmagic.adapter import RootsMagicDatabase
from gedmerge.matching import PersonMatcher
from gedmerge.merge import PersonMerger, MergeStrategy

# Open database
db = RootsMagicDatabase('/path/to/database.rmtree')

# Find duplicates
matcher = PersonMatcher(db, min_confidence=60.0)
matches = matcher.find_duplicates(limit=100)

# Display matches
for match in matches:
    print(f"Match: {match.confidence:.1f}%")
    print(f"  Person 1: {match.person1_id}")
    print(f"  Person 2: {match.person2_id}")

# Merge duplicates
merger = PersonMerger(db, strategy=MergeStrategy.INTERACTIVE)
results = merger.merge_candidates(matches, auto_merge_threshold=90.0)

# Check results
for result in results:
    if result.success:
        print(f"✓ Merged {result.removed_person_id} into {result.merged_person_id}")
    else:
        print(f"✗ Failed: {result.errors}")

db.close()
```

## Recommended Workflow

### Phase 1: Preprocessing (BEFORE duplicate detection)

Run these scripts first to clean your data:

1. **`preprocess_names_for_matching.py`**
   - Apply NN convention for missing given names
   - Remove placeholder surnames
   - Normalize whitespace

2. **`analyze_name_structure.py`**
   - Detect and separate language variants
   - Set language codes on names
   - Fix title/honorific placement

3. **`cleanup_unnamed_people.py`**
   - Remove true placeholder persons
   - Flag "MRS" persons for review

### Phase 2: Duplicate Detection (THIS SYSTEM)

4. **`find_and_merge_duplicates.py`**
   - Find potential duplicates
   - Review and merge duplicates

### Phase 3: Post-Merge Review

5. **Manual review** of flagged conflicts
6. **Quality check** of merged records
7. **Backup verification**

## Best Practices

### Before Running

1. **BACKUP YOUR DATABASE**
   - Always work on a copy
   - Keep original untouched

2. **Run Preprocessing First**
   - Clean data produces better matches
   - Reduces false positives

3. **Start with Dry-Run**
   - Review match quality
   - Adjust confidence threshold if needed

### During Merging

1. **Use Interactive Mode First**
   - Review medium-confidence matches
   - Build confidence in the system

2. **Monitor Conflict Flags**
   - Pay attention to warnings
   - Investigate sex conflicts immediately

3. **Merge in Batches**
   - Don't merge everything at once
   - Verify results incrementally

### After Merging

1. **Verify Results**
   - Check merged records in RootsMagic
   - Validate family relationships
   - Review sources and citations

2. **Document Changes**
   - Keep merge logs
   - Note any manual corrections needed

## Multilingual Support

### Language Detection

The system automatically detects languages based on name patterns:

```python
# French names
"Jean", "Marie", "Pierre", "Jacques", "François", "Marguerite"

# German names
"Wilhelm", "Friedrich", "Heinrich", "Johann", "Margarethe", "Katharina"

# Language markers in names
"dit" → French ("called")
"genannt" → German ("named")
"detto" → Italian ("called")
"aka" → English
```

### Handling Multilingual Duplicates

Example:
```
Person 1: "Wilhelm /Schmidt/" [de]
Person 2: "William /Smith/" [en]

Phonetic Match:
  Wilhelm → WLM (Metaphone)
  William → WLM (Metaphone)
  Schmidt → XMT (Metaphone)
  Smith   → XMT (Metaphone)

Result: HIGH phonetic match
Action: Keep both as language variants
```

## Performance

### Speed

- **Small databases** (<1,000 persons): Seconds
- **Medium databases** (1,000-10,000 persons): Minutes
- **Large databases** (>10,000 persons): May take hours

### Optimization Tips

1. Use `--person-ids` to check specific persons
2. Use `--limit` to process matches in batches
3. Run on a local copy for faster I/O
4. Increase `--min-confidence` to reduce matches

## Troubleshooting

### No Matches Found

- Lower `--min-confidence` threshold (try 50)
- Verify preprocessing was run
- Check that names have Metaphone fields populated

### Too Many False Positives

- Raise `--min-confidence` threshold (try 70-75)
- Review match score breakdown
- Check for data quality issues

### Merge Failures

- Check database permissions
- Verify database not open in RootsMagic
- Review error messages in output
- Check transaction logs

### Sex Conflicts

- Investigate immediately (may indicate wrong match)
- Verify in RootsMagic UI
- Manually resolve before merging

## Testing

Run the test suite:

```bash
cd GedMerge
pytest tests/test_matcher.py -v
pytest tests/test_merger.py -v
```

## Architecture

```
GedMerge/
├── gedmerge/
│   ├── matching/
│   │   ├── matcher.py          # PersonMatcher class
│   │   └── scorer.py           # MatchScorer, confidence scoring
│   │
│   ├── merge/
│   │   ├── merger.py           # PersonMerger class
│   │   └── conflict_resolver.py # Conflict resolution logic
│   │
│   ├── rootsmagic/
│   │   ├── models.py           # RMPerson, RMName, RMEvent
│   │   └── adapter.py          # Database operations
│   │
│   └── core/
│       ├── person.py           # Person data model
│       └── place.py            # Multilingual places
│
└── tests/
    ├── test_matcher.py
    └── test_merger.py

Scripts:
- find_and_merge_duplicates.py  # Main CLI tool
```

## Dependencies

- **python-gedcom**: GEDCOM file parsing
- **rapidfuzz**: Fast fuzzy string matching
- **phonetics**: Metaphone phonetic encoding
- **sqlite3**: RootsMagic database (built-in)

## License

Part of the GedMerge genealogy data management toolkit.

## Future Enhancements

- [ ] Machine learning for improved matching
- [ ] Bulk merge operations
- [ ] Undo/rollback capability
- [ ] Visual diff view for merge review
- [ ] Export merge reports
- [ ] Integration with GEDCOM import/export
- [ ] Support for more languages (Chinese, Arabic, Hebrew)
- [ ] Place name standardization
- [ ] Date range matching (circa dates)
