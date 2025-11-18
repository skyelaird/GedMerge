# GedMerge Genealogy Matching Implementation Analysis

## CRITICAL FINDINGS

### Problem Summary
The genealogy matching system is incorrectly matching people born 130+ years apart due to weak date validation and missing lifespan constraints. The system uses .GED files and RootsMagic (.rmtree) databases but doesn't properly leverage family tree structure.

---

## 1. FILES RELATED TO GENEALOGY MATCHING

### Core Matching Files
- **`/home/user/Python-Scripts/GedMerge/gedmerge/matching/matcher.py`** (264 lines)
  - Main PersonMatcher class
  - Handles phonetic, fuzzy string, multilingual matching
  - Entry point: `find_duplicates()` and `find_duplicates_for_person()`

- **`/home/user/Python-Scripts/GedMerge/gedmerge/matching/scorer.py`** (518 lines)
  - MatchScorer class with confidence scoring
  - Weighted scoring: Name (35%), Phonetic (25%), Dates (20%), Places (10%), Relationships (8%), Sex (2%)
  - **CRITICAL BUG LOCATION**: `_score_dates()` method

### Database Adapter Files
- **`/home/user/Python-Scripts/GedMerge/gedmerge/rootsmagic/adapter.py`** (769 lines)
  - RootsMagicDatabase class
  - Manages SQLite connections to .rmtree files
  - Methods: `get_person()`, `get_family()`, `get_person_families_as_child()`, etc.

- **`/home/user/Python-Scripts/GedMerge/gedmerge/rootsmagic/models.py`** (353 lines)
  - RMPerson, RMName, RMEvent, RMFamily data models
  - Represents database records
  - Fields: `living` boolean, parent_id, spouse_id, sex, events[], names[]

### GEDCOM Parser
- **`/home/user/Python-Scripts/GedMerge/gedmerge/core/gedcom_parser.py`** (partial, 100 lines shown)
  - Parses .GED files to Person/Family objects
  - Handles multiple encodings
  - Creates intermediate data structures

### Core Data Models
- **`/home/user/Python-Scripts/GedMerge/gedmerge/core/person.py`** (204 lines)
  - GEDCOM-based Person class (different from RMPerson)
  - Methods: `get_birth_year()`, `get_death_year()`, `is_living()`
  - Uses Event objects with type ('BIRT', 'DEAT', etc.)

- **`/home/user/Python-Scripts/GedMerge/gedmerge/core/event.py`** (144 lines)
  - Event class with date and place info
  - Method: `get_year()` - extracts year via regex

- **`/home/user/Python-Scripts/GedMerge/gedmerge/core/family.py`** (164 lines)
  - Family class with husband_id, wife_id, children_ids
  - Methods: `get_parents()`, `has_children()`

### Merge System
- **`/home/user/Python-Scripts/GedMerge/gedmerge/merge/merger.py`** (partial read)
  - PersonMerger class with MergeStrategy enum
  - Handles merge logic

- **`/home/user/Python-Scripts/GedMerge/gedmerge/merge/conflict_resolver.py`**
  - ConflictResolver class

### Scripts
- **`/home/user/Python-Scripts/GedMerge/scripts/find_and_merge_duplicates.py`** (392 lines)
  - Main CLI tool for duplicate detection
  - Uses PersonMatcher and PersonMerger
  - Entry point for end users

---

## 2. DATE HANDLING (Birth, Marriage, Death - BMD)

### Current Implementation

#### Where Dates are Stored
1. **RootsMagic format (in rmtree database)**:
   - Stored in `EventTable` with `EventType` codes:
     - `BIRTH = 1`
     - `DEATH = 2`
     - `BURIAL = 3`
     - `MARRIAGE = 4`
     - `DIVORCE = 5`
   - Date format: String field (e.g., "15 JAN 1900", "1900", "ABT 1900")

2. **GEDCOM format (in .GED files)**:
   - Stored as Event objects with type ('BIRT', 'DEAT', 'MARR', etc.)
   - Date extracted via regex: `\b(\d{4})\b` (4-digit year only)

