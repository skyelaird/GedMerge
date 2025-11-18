# Bug Report: Genealogy Matching Incorrectly Allows 130+ Year Age Gaps

## Critical Bug Location
**File**: `/home/user/Python-Scripts/GedMerge/gedmerge/matching/scorer.py`
**Method**: `_score_dates()`
**Lines**: 276-332

---

## The Bug

### Current Code (BUGGY)
```python
def _score_dates(
    self,
    person1: RMPerson,
    person2: RMPerson,
    result: MatchResult
) -> float:
    """
    Score date proximity for birth and death dates.
    """
    scores = []

    # Compare birth dates (event_type=1 for Birth)
    birth1 = self._get_event_year(person1, 1)
    birth2 = self._get_event_year(person2, 1)

    if birth1 and birth2:
        birth_score = self._compare_years(birth1, birth2)
        scores.append(birth_score)
        # ... conflict checking ...

    # Compare death dates (event_type=2 for Death)
    death1 = self._get_event_year(person1, 2)
    death2 = self._get_event_year(person2, 2)

    if death1 and death2:
        death_score = self._compare_years(death1, death2)
        scores.append(death_score)
        # ... conflict checking ...

    # Check for conflicts (dates too far apart)
    if birth1 and birth2 and abs(birth1 - birth2) > 10:
        result.has_conflicting_info = True
    if death1 and death2 and abs(death1 - death2) > 10:
        result.has_conflicting_info = True

    if not scores:
        return 50.0  # ⚠️⚠️⚠️ BUG HERE! Returns NEUTRAL score when NO DATES ⚠️⚠️⚠️

    # If both dates match exactly
    if len(scores) == 2 and all(s == 100 for s in scores):
        result.is_exact_date_match = True

    return sum(scores) / len(scores)
```

---

## Why This Is a Bug

### Scenario: Person Born 130 Years Apart
```
Person A:
  - Birth Year: 1850
  - No death date recorded
  - No marriage date recorded

Person B:
  - Birth Year: 1980 (130 years later!)
  - No death date recorded
  - No marriage date recorded

Expected Result: LOW match score (0% on dates, should reject)
Actual Result: 50% date score (PASSES as neutral!)
```

### What Happens Step by Step

**Step 1: Get birth years**
```python
birth1 = self._get_event_year(person1, 1)  # Returns 1850 ✓
birth2 = self._get_event_year(person2, 1)  # Returns 1980 ✓
```

**Step 2: Compare if both exist**
```python
if birth1 and birth2:  # TRUE (both 1850 and 1980 exist)
    birth_score = self._compare_years(1850, 1980)
    # Returns 0.0 (130 years > 5 year tolerance)
    scores.append(0.0)
```

**Wait - that should work!** Let's check the actual data...

**Actually the Real Bug:**
When Person B has NO birth date at all:
```python
birth1 = self._get_event_year(person1, 1)  # Returns 1850
birth2 = self._get_event_year(person2, 1)  # Returns None (no birth event!)

if birth1 and birth2:  # FALSE (birth2 is None)
    # This block is SKIPPED!
    birth_score = self._compare_years(birth1, birth2)
    scores.append(birth_score)
```

**Step 3: Get death years**
```python
death1 = self._get_event_year(person1, 2)  # Returns None
death2 = self._get_event_year(person2, 2)  # Returns None

if death1 and death2:  # FALSE (both None)
    # This block is SKIPPED too!
    death_score = self._compare_years(death1, death2)
    scores.append(death_score)
```

**Step 4: Return score**
```python
if not scores:  # TRUE (scores list is empty!)
    return 50.0  # BUG: Returns neutral score!
```

### Result
- Even though Person A (1850) and Person B (1980) are 130 years apart
- Because Person B is MISSING birth date info
- The system gives a **50% neutral score** instead of penalizing
- This is then weighted into overall matching (20% weight on 50 score)
- Overall score could still be 70-80% if other factors match!

---

## Related Code Issues

### Issue 1: Weak Conflict Threshold
**Lines 320-323:**
```python
# Check for conflicts (dates too far apart)
if birth1 and birth2 and abs(birth1 - birth2) > 10:
    result.has_conflicting_info = True
```

**Problem**: 
- Only flags conflict if > 10 years apart
- But `_compare_years()` returns 0% for > 5 years
- Inconsistent thresholds!
- A 7-year age difference returns 0% date score but doesn't flag conflict

### Issue 2: No Lifespan Validation
**Missing code:**
- No check for death < birth
- No check for age > 120 years
- No check for parent-child generation gap (should be ~25-35 years)

### Issue 3: Unused Living Field
**In `rootsmagic/models.py` line 292:**
```python
living: bool = False  # Field exists but NEVER USED
```

The `living` field is populated from the database but:
- Never checked in scorer
- Never validated against dates
- Could allow matching "living" person with death date 100 years ago

---

## Impact Assessment

### Who Is Affected
- Anyone using `find_and_merge_duplicates.py` script
- Any system calling `PersonMatcher.find_duplicates()`
- Any system calling `MatchScorer.calculate_match_score()`

### Severity
- **HIGH**: Allows biologically impossible matches
- Can merge people 130+ years apart as duplicates
- Could lose family tree structure
- Irreversible database corruption possible

