# GedMerge TODO List

**Last Updated**: 2025-11-17
**Maintainer**: Development Team

## Recently Completed ✅

### Date Decoding Implementation (2025-11-17)

- ✅ Implemented RootsMagic SortDate 64-bit decoder
- ✅ Added multi-language date modifier support (French, Spanish, Italian, German, Dutch, Portuguese, Latin)
- ✅ Created comprehensive test suite for date decoder
- ✅ Decoded user-reported dates successfully:
  - `'Tum 0781'` → `BET 781` (Dutch: Tussen = Between)
  - `SortDate 6098999812545314828` → `AFT 834` (After 834 AD)
- ✅ Created audit trail system for tracking repair operations
- ✅ Fixed database connection bug in places/analyze endpoint (`db.connection` → `db.conn`)
- ✅ Created comprehensive documentation (DATE_DECODING_AND_AUDIT_TRAIL.md)

## High Priority 🔴

### 1. Integrate Date Decoder into Repair Endpoints

**Status**: Not Started
**Priority**: High
**Estimated Effort**: 4-6 hours

**Tasks**:
- [ ] Integrate decoder into `/api/repairs/events` endpoint
- [ ] Update event repair to normalize all date formats
- [ ] Add SortDate recalculation after date normalization
- [ ] Test with real database containing non-English dates
- [ ] Update API response to include date normalization statistics

**Files to Modify**:
- `gedmerge/web/api/main.py` (events repair endpoint)

**Example Code**:
```python
from ...utils.date_decoder import decode_rootsmagic_date

# In events repair
for event_id, date_str, sort_date in events:
    new_date = decode_rootsmagic_date(date_str, sort_date)
    if new_date != date_str:
        # Update date and log to audit
        ...
```

### 2. Add Audit Trail to All Repair Endpoints

**Status**: Audit system created, integration pending
**Priority**: High
**Estimated Effort**: 6-8 hours

**Tasks**:
- [ ] Integrate audit trail into `/api/repairs/places`
- [ ] Integrate audit trail into `/api/repairs/names`
- [ ] Integrate audit trail into `/api/repairs/events`
- [ ] Integrate audit trail into `/api/repairs/people`
- [ ] Update `/api/quality/repair-all` to track session ID
- [ ] Create audit trail viewer endpoints
- [ ] Test audit trail with all repair operations

**New Endpoints to Add**:
```python
GET  /api/audit/sessions              # List repair sessions
GET  /api/audit/session/{id}          # Get session details
GET  /api/audit/record/{table}/{id}   # Get record history
POST /api/audit/export/{session_id}   # Export session report
```

### 3. Fix People/Families Repair Blocking Issue

**Status**: Investigation Needed
**Priority**: High
**Estimated Effort**: 3-4 hours

**Problem**: After running events repair, people/families repair appears to be blocked.

**Investigation Steps**:
- [ ] Add detailed logging to people/families repair endpoint
- [ ] Check for database locks after events repair
- [ ] Verify transaction commit/rollback in events repair
- [ ] Test repair sequence isolation
- [ ] Check for foreign key constraint violations

**Potential Fixes**:
- [ ] Add explicit transaction cleanup between repairs
- [ ] Implement connection reset between repair operations
- [ ] Add database checkpoint after each repair
- [ ] Add timeout handling for long-running operations

**Files to Investigate**:
- `gedmerge/web/api/main.py` (repair-all, events, people endpoints)
- `gedmerge/rootsmagic/adapter.py` (transaction management)

### 4. Debug Remaining 500 Errors

**Status**: One bug fixed (db.connection), others need investigation
**Priority**: High
**Estimated Effort**: 2-3 hours

**Completed**:
- ✅ Fixed `db.connection` → `db.conn` bug in places/analyze

**Remaining Tasks**:
- [ ] Add `exc_info=True` to all error logging
- [ ] Test all repair endpoints after database connection fix
- [ ] Check for missing imports (NameParser, PlaceCleaner)
- [ ] Verify all database operations use correct connection attribute
- [ ] Add request validation to catch bad inputs early
- [ ] Create integration tests for all repair endpoints

**Enhanced Error Logging Template**:
```python
except Exception as e:
    logger.error(f"Error in {operation}: {e}", exc_info=True)
    # Consider adding:
    #   - Request context
    #   - Database path
    #   - Current record ID
    raise HTTPException(status_code=500, detail=str(e))
```

## Medium Priority 🟡

### 5. Implement Gazetteer Module

**Status**: Requirements documented, implementation needed
**Priority**: Medium
**Estimated Effort**: 20-30 hours
**Reference**: `docs/GAZETTEER_REQUIREMENTS.md`

**Phase 1: Basic Gazetteer (MVP)**

- [ ] Download GeoNames data
- [ ] Create SQLite schema for gazetteer
- [ ] Implement data loader from GeoNames
- [ ] Create basic lookup functions
- [ ] Add temporal validation support
- [ ] Implement multi-lingual name support

**Phase 2: Context-Aware Disambiguation**

