# Quick Reference: Genealogy Matching Investigation

## Key Findings (TL;DR)

### The Critical Bug
**File**: `gedmerge/matching/scorer.py` **Line 326**
```python
if not scores:
    return 50.0  # BUG: Returns neutral when dates missing!
```

**Impact**: People born 130+ years apart match as duplicates if either has missing dates.

---

## File Locations by Category

### 1. MATCHING LOGIC
| File | Lines | Purpose |
|------|-------|---------|
| `gedmerge/matching/matcher.py` | 264 | Main PersonMatcher class |
| `gedmerge/matching/scorer.py` | 518 | **MatchScorer - HAS THE BUG** |

### 2. DATABASE OPERATIONS (rmtree)
| File | Lines | Purpose |
|------|-------|---------|
| `gedmerge/rootsmagic/adapter.py` | 769 | RootsMagic SQLite adapter |
| `gedmerge/rootsmagic/models.py` | 353 | Data models (RMPerson, RMEvent, etc.) |

### 3. GEDCOM OPERATIONS (.GED)
| File | Lines | Purpose |
|------|-------|---------|
| `gedmerge/core/gedcom_parser.py` | ~300 | GEDCOM file parser |
| `gedmerge/core/person.py` | 204 | GEDCOM Person model |
| `gedmerge/core/event.py` | 144 | GEDCOM Event model |
| `gedmerge/core/family.py` | 164 | GEDCOM Family model |

### 4. MERGE OPERATIONS
| File | Lines | Purpose |
|------|-------|---------|
| `gedmerge/merge/merger.py` | ~300 | PersonMerger class |
| `gedmerge/merge/conflict_resolver.py` | ~200 | Conflict resolution |

### 5. MAIN SCRIPT
| File | Lines | Purpose |
|------|-------|---------|
| `scripts/find_and_merge_duplicates.py` | 392 | CLI tool (user-facing) |

---

## The 6 Core Issues

### Issue 1: Missing Date Penalty
**Location**: `gedmerge/matching/scorer.py:326`
**Problem**: Returns 50% neutral when both people have no dates
**Impact**: Allows 130-year age gap matches
**Severity**: CRITICAL

### Issue 2: Weak Conflict Threshold
**Location**: `gedmerge/matching/scorer.py:320-323`
**Problem**: Only flags conflict if > 10 years apart (but scoring returns 0% for > 5 years)
**Impact**: Inconsistent validation thresholds
**Severity**: HIGH

### Issue 3: No Lifespan Validation
**Location**: Missing from `scorer.py`
**Problem**: No checks for death < birth or age > 120
**Impact**: Could allow impossible lifespans
**Severity**: HIGH

### Issue 4: Incomplete Relationship Scoring
**Location**: `gedmerge/matching/scorer.py:391-425` (TODO on line 404)
**Problem**: Only checks single ParentID/SpouseID, not full family tree
**Impact**: Misses generation gap validation
**Severity**: MEDIUM

### Issue 5: Unused Living Field
**Location**: `gedmerge/rootsmagic/models.py:292`
**Problem**: Living field loaded but never used in matching
**Impact**: Can't detect living person with death year 100 years ago
**Severity**: MEDIUM

### Issue 6: Limited Tree Structure Usage
**Location**: Throughout `scorer.py`
**Problem**: Doesn't use `get_person_families_as_child()` or `get_person_families_as_spouse()`
**Impact**: Can't validate ancestor-descendant relationships
**Severity**: MEDIUM

---

## Database Schema (rmtree .sqlite)

```
PersonTable:
  PersonID → BIRTH EVENT
  Sex (0=Unknown, 1=Male, 2=Female)
  ParentID (single parent link)
  SpouseID (single spouse link)
  Living (0/1) ← NOT USED IN MATCHING!

EventTable:
  EventID
  EventType: 1=Birth, 2=Death, 3=Burial, 4=Marriage, 5=Divorce
  OwnerID → PersonID
  Date (string) → REGEX extracts year only

FamilyTable:
  FamilyID
  FatherID, MotherID
  (ChildTable links children separately)
```

---

## Date Comparison Logic

```
Scores birth/death year differences:

If diff == 0 years   → 100% match
If diff <= 2 years   → 80% match
If diff <= 5 years   → 50% match
If diff > 5 years    → 0% match
```

**Problem**: When dates are MISSING, returns 50% instead of penalizing

---

## Test Case for Bug

```
Person A: Birth 1850, Name "John Smith"
Person B: Birth 1980, Name "John Smith"
          (130 years apart!)

If Person B has NO birth date recorded:
  Expected: Low match score (<60%)
  Actual: 65-75% match score ✗
```

---

## Recommended Fixes (Priority Order)

1. **FIX LINE 326** - Change 50.0 to 30.0 or add penalty logic
2. **ADD LIFESPAN VALIDATION** - Check age 0-120, death > birth
3. **USE LIVING FIELD** - Validate living + death date combo
4. **LOAD FAMILY TREE** - Use database relationships properly
5. **LOWER CONFLICT THRESHOLD** - Make consistent with scoring
6. **ADD TESTS** - Test missing dates, edge cases

---

## Documentation Files (Generated)

These files are in the repository root:

1. **GENEALOGY_MATCHING_ANALYSIS.md** (15 KB)
   - Complete technical analysis
   - All 6 issues detailed
   - Code samples
   - Database schema
   - Recommended fixes

2. **BUG_REPORT_DATE_MATCHING.md** (10 KB)
   - Detailed bug explanation
   - Step-by-step walkthrough
   - Test case
   - Sample fixes with code
   - Impact assessment

3. **QUICK_REFERENCE_INVESTIGATION.md** (this file)
   - Quick lookup
   - File locations
   - Issue summary
   - Database schema

---

## How to Reproduce Bug

```bash
# 1. Create a genealogy database with:
#    - Person A: Born 1850, name "John Smith"
#    - Person B: Born 1980, name "John Smith" (no birth event in DB)

# 2. Run duplicate finder
python scripts/find_and_merge_duplicates.py /path/to/database.rmtree --dry-run

# 3. Look for high-confidence match with 130-year gap
#    Should NOT exist but WILL due to bug
```

---

## Key Code Snippets

### The Bug (scorer.py line 326)
```python
if not scores:
    return 50.0  # ← Returns neutral, should penalize
```

### Birth Year Extraction (scorer.py line 484)
```python
match = re.search(r'\b(\d{4})\b', event.date)  # Year only
if match:
    return int(match.group(1))
```

### Scoring Weights (scorer.py lines 65-72)
```python
WEIGHTS = {
    'name': 0.35,
    'phonetic': 0.25,
    'date': 0.20,      # ← 20% weight
    'place': 0.10,
    'relationship': 0.08,
    'sex': 0.02,
}
```

### Living Status Field (models.py line 292)
```python
living: bool = False  # ← Loaded but NEVER CHECKED
```

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Python files analyzed | 12+ |
| Total lines of code reviewed | 2,000+ |
| Critical bugs found | 1 |
| High-severity issues | 2 |
| Medium-severity issues | 3 |
| Code files with TODOs | 2 |
| Database tables involved | 5 |
| Unsused features | 2 (Living field, full family tree) |

---

## Additional Resources

- Check `IMPLEMENTATION_SUMMARY.md` - References "age > 120 validation" (not implemented)
- Check `DUPLICATE_DETECTION.md` - Documents matching algorithm
- Test files: `tests/test_matcher.py`, `tests/test_person.py`