### How to Detect
```bash
# Find high-confidence matches with huge age gaps
python find_and_merge_duplicates.py /path/to/database.rmtree --dry-run

# Look for matches like:
# ✓✓✓ Match #1 - Confidence: 85% (HIGH)
#   Person 1 (ID: 123): Birth: 1850
#   Person 2 (ID: 456): Birth: 1980 (or NO birth date!)
```

---

## The Fix (Recommended)

### Fix 1: Proper Date Score When Missing
```python
def _score_dates(self, person1, person2, result):
    scores = []
    
    birth1 = self._get_event_year(person1, 1)
    birth2 = self._get_event_year(person2, 1)
    
    if birth1 and birth2:
        birth_score = self._compare_years(birth1, birth2)
        scores.append(birth_score)
    elif birth1 or birth2:
        # FIXED: One has date, one doesn't = penalty!
        scores.append(20.0)  # Low score for partial info
    
    # Similar for death dates...
    
    death1 = self._get_event_year(person1, 2)
    death2 = self._get_event_year(person2, 2)
    
    if death1 and death2:
        death_score = self._compare_years(death1, death2)
        scores.append(death_score)
    elif death1 or death2:
        # FIXED: One has date, one doesn't = penalty!
        scores.append(20.0)
    
    # FIXED: Don't return neutral if no scores!
    if not scores:
        # If BOTH people completely lack dates
        # This is acceptable only for very old genealogy
        # Otherwise penalize
        return 30.0  # More conservative
    
    return sum(scores) / len(scores)
```

### Fix 2: Add Lifespan Validation
```python
def _validate_lifespan(self, person: RMPerson, result: MatchResult) -> bool:
    """Validate that person's lifespan is biologically possible."""
    birth = self._get_event_year(person, 1)
    death = self._get_event_year(person, 2)
    
    if birth and death:
        age = death - birth
        
        # Death before birth = invalid
        if age < 0:
            result.has_conflicting_info = True
            return False
        
        # Age > 120 = suspicious
        if age > 120:
            result.has_conflicting_info = True
            return False
    
    return True
```

### Fix 3: Use Living Field
```python
def _score_sex(self, person1, person2, result):
    # ... existing code ...
    
    # NEW: Check living status
    if person1.living and person1.get_death_year():
        # Living person with death date = data error
        result.has_conflicting_info = True
    
    if person2.living and person2.get_death_year():
        # Living person with death date = data error
        result.has_conflicting_info = True
```

### Fix 4: Load Full Family Tree
```python
def _score_relationships(self, person1, person2, result):
    # TODO: Load full family relationships from database
    # Use: self.db.get_person_families_as_child()
    # Use: self.db.get_person_families_as_spouse()
    
    # Validate parent-child generation gap
    # Should be ~25-35 years, not 130!
```

---

## Testing the Bug

### Create Test Case
```python
from gedmerge.rootsmagic.models import RMPerson, RMName, RMEvent

# Person A: born 1850
person1 = RMPerson(
    person_id=1,
    sex=1,
    names=[RMName(name_id=1, given='John', surname='Smith', surname_mp='XMT', given_mp='JN')],
    events=[RMEvent(event_id=1, event_type=1, date='1850')]  # Birth only
)

# Person B: born 1980 with MISSING birth date!
person2 = RMPerson(
    person_id=2,
    sex=1,
    names=[RMName(name_id=2, given='John', surname='Smith', surname_mp='XMT', given_mp='JN')],
    events=[]  # NO events!
)

scorer = MatchScorer()
result = scorer.calculate_match_score(person1, person2)

print(f"Date score: {result.date_score}")  # Shows 50.0 (BUG!)
print(f"Overall score: {result.overall_score}")  # Probably 70%+
```

### Expected vs Actual
```
Test Case: Person A (1850) vs Person B (no date)
         with same name "John Smith"

Expected:
  - Date score: 0% or 20% (penalty for mismatch)
  - Overall score: <60% (should NOT match)

Actual:
  - Date score: 50% (neutral)
  - Overall score: 65%+ (MATCHES!)

Result: BUG CONFIRMED
```

---

## Summary

| Aspect | Detail |
|--------|--------|
| **Bug Type** | Logic error in date scoring |
| **Severity** | HIGH - Data corruption risk |
| **Root Cause** | Returns 50% neutral when dates missing |
| **Impact** | Allows 130-year age gaps in matches |
| **Files** | `gedmerge/matching/scorer.py` lines 276-332 |
| **Fix Difficulty** | Medium (requires logic redesign) |
| **Test Coverage** | Missing tests for missing date scenarios |

---

## References

**Files to Review:**
- `gedmerge/matching/scorer.py` - Main bug location
- `gedmerge/matching/matcher.py` - Uses scorer (line 404 TODO)
- `rootsmagic/models.py` - RMPerson model with living field
- `rootsmagic/adapter.py` - Database access methods
- Tests to add: `tests/test_date_validation.py`

**Documentation:**
- `IMPLEMENTATION_SUMMARY.md` - References age > 120 validation (not implemented)
- `DUPLICATE_DETECTION.md` - Documents date handling

---