- [ ] Add geographic proximity scoring
- [ ] Implement family tree context analysis
- [ ] Create place hierarchy normalization
- [ ] Add event date-based disambiguation

**Phase 3: Advanced Features**

- [ ] Integrate FamilySearch Places API
- [ ] Add historical county boundary data
- [ ] Implement machine learning disambiguation
- [ ] Create crowdsourced correction system

**Files to Create**:
- `gedmerge/gazetteer/models.py`
- `gedmerge/gazetteer/loader.py`
- `gedmerge/gazetteer/lookup.py`
- `gedmerge/gazetteer/disambiguate.py`
- `scripts/load_geonames.py`
- `tests/test_gazetteer.py`

### 6. Enhance Error Handling and Logging

**Status**: Not Started
**Priority**: Medium
**Estimated Effort**: 4-6 hours

**Tasks**:
- [ ] Add structured logging with context
- [ ] Create error reporting dashboard
- [ ] Implement retry logic for transient failures
- [ ] Add performance monitoring
- [ ] Create error notification system
- [ ] Add request tracing

**Example Structured Logging**:
```python
logger.error(
    "Repair operation failed",
    extra={
        "operation": "repair_places",
        "database": database_path,
        "session_id": session_id,
        "records_processed": count,
        "error_type": type(e).__name__,
    },
    exc_info=True
)
```

### 7. Create Audit Trail Web UI

**Status**: Not Started
**Priority**: Medium
**Estimated Effort**: 8-12 hours

**Tasks**:
- [ ] Design audit trail viewer interface
- [ ] Create session list view
- [ ] Create session detail view with change breakdown
- [ ] Add record history timeline
- [ ] Implement export functionality (CSV, JSON, PDF)
- [ ] Add search and filter capabilities
- [ ] Create rollback UI (if rollback implemented)

**UI Components Needed**:
- Session list table with filtering
- Session detail page with grouped changes
- Record history timeline
- Change diff viewer
- Export modal
- Statistics dashboard

### 8. Add Rollback Capability

**Status**: Not Started
**Priority**: Medium
**Estimated Effort**: 6-8 hours

**Tasks**:
- [ ] Design rollback algorithm
- [ ] Implement single change rollback
- [ ] Implement session rollback
- [ ] Add safety checks (prevent partial rollbacks)
- [ ] Create rollback preview
- [ ] Add rollback testing
- [ ] Document rollback limitations

**Rollback Considerations**:
- Handle cascading foreign key constraints
- Prevent rollback of changes that have been superseded
- Verify database state before rollback
- Log rollback operations in audit trail
- Support dry-run mode

### 9. Batch Date Repair Operations

**Status**: Not Started
**Priority**: Medium
**Estimated Effort**: 4-6 hours

**Tasks**:
- [ ] Create batch date normalization endpoint
- [ ] Add date validation rules
- [ ] Implement date conflict resolution
- [ ] Create date quality reporting
- [ ] Add preview before applying changes
- [ ] Support selective date repair (by date quality score)

**Features**:
- Normalize all dates in database
- Fix chronological errors (birth after death)
- Standardize date formats
- Decode all SortDates
- Report dates needing manual review

## Low Priority 🟢

### 10. Historical Calendar Conversion

**Status**: Research phase
**Priority**: Low
**Estimated Effort**: 8-12 hours

**Tasks**:
- [ ] Research Julian to Gregorian conversion needs
- [ ] Implement calendar conversion algorithms
- [ ] Add regional calendar adoption dates
- [ ] Create conversion UI
- [ ] Add conversion warnings and notes

**Calendar Systems to Support**:
- Julian calendar (before 1582)
- Gregorian calendar (after 1582)
- French Revolutionary calendar (1793-1806)
- Hebrew calendar (for Jewish genealogy)
- Islamic calendar (for Muslim genealogy)

### 11. Machine Learning Date Validation

**Status**: Not Started
**Priority**: Low
**Estimated Effort**: 15-20 hours

**Tasks**:
- [ ] Collect training data for date validation
- [ ] Train model to detect invalid dates
- [ ] Implement date prediction for missing dates
- [ ] Add confidence scoring
- [ ] Create explainability features

**ML Features**:
- Predict birth year from marriage/children dates
- Detect anachronistic dates
- Suggest date ranges based on life events
- Flag suspicious date patterns

### 12. Performance Optimization

**Status**: Not Started
**Priority**: Low
**Estimated Effort**: 6-10 hours

**Tasks**:
- [ ] Profile repair operations
- [ ] Add database indexes for common queries
- [ ] Implement batch operations
- [ ] Add connection pooling
- [ ] Cache frequently accessed data
- [ ] Optimize date decoder performance

**Optimization Targets**:
- Events repair: target < 10s for 10k events
- Places repair: target < 5s for 1k places
- Names repair: target < 15s for 10k names
- Audit logging: minimal overhead (< 5% slowdown)

## Documentation Needed 📝

