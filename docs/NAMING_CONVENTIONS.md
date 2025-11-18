# Genealogy Naming Conventions and Preprocessing

## Overview

This document describes the naming conventions and preprocessing steps used in this genealogy database to ensure consistent data before duplicate detection.

## Naming Conventions

### 1. NN Convention for Missing Given Names

**Convention**: Use `NN` (No Name) for missing given names.

**Rationale**:
- Standard genealogy practice
- Clearly distinguishes "unknown" from "unnamed"
- Prevents database NULL issues
- Facilitates searching and sorting

**Examples**:
```
NN /Smith/           - Unknown given name, surname Smith
NN /von Bergen/      - Unknown given name with prefix
NN //                - Completely unknown name (ancient times)
```

### 2. Ancient Names (Given Name Only)

**Convention**: Store only given name, leave surname empty (or NULL).

**Rationale**:
- Historically accurate for ancient/medieval records
- Many cultures used patronymics instead of surnames
- Avoids placeholder surnames that add no information

**Examples**:
```
Eric //              - Eric (Norse, no surname)
Olaf //              - Olaf (no surname)
Constantine VII //   - Byzantine emperor (title in suffix)
```

### 3. Placeholder Surnames

**When to Remove**:
- `EndofLine` - Generic placeholder
- `Unknown` - No information
- `???` - Question marks
- `---` - Dashes

**When to PRESERVE**:
- Mother has different surname from child
  - May indicate maiden name preserved in records
  - Could help find marriage records
  - May indicate origin location/family

**Examples**:
```
REMOVE:
  NN /EndofLine/     - Placeholder parent
  John /Unknown/     - No actual surname info

PRESERVE:
  Mary /Wilson/      - Mother of "John Smith"
                       (Wilson may be her maiden name - useful!)
```

### 4. Language Codes

**Convention**: Use ISO 639-1 language codes in `NameTable.Language` field.

**Common Codes**:
- `en` - English
- `fr` - French
- `de` - German
- `it` - Italian
- `es` - Spanish
- `la` - Latin

**When to Use**:
1. **Alternate names**: ALWAYS set language code
   ```
   Primary:   Margaret /Smith/      [language: en]
   Alternate: Marguerite /Smith/    [language: fr]
   ```

2. **Language variants**: Create separate name records
   ```
   DO NOT: Margaret [Marguerite] /Smith/
   DO:     Margaret /Smith/         [language: en]
           Marguerite /Smith/       [language: fr]
   ```

3. **Multilingual families**: Specify language for each variant
   ```
   Wilhelm /Schmidt/    [language: de]
   William /Smith/      [language: en]
   Guillaume /Schmitt/  [language: fr]
   ```

**RootsMagic Compatibility**: ✅ Language codes are SAFE!
- `NameTable.Language` is a standard RootsMagic field
- RootsMagic expects and supports these codes
- Will NOT break database on load

## Preprocessing Workflow

### Phase 1: Structural Cleanup

**Purpose**: Ensure names are properly structured before matching.

**Steps**:
1. Apply NN convention for missing given names
2. Remove embedded language variants (create separate records)
3. Remove true placeholder surnames
4. Normalize whitespace and formatting

**Tool**: `preprocess_names_for_matching.py`

```bash
# Dry-run (see what would change)
python preprocess_names_for_matching.py database.rmtree --report

# Execute changes
python preprocess_names_for_matching.py database.rmtree --execute
```

### Phase 2: Language Analysis

**Purpose**: Ensure proper language codes for matching.

**Steps**:
1. Detect language from name patterns
2. Set missing language codes
3. Create separate records for embedded variants

**Tool**: `analyze_name_structure.py`

```bash
# Analyze language issues
python analyze_name_structure.py database.rmtree --check-language

# Fix embedded variants
python analyze_name_structure.py database.rmtree --fix-variants --execute
```

### Phase 3: Duplicate Detection (Future)

**Purpose**: Find potential duplicate persons.

**Requirements**:
- ✅ All names use NN convention
- ✅ Embedded variants separated
- ✅ Language codes set
- ✅ Placeholder surnames removed

**Matching Strategy**:
```
1. Metaphone matching (surname_mp, given_mp)
2. Fuzzy string matching (rapidfuzz)
3. Date proximity (birth/death within N years)
4. Place proximity (same location or nearby)
5. Relationship analysis (same parents/spouse/children)
6. Scoring system (confidence level)
```

**Tool**: `gedmerge/matching/` (to be implemented)

## Special Cases

### MRS Placeholders

**Identify**:
```
MRS /Smith/
Mrs. /Jones/
Ms /Brown/
```

**Action**:
- Flag for review
- May be merged with named person elsewhere
- Check for marriage records
- Consider mother's maiden name preservation

**Tool**: `cleanup_unnamed_people.py` handles these

### Reversed Names

**Pattern**: `Smith, John` instead of `John /Smith/`

**Action**:
- Detect comma-separated format
- Reverse to proper GEDCOM format
- Verify with context (dates, relationships)

### Titles in Wrong Fields

**Pattern**: `Sir William` in Given field

**Action**:
- Move `Sir` to Prefix field
- Keep `William` in Given field
- Preserve for proper display and sorting

## Why Preprocess Before Duplicate Detection?

**Problem**: Without preprocessing, you get false mismatches:
```
❌ "Margaret [Marguerite]" vs "Margaret" - seen as DIFFERENT
❌ "" vs "NN" - NULL vs string comparison issues
❌ "Wilhelm" vs "William" - no language context
```

**Solution**: After preprocessing, you get proper matches:
```
✅ "Margaret" [en] vs "Marguerite" [fr] - alternate name records
✅ "NN" vs "NN" - consistent convention
✅ "Wilhelm" [de] vs "William" [en] - language-aware matching
```

## Tools Summary

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `preprocess_names_for_matching.py` | Apply NN convention, remove placeholders | **FIRST** - before duplicate detection |
| `analyze_name_structure.py` | Language analysis, embedded variants | **SECOND** - after basic cleanup |
| `cleanup_unnamed_people.py` | Remove truly unnamed placeholders | **THIRD** - after identifying duplicates |
| Duplicate matcher (future) | Find and merge duplicates | **LAST** - after all preprocessing |

## Best Practices

1. **Always backup** before making changes
   ```bash
   cp database.rmtree database.rmtree.backup
   ```

2. **Use dry-run mode** first
   ```bash
   python script.py database.rmtree --report
   ```

3. **Review reports** before executing
   - Check that changes make sense
   - Verify no valuable data is lost
   - Confirm language detection accuracy

4. **Process in order**
   1. Structural cleanup (NN, placeholders)
   2. Language analysis (codes, variants)
   3. Duplicate detection (matching)
   4. Final cleanup (remove confirmed duplicates)

5. **Preserve valuable information**
   - Mother's different surname → might indicate origin
   - Alternate spellings → create separate name records
   - Historical variants → add language codes

## References

- GEDCOM 5.5.1 Specification
- RootsMagic Database Schema
- ISO 639-1 Language Codes
- Genealogy naming standards (NGS, BCG)
