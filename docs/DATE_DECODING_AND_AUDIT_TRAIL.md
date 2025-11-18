# Date Decoding and Audit Trail Implementation

**Date**: 2025-11-17
**Author**: Claude AI Assistant
**Version**: 1.0

## Executive Summary

This document describes the implementation of:
1. **RootsMagic SortDate Decoder** - Decode proprietary 64-bit date formats
2. **Multi-Language Date Support** - Support for French, Spanish, Italian, German, Dutch, Portuguese, and Latin date modifiers
3. **Audit Trail System** - Comprehensive tracking of all repair operations
4. **Bug Fixes** - Critical database connection bugs in API endpoints

## Problem Statement

### Original Issues

The user reported two types of unintelligible date formats in their genealogical database:

1. **Birth**: `'Tum 0781'` (sort: 9223372036854775807)
2. **Death**: `'D.+08340000..+00000000..'` (sort: 6098999812545314828)

Additionally, there were:
- 500 errors in repair-all, places, and names API endpoints
- No audit trail for repair operations
- Missing support for non-English date modifiers

## Solution Overview

### 1. RootsMagic SortDate Decoder

**File**: `gedmerge/utils/date_decoder.py`

RootsMagic uses a proprietary 64-bit integer encoding for dates. The decoder implements the official algorithm:

#### Decoding Formula

```python
Y1 = (Ds>>49) - 10000      # Year 1
M1 = (Ds>>45) & 0xf        # Month 1 (1-12)
D1 = (Ds>>39) & 0x3f       # Day 1 (1-31)
Y2 = (Ds>>20) & 0x3fff - 10000  # Year 2 (for ranges)
M2 = (Ds>>16) & 0xf        # Month 2
D2 = (Ds>>10) & 0x3f       # Day 2
F = Ds & 0x3ff             # Flags/modifiers
```

Where:
- `Ds` = SortDate value (64-bit integer)
- `9223372036854775807` = Unknown/No date marker

#### Encoding Formula

```python
Ds = ((Y1 + 10000) << 49) +
     (M1 << 45) +
     (D1 << 39) +
     ((Y2 + 10000) << 20 if Y2 else 17178820608) +
     (M2 << 16) +
     (D2 << 10) +
     F
```

#### Example Results

From testing with user's actual data:

| Original | SortDate | Decoded GEDCOM |
|----------|----------|----------------|
| `'Tum 0781'` | 9223372036854775807 | `BET 781` |
| `'D.+08340000..'` | 6098999812545314828 | `AFT 834` |

**Explanation**:
- `Tum` is Dutch abbreviation for `Tussen` (Between) → `BET 781`
- The death SortDate decoded to year 834 AD with AFT (After) modifier

### 2. Multi-Language Date Support

The parser supports date modifiers in multiple languages:

#### Supported Languages

| Language | About | Before | After | Between |
|----------|-------|--------|-------|---------|
| **English** | ABT, ABOUT, EST | BEF, BEFORE | AFT, AFTER | BET, BETWEEN |
| **French** | VERS, ENVIRON | AVANT | APRÈS | ENTRE |
| **Spanish** | HACIA, CERCA | ANTES | DESPUÉS | ENTRE |
| **Italian** | CIRCA | PRIMA | DOPO | TRA |
| **German** | UM, ETWA | VOR | NACH | ZWISCHEN |
| **Dutch** | OMSTREEKS | VOOR | NA | TUSSEN, TUM |
| **Portuguese** | CERCA | ANTES | DEPOIS | ENTRE |
| **Latin** | CIRCA | ANTE | POST | - |

#### Normalization Examples

```python
from gedmerge.utils.date_decoder import MultiLanguageDateParser

# French
MultiLanguageDateParser.normalize_to_gedcom("Vers 1650")
# Returns: "ABT 1650"

# Italian
MultiLanguageDateParser.normalize_to_gedcom("Circa 1500")
# Returns: "ABT 1500"

# German
MultiLanguageDateParser.normalize_to_gedcom("Um 1750")
# Returns: "ABT 1750"

# Dutch - user's example
MultiLanguageDateParser.normalize_to_gedcom("Tum 0781")
# Returns: "BET 781"
```