#### Date Extraction
**`scorer.py` lines 466-493** (`_get_event_year` method):
```python
def _get_event_year(self, person: RMPerson, event_type: int) -> Optional[int]:
    if not person.events:
        return None
    for event in person.events:
        if event.event_type == event_type and event.date:
            try:
                import re
                match = re.search(r'\b(\d{4})\b', event.date)
                if match:
                    return int(match.group(1))
            except:
                pass
    return None
```

**Problem**: Only extracts year, ignores month/day. Regex only finds 4-digit numbers.

#### Date Comparison Logic
**`scorer.py` lines 334-345** (`_compare_years` method):
```python
def _compare_years(self, year1: int, year2: int) -> float:
    diff = abs(year1 - year2)
    if diff == self.DATE_EXACT_TOLERANCE:        # 0
        return 100.0
    elif diff <= self.DATE_CLOSE_TOLERANCE:      # 2
        return 80.0
    elif diff <= self.DATE_LIKELY_TOLERANCE:     # 5
        return 50.0
    else:
        return 0.0  # DATES > 5 YEARS APART = 0% SCORE
```

#### Score Date Function (THE BUG)
**`scorer.py` lines 276-332** (`_score_dates` method):

```python
def _score_dates(self, person1, person2, result):
    scores = []
    
    # Birth dates
    birth1 = self._get_event_year(person1, 1)  # Returns None if no birth event
    birth2 = self._get_event_year(person2, 1)
    
    if birth1 and birth2:  # ONLY scores if BOTH have birth dates
        birth_score = self._compare_years(birth1, birth2)
        scores.append(birth_score)
    
    # Death dates
    death1 = self._get_event_year(person1, 2)
    death2 = self._get_event_year(person2, 2)
    
    if death1 and death2:  # ONLY scores if BOTH have death dates
        death_score = self._compare_years(death1, death2)
        scores.append(death_score)
    
    # Conflict detection
    if birth1 and birth2 and abs(birth1 - birth2) > 10:  # Only flags > 10 years
        result.has_conflicting_info = True
    if death1 and death2 and abs(death1 - death2) > 10:
        result.has_conflicting_info = True
    
    if not scores:
        return 50.0  # ⚠️ CRITICAL BUG: Returns NEUTRAL if NO dates available!
    
    return sum(scores) / len(scores)
```

### THE CORE PROBLEM
**Line 326: `return 50.0  # Neutral score if no dates available`**

When neither person has dates (or only one has dates), the date score is **50% (neutral)** instead of being penalizing.

**Example of the bug**:
- Person A: Birth 1850, no death date
- Person B: Birth 1980 (130 years later), no death date
- `_get_event_year(A, 1)` = 1850
- `_get_event_year(B, 1)` = 1980
- Should score: `_compare_years(1850, 1980)` = **0.0** (130 years apart)
- But if Person B has no birth date: `_get_event_year(B, 1)` = None
- Then the `if birth1 and birth2:` condition is FALSE, so no score appended
- Result: `scores = []` → returns **50.0** (neutral!)

---

## 3. RMTREE vs .GED FILES

### .GED Files (GEDCOM Format)
**What they are**: 
- Text-based genealogy files (GEDCOM v5.5 standard)
- Human-readable format
- Hierarchical structure with individuals (INDI) and families (FAM)
- Example path: `/home/user/Python-Scripts/GedMerge/GEDCOM/JOEL.GED`

**How they're used**:
- Parsed via `GedcomParser` class
- Converted to `Person`, `Family`, `Event` objects
- Main use: **Data import/export**, not primary storage for matching

### .rmtree Files (RootsMagic SQLite Database)
**What they are**:
- SQLite databases with RootsMagic schema
- Binary format
- Proprietary genealogy software database
- Tables: PersonTable, FamilyTable, EventTable, NameTable, PlaceTable, etc.

**How they're used**:
- **Primary database** for matching and merging operations
- Connected via `RootsMagicDatabase` adapter
- Direct SQL queries to tables
- Used by scripts like `find_and_merge_duplicates.py`