### High Priority
- [ ] API documentation (OpenAPI/Swagger)
- [ ] User guide for repair operations
- [ ] Audit trail usage guide
- [ ] Date format migration guide

### Medium Priority
- [ ] Developer setup guide
- [ ] Architecture documentation
- [ ] Database schema documentation
- [ ] Testing strategy document

### Low Priority
- [ ] Performance tuning guide
- [ ] Deployment guide
- [ ] Troubleshooting guide
- [ ] Contributing guidelines

## Testing Requirements 🧪

### Unit Tests Needed
- [x] Date decoder tests (completed)
- [ ] Audit trail tests
- [ ] Repair endpoint tests
- [ ] Database adapter tests
- [ ] Name parser tests
- [ ] Place cleaner tests

### Integration Tests Needed
- [ ] End-to-end repair workflow tests
- [ ] Multi-language date handling tests
- [ ] Audit trail integration tests
- [ ] Error handling tests
- [ ] Transaction management tests

### Performance Tests Needed
- [ ] Large database repair benchmarks
- [ ] Concurrent repair operation tests
- [ ] Memory usage profiling
- [ ] Audit trail overhead measurement

## Known Issues 🐛

### Critical
1. **People/families repair blocking after events repair**
   - Status: Under investigation
   - Impact: High - blocks workflow completion
   - Workaround: Restart application between repairs

### High
2. **500 errors in some repair endpoints**
   - Status: Partially fixed (database connection bug)
   - Impact: High - prevents repair operations
   - Fix: Monitor after deploying db.conn fix

### Medium
3. **No audit trail UI**
   - Status: API implemented, UI pending
   - Impact: Medium - harder to view audit information
   - Workaround: Query .audit.db directly with SQL

4. **Date decoder flags interpretation may need refinement**
   - Status: Basic implementation working
   - Impact: Low - may miss some modifier edge cases
   - Note: Monitor actual usage and refine as needed

### Low
5. **Missing validation for date ranges**
   - Status: Not implemented
   - Impact: Low - can create logically invalid ranges
   - Example: "BET 1900 AND 1800" (backwards range)

## Future Enhancements 🚀

### Data Quality
- [ ] Duplicate detection improvements
- [ ] Smart merge suggestions
- [ ] Data consistency validation
- [ ] Reference data validation (against external sources)

### User Experience
- [ ] Progress indicators for long operations
- [ ] Undo/redo functionality
- [ ] Batch operation wizard
- [ ] Export repair reports
- [ ] Email notifications for completed repairs

### Integration
- [ ] FamilySearch API integration
- [ ] Ancestry.com data sync
- [ ] WikiTree integration
- [ ] GEDCOM import/export enhancements

### Analytics
- [ ] Data quality dashboard
- [ ] Repair statistics and trends
- [ ] Database health metrics
- [ ] Change impact analysis

## Questions / Decisions Needed ❓

1. **Training Job Status**: User mentioned "training job duplicate detector ID: 597badb7-2925-488b-bfdb-1d252d21551c"
   - [ ] Check status of this training job
   - [ ] Integrate duplicate detector with repairs
   - [ ] Test duplicate detection after date normalization

2. **Repair Order**: Should there be a recommended order for running repairs?
   - Suggested: Places → Names → Events → People/Families
   - [ ] Document recommended repair sequence
   - [ ] Add repair sequence validation

3. **SortDate Recalculation**: Should SortDates be recalculated after date normalization?
   - Pro: Ensures sorting consistency
   - Con: Modifies RootsMagic internal data
   - [ ] Research RootsMagic's expectations
   - [ ] Make configurable option

4. **Audit Trail Retention**: How long should audit logs be kept?
   - [ ] Add configurable retention policy
   - [ ] Implement audit log archival
   - [ ] Create audit log cleanup job

5. **Gazetteer Data Source**: Which source(s) to prioritize?
   - GeoNames: Free, comprehensive
   - FamilySearch: Genealogy-focused
   - Wikidata: Historical coverage
   - [ ] Evaluate data quality
   - [ ] Create loader for chosen source(s)

## Resources 📚

### Documentation
- [Date Decoding and Audit Trail](./DATE_DECODING_AND_AUDIT_TRAIL.md)
- [Gazetteer Requirements](./GAZETTEER_REQUIREMENTS.md)
- [Name Structure Issues](./NAME_STRUCTURE_ISSUES.md)
- [Validation Features](../VALIDATION_FEATURES.md)

### External References
- [RootsMagic SortDate Algorithm](https://sqlitetoolsforrootsmagic.com/Dates-SortDate-Algorithm/)
- [GEDCOM 5.5.1 Specification](https://gedcom.io/specs/ged551.pdf)
- [GeoNames](http://www.geonames.org/)
- [FamilySearch Places API](https://www.familysearch.org/developers/docs/guides/places)

### Tools
- SQLite Browser (for viewing .audit.db)
- pytest (for running tests)
- FastAPI docs (http://localhost:8000/docs when server running)

---

**Last Review**: 2025-11-17
**Next Review**: Weekly until high-priority items complete
**Owner**: Development Team