### 3. Audit Trail System

**File**: `gedmerge/utils/audit_trail.py`

The audit trail system provides comprehensive tracking of all repair operations with:

#### Features

1. **Change Tracking**: Every modification logged with old/new values
2. **Session Management**: Group operations into repair sessions
3. **History Queries**: View changes by record, session, or operation type
4. **Export Reports**: Generate detailed reports of repair sessions
5. **Separate Database**: Audit logs stored in `.audit.db` file alongside main database

#### Database Schema

```sql
-- Main audit log
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    operation_type TEXT NOT NULL,
    table_name TEXT NOT NULL,
    record_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    metadata TEXT
);

-- Repair sessions
CREATE TABLE repair_session (
    session_id INTEGER PRIMARY KEY,
    start_time TEXT NOT NULL,
    end_time TEXT,
    operation_name TEXT NOT NULL,
    status TEXT NOT NULL,
    total_records_processed INTEGER,
    total_records_updated INTEGER,
    metadata TEXT
);

-- Link sessions to changes
CREATE TABLE session_audit_link (
    session_id INTEGER NOT NULL,
    audit_id INTEGER NOT NULL,
    PRIMARY KEY (session_id, audit_id)
);
```

#### Operation Types

```python
class OperationType(Enum):
    PLACE_STANDARDIZE = "place_standardize"
    PLACE_MERGE = "place_merge"
    NAME_REVERSE = "name_reverse"
    NAME_EXTRACT_VARIANT = "name_extract_variant"
    NAME_MOVE_PREFIX = "name_move_prefix"
    NAME_CAPITALIZE = "name_capitalize"
    EVENT_DATE_FIX = "event_date_fix"
    EVENT_DATE_STANDARDIZE = "event_date_standardize"
    EVENT_CHRONOLOGY_FIX = "event_chronology_fix"
    PERSON_RELATIONSHIP_FIX = "person_relationship_fix"
    PERSON_ORPHAN_LINK = "person_orphan_link"
    FAMILY_STRUCTURE_FIX = "family_structure_fix"
```

#### Usage Example

```python
from gedmerge.utils.audit_trail import AuditTrail, OperationType

# Create audit trail for database
audit = AuditTrail("/path/to/database.rmtree")

# Start a repair session
session_id = audit.start_session(
    operation_name="repair_places",
    metadata={"user": "admin", "reason": "standardize place names"}
)

# Log a change
audit.log_change(
    operation_type=OperationType.PLACE_STANDARDIZE,
    table_name="PlaceTable",
    record_id=123,
    field_name="Name",
    old_value="Cambridge, England, UK",
    new_value="Cambridge, Cambridgeshire, England",
    reason="Standardized place hierarchy",
    session_id=session_id
)

# End session
audit.end_session(
    session_id=session_id,
    status="completed",
    total_processed=500,
    total_updated=123
)

# Query history
record_history = audit.get_record_history("PlaceTable", 123)
session_changes = audit.get_session_changes(session_id)
recent_changes = audit.get_recent_changes(limit=100)

# Export session report
report = audit.export_session_report(session_id)
```

### 4. Bug Fixes

#### Database Connection Bug

**File**: `gedmerge/web/api/main.py` (lines 659, 664)

**Problem**:
```python
places = [row[0] for row in db.connection.execute(query).fetchall()]
```

**Fix**:
```python
places = [row[0] for row in db.conn.execute(query).fetchall()]
```

**Impact**: This bug was causing 500 errors in the `/api/places/analyze` endpoint.

## Integration Guide

### Integrating Date Decoder into Repair Endpoints

Example of how to integrate the date decoder into the events repair endpoint:

```python
from gedmerge.utils.date_decoder import decode_rootsmagic_date, MultiLanguageDateParser

@app.post("/api/repairs/events")
async def repair_events(request: RepairRequest):
    """Repair event dates with multi-language support."""
    try:
        from ...rootsmagic.adapter import RootsMagicDatabase
        from ...utils.audit_trail import AuditTrail, OperationType

        db = RootsMagicDatabase(request.database_path)
        audit = AuditTrail(request.database_path)

        # Start audit session
        session_id = audit.start_session("repair_events")

        dates_fixed = 0
        total_updated = 0

        with db.transaction():
            cursor = db.conn.cursor()

            # Get all events
            cursor.execute("""
                SELECT EventID, Date, SortDate
                FROM EventTable
            """)

            for event_id, date_str, sort_date in cursor.fetchall():
                # Decode the date
                new_date = decode_rootsmagic_date(date_str, sort_date)

                if new_date and new_date != date_str:
                    # Log the change
                    audit.log_change(
                        operation_type=OperationType.EVENT_DATE_STANDARDIZE,
                        table_name="EventTable",
                        record_id=event_id,
                        field_name="Date",
                        old_value=date_str,
                        new_value=new_date,
                        reason="Decoded RootsMagic date to GEDCOM format",
                        metadata={
                            "sort_date": sort_date,
                            "decoder": "RootsMagicDateDecoder"
                        },
                        session_id=session_id
                    )

                    # Update the date
                    cursor.execute("""
                        UPDATE EventTable
                        SET Date = ?
                        WHERE EventID = ?
                    """, (new_date, event_id))

                    dates_fixed += 1
                    total_updated += 1

        # End audit session
        audit.end_session(
            session_id=session_id,
            status="completed",
            total_updated=total_updated
        )

        return {
            "dates_fixed": dates_fixed,
            "total_updated": total_updated,
            "status": "completed",
            "audit_session_id": session_id
        }

    except Exception as e:
        logger.error(f"Error repairing events: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
```

### Adding Audit Trail to Existing Repairs

For each repair endpoint, add:

1. **Import audit trail**:
```python
from ...utils.audit_trail import AuditTrail, OperationType
```

2. **Create audit instance**:
```python
audit = AuditTrail(request.database_path)
```

3. **Start session**:
```python
session_id = audit.start_session("repair_operation_name")
```

4. **Log each change**:
```python
audit.log_change(
    operation_type=OperationType.XXX,
    table_name="TableName",
    record_id=record_id,
    field_name="FieldName",
    old_value=old,
    new_value=new,
    reason="Why this change was made",
    session_id=session_id
)
```

5. **End session**:
```python
audit.end_session(session_id, "completed", total_processed, total_updated)
```

6. **Return session ID**:
```python
return {
    ...existing_fields...,
    "audit_session_id": session_id
}
```

## Testing

### Date Decoder Tests

**File**: `tests/test_date_decoder.py`

Comprehensive tests covering:
- RootsMagic SortDate encoding/decoding
- Multi-language date parsing
- User-reported date formats
- GEDCOM normalization
- Historical dates (e.g., 781 AD)

Run tests:
```bash
python -m pytest tests/test_date_decoder.py -v
```

### Manual Testing

Test with user's actual dates:
```python
from gedmerge.utils.date_decoder import decode_rootsmagic_date

# Birth
birth = decode_rootsmagic_date('Tum 0781', 9223372036854775807)
print(birth)  # Output: "BET 781"

# Death
death = decode_rootsmagic_date('D.+08340000..+00000000..', 6098999812545314828)
print(death)  # Output: "AFT 834"
```

## API Changes

### New Audit Trail Endpoints (Recommended)

Add these endpoints to view audit information:

```python
@app.get("/api/audit/sessions")
async def get_audit_sessions(database_path: str, limit: int = 50):
    """Get recent repair sessions."""
    audit = AuditTrail(database_path)
    sessions = audit.get_sessions(limit)
    return {"sessions": sessions}

@app.get("/api/audit/session/{session_id}")
async def get_session_report(database_path: str, session_id: int):
    """Get detailed report for a session."""
    audit = AuditTrail(database_path)
    report = audit.export_session_report(session_id)
    return report

@app.get("/api/audit/record")
async def get_record_history(
    database_path: str,
    table_name: str,
    record_id: int
):
    """Get change history for a specific record."""
    audit = AuditTrail(database_path)
    history = audit.get_record_history(table_name, record_id)
    return {"history": [h.to_dict() for h in history]}
```

## Outstanding Issues

### 1. People/Families Repair Blocking

**Issue**: After running events repair, people/families repair appears blocked.

**Investigation Needed**:
- Check for database locks
- Verify transaction handling
- Check for foreign key constraints
- Review error logs

**Potential Causes**:
- Uncommitted transaction from events repair
- Database file locking issue
- Schema changes during events repair
- Missing indexes causing timeouts

**Recommended Fix**:
1. Ensure all repairs use proper transaction management
2. Add explicit transaction commit/rollback
3. Add connection pooling or connection reset between repairs
4. Add timeout handling

### 2. 500 Errors in Repair Endpoints

**Status**: Partially resolved (database connection bug fixed)

**Remaining Investigation**:
- Monitor error logs after deploying database connection fix
- Check for missing imports (NameParser)
- Verify all database operations use `db.conn` not `db.connection`
- Add better error logging with stack traces

**Recommended Enhancement**:
```python
except Exception as e:
    logger.error(f"Error in repair: {e}", exc_info=True)  # Add exc_info=True
    raise HTTPException(status_code=500, detail=str(e))
```

## Next Steps

### Immediate (Phase 1)

1. ✅ Implement RootsMagic SortDate decoder
2. ✅ Add multi-language date support
3. ✅ Create audit trail system
4. ✅ Fix database connection bug
5. ⬜ Integrate date decoder into events repair endpoint
6. ⬜ Add audit trail to all repair endpoints
7. ⬜ Test with real database
8. ⬜ Fix people/families blocking issue

### Short-term (Phase 2)

1. Add audit trail API endpoints
2. Create web UI for viewing audit trails
3. Implement audit trail export (CSV, JSON)
4. Add rollback capability based on audit trail
5. Enhance error logging in all endpoints
6. Add performance monitoring

### Long-term (Phase 3)

1. Implement gazetteer module (see GAZETTEER_REQUIREMENTS.md)
2. Add machine learning-based date validation
3. Create date conflict resolution workflow
4. Add batch date repair operations
5. Implement date range validation rules
6. Add historical calendar conversion (Julian/Gregorian)

## Files Created/Modified

### New Files

1. `gedmerge/utils/date_decoder.py` - Date decoding and multi-language support
2. `gedmerge/utils/audit_trail.py` - Audit trail system
3. `tests/test_date_decoder.py` - Comprehensive tests
4. `docs/DATE_DECODING_AND_AUDIT_TRAIL.md` - This documentation

### Modified Files

1. `gedmerge/web/api/main.py`
   - Line 659: Fixed `db.connection` → `db.conn`
   - Line 664: Fixed `db.connection` → `db.conn`

## References

1. **RootsMagic SortDate Algorithm**: https://sqlitetoolsforrootsmagic.com/Dates-SortDate-Algorithm/
2. **GEDCOM Date Format**: GEDCOM 5.5.1 Standard
3. **Multi-language Genealogy**: FamilySearch Style Guide
4. **Audit Trail Best Practices**: Database Change Tracking Patterns

## Support

For questions or issues:
1. Check this documentation
2. Review test cases in `tests/test_date_decoder.py`
3. Check audit trail in `.audit.db` file
4. Review error logs with `exc_info=True` enabled

---

**Document Version**: 1.0
**Last Updated**: 2025-11-17
**Status**: Implementation Complete, Testing In Progress