**Key Tables**:
```
PersonTable:
  - PersonID (primary key)
  - Sex (0=Unknown, 1=Male, 2=Female)
  - ParentID (links to family as child)
  - SpouseID (links to family as spouse)
  - Living (0/1 boolean)
  - IsPrivate (0/1 boolean)

FamilyTable:
  - FamilyID
  - FatherID (PersonID)
  - MotherID (PersonID)
  - ChildID (field in older schema)
  
ChildTable:
  - FamilyID
  - ChildID
  - ChildOrder
  
EventTable:
  - EventID
  - EventType (1=Birth, 2=Death, 3=Burial, 4=Marriage, 5=Divorce)
  - OwnerID (PersonID)
  - OwnerType (0=Person)
  - Date (string)
  - PlaceID

NameTable:
  - NameID
  - OwnerID (PersonID)
  - Surname
  - Given
  - Prefix, Suffix, Nickname
  - SurnameMP, GivenMP, NicknameMP (Metaphone encodings)
  - IsPrimary (0/1)
```

**Current Architecture Choice**:
The system uses **rmtree** (database) not **GED** (files) for actual duplicate detection and merging. GED files are only for initial import.

---

## 4. TREE STRUCTURE REPRESENTATION

### How Family Relationships are Currently Stored

#### In RootsMagic Database
**Person relationships**:
- Direct fields in PersonTable: `ParentID`, `SpouseID` (INCOMPLETE!)
- Family relationships via FamilyTable

**Family unit representation**:
```
FamilyTable:
  FatherID → PersonID
  MotherID → PersonID
  (then lookup children via ChildTable)
```

#### How Relationships are Used in Matching
**`scorer.py` lines 391-425** (`_score_relationships` method):
```python
def _score_relationships(self, person1, person2, result):
    # Check for shared spouses
    spouse1 = person1.spouse_id if hasattr(person1, 'spouse_id') else None
    spouse2 = person2.spouse_id if hasattr(person2, 'spouse_id') else None
    shared_spouse = (spouse1 and spouse2 and spouse1 == spouse2)
    
    # Check for shared parents
    parent1 = person1.parent_id if hasattr(person1, 'parent_id') else None
    parent2 = person2.parent_id if hasattr(person2, 'parent_id') else None
    shared_parent = (parent1 and parent2 and parent1 == parent2)
    
    score = 0.0
    if shared_parent:
        score += 60.0  # Same parents = strong indicator
        result.details['shared_parent'] = parent1
    if shared_spouse:
        score += 40.0  # Same spouse = strong indicator
        result.details['shared_spouse'] = spouse1
    
    return min(score, 100.0)
```

#### ⚠️ CRITICAL ISSUES WITH RELATIONSHIPS

**Problem 1: Incomplete Data**
- Only uses `ParentID` and `SpouseID` fields
- These are single person IDs, not sets of relationships
- Doesn't load full family trees via `get_person_families_as_child()` and `get_person_families_as_spouse()`

**Problem 2: TODOs in Code**
`matcher.py` line 404:
```python
# TODO: Load full family relationships from database
```

**Problem 3: No Ancestor/Descendant Validation**
- Never checks if Person A could be ancestor of Person B
- Never validates: Birth(Child) > Birth(Parent)
- Never validates: Birth(Parent) + ~30 years ≈ Birth(Child)
- People 130 years apart could legitimately be ancestors, but NOT siblings or spouses!

**Problem 4: Weak Conflict Detection**
- Relationship weight = only 8% of total score
- Even with same parent, could have 130-year age gap
- No checking if age gap makes biological sense

---

## 5. LIVING vs DEAD STATUS

### Where It's Stored
**`rootsmagic/models.py` line 292**:
```python
@dataclass(slots=True)
class RMPerson:
    ...
    living: bool = False  # Field from PersonTable.Living column
```

**`rootsmagic/adapter.py` line 345**:
```python
living=bool(row['Living']),  # Converts 0/1 to bool
```

**`core/person.py` lines 156-162**:
```python
def is_living(self) -> bool:
    """Determine if the person is likely still living.
    
    Returns:
        False if death event exists, True otherwise
    """
    return self.get_death_event() is None
```

### How It's Used
**Currently: NOT USED in matching at all!**

The `living` field is loaded but never checked in:
- `scorer.py` - no reference to living/dead
- `matcher.py` - no reference to living/dead
- `conflict_resolver.py` - no reference to living/dead

**Should be used for**:
- Can't match two people if one is marked living and has birth year + 100+ years ago
- Living people should have death year = None
- Dead people should have death year populated

---

## 6. LIFESPAN VALIDATION & DATE COMPARISON LOGIC

### Current Validation (Insufficient)
**`scorer.py` lines 320-323**:
```python
# Check for conflicts (dates too far apart)
if birth1 and birth2 and abs(birth1 - birth2) > 10:
    result.has_conflicting_info = True
if death1 and death2 and abs(death1 - death2) > 10:
    result.has_conflicting_info = True
```

**Problems**:
1. Threshold is TOO HIGH (10 years)
   - 10-year age gap between same-age people is already huge
   - People born 100 years apart get scored as 0% date match (correct)
   - But only conflict if > 10 years (inconsistent)

2. No maximum age validation
   - No check for "age > 120 years"
   - No check for "death before birth"
   - Documentation mentions it but it's NOT implemented

3. No minimum lifespan validation
   - No check for biological feasibility
   - No parent-child generation gaps

### What SHOULD Be Validated
From `IMPLEMENTATION_SUMMARY.md` line 137:
> "Invalid dates (death before birth, age > 120)"

This is mentioned as a ML model feature but NOT actually in scorer.py

---

## SUMMARY TABLE

| Aspect | Current Status | Issue |
|--------|---|---|
| **Date Handling** | Extracts year only | No month/day precision, misses date context |
| **Missing Dates** | Returns 50% neutral score | CRITICAL: Allows impossible matches |
| **Age Gaps** | Returns 0% if > 5 years | Correct BUT returns 50% if dates missing |
| **Conflict Detection** | Flags if > 10 years apart | Threshold too high, inconsistent |
| **Max Age Validation** | NOT IMPLEMENTED | Should reject age > 120 years |
| **Death Before Birth** | NOT CHECKED | Could allow dead < birth dates |
| **Parent-Child Relationships** | TODO (incomplete) | Doesn't load full family trees |
| **Living/Dead Status** | Loaded but UNUSED | Field exists but never checked |
| **Tree Structure** | Minimal usage | Only ParentID/SpouseID, not full family |
| **Generation Gaps** | NOT VALIDATED | 130-year gaps possible with missing dates |

---

## RECOMMENDED FIXES

### Priority 1: Fix Date Scoring Bug
**File**: `gedmerge/matching/scorer.py`
**Location**: Lines 326, 276-332
**Fix**: 
- Don't return 50% when dates missing
- Return 0% or lower score when one person has dates and other doesn't
- Add lifespan validation

### Priority 2: Load Full Family Tree
**File**: `gedmerge/matching/scorer.py`  
**Location**: Line 404 (TODO comment)
**Fix**: 
- Use `get_person_families_as_child()` and `get_person_families_as_spouse()`
- Validate parent-child generation gaps
- Check sibling relationships

### Priority 3: Add Lifespan Validation
**File**: `gedmerge/matching/scorer.py`
**New method needed**:
- Validate age between 0-120 years
- Validate death year > birth year
- Validate parent birth < child birth by ~15-60 years

### Priority 4: Use Living Status
**File**: `gedmerge/matching/scorer.py`
**Fix**: 
- Check living field
- Reconcile with death events
- Penalize "living + death year 100 years ago"

---

## FILES TO MODIFY
1. `/home/user/Python-Scripts/GedMerge/gedmerge/matching/scorer.py` (main fixes)
2. `/home/user/Python-Scripts/GedMerge/gedmerge/matching/matcher.py` (relationship loading)
3. New validation module for lifespan logic
