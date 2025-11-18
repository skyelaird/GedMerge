"""Integration tests for repair endpoints with audit trail."""

import pytest
import os
from pathlib import Path
from gedmerge.rootsmagic.adapter import RootsMagicDatabase
from gedmerge.utils.audit_trail import AuditTrail


# Test database path
TEST_DB_PATH = Path(__file__).parent.parent / "RootsMagicData" / "Joel2020.rmtree"


@pytest.fixture
def test_database():
    """Fixture to provide test database path."""
    if not TEST_DB_PATH.exists():
        pytest.skip(f"Test database not found at {TEST_DB_PATH}")
    return str(TEST_DB_PATH)


@pytest.fixture
def audit_trail(test_database):
    """Fixture to provide audit trail instance."""
    return AuditTrail(test_database)


class TestRepairEndpoints:
    """Test repair endpoints functionality."""

    def test_database_connection(self, test_database):
        """Test that we can connect to the test database."""
        with RootsMagicDatabase(test_database) as db:
            stats = db.get_stats()
            assert stats['persons'] > 0, "Database should have persons"
            assert stats['events'] > 0, "Database should have events"

    def test_audit_trail_creation(self, test_database):
        """Test audit trail database creation."""
        audit = AuditTrail(test_database)

        # Start a session
        session_id = audit.start_session("test_operation", {"test": "data"})
        assert session_id > 0, "Session ID should be positive"

        # Log a change
        audit_id = audit.log_change(
            operation_type="test_operation",
            table_name="TestTable",
            record_id=1,
            field_name="TestField",
            old_value="old",
            new_value="new",
            reason="Testing",
            session_id=session_id
        )
        assert audit_id > 0, "Audit ID should be positive"

        # End session
        audit.end_session(session_id, "completed", 10, 5)

        # Verify session was recorded
        sessions = audit.get_sessions(limit=1)
        assert len(sessions) > 0, "Should have at least one session"
        assert sessions[0]['session_id'] == session_id

    def test_date_decoder_import(self):
        """Test that date decoder can be imported."""
        from gedmerge.utils.date_decoder import (
            decode_rootsmagic_date,
            RootsMagicDateDecoder,
            MultiLanguageDateParser
        )

        # Test basic decoding
        result = decode_rootsmagic_date("15 Jan 2020", None)
        assert result == "15 Jan 2020" or result == "15 JAN 2020"

        # Test French date normalization
        decoded = MultiLanguageDateParser.parse("Vers 1850")
        if decoded:
            assert "ABT" in decoded.to_gedcom() or "1850" in decoded.to_gedcom()

    def test_database_stats(self, test_database):
        """Test getting database statistics."""
        with RootsMagicDatabase(test_database) as db:
            stats = db.get_stats()

            # Verify all expected keys are present
            expected_keys = ['persons', 'families', 'events', 'names', 'places', 'sources', 'citations', 'multimedia']
            for key in expected_keys:
                assert key in stats, f"Stats should include '{key}'"
                assert isinstance(stats[key], int), f"'{key}' should be an integer"
                assert stats[key] >= 0, f"'{key}' should be non-negative"

            print(f"\nDatabase Statistics:")
            for key, value in stats.items():
                print(f"  {key}: {value:,}")

    def test_audit_session_lifecycle(self, audit_trail):
        """Test complete audit session lifecycle."""
        # Create session
        session_id = audit_trail.start_session(
            "test_repair",
            {"database": "test.rmtree", "user": "test"}
        )

        # Log multiple changes
        for i in range(5):
            audit_trail.log_change(
                operation_type="test_change",
                table_name="PersonTable",
                record_id=i,
                field_name="Name",
                old_value=f"Old Name {i}",
                new_value=f"New Name {i}",
                reason=f"Test change {i}",
                session_id=session_id
            )

        # End session
        audit_trail.end_session(session_id, "completed", 5, 5)

        # Verify session details by getting the specific session
        sessions = audit_trail.get_sessions(limit=10)
        # Find our session by ID
        session = next((s for s in sessions if s['session_id'] == session_id), None)

        assert session is not None, "Should find the session we just created"
        assert session['status'] == "completed"
        assert session['total_records_processed'] == 5
        assert session['total_records_updated'] == 5
        assert session['end_time'] is not None

    def test_places_data_exists(self, test_database):
        """Test that places data exists in test database."""
        with RootsMagicDatabase(test_database) as db:
            cursor = db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM PlaceTable")
            place_count = cursor.fetchone()[0]

            assert place_count > 0, "Should have places in database"
            print(f"\nTest database has {place_count:,} places")

    def test_names_data_exists(self, test_database):
        """Test that names data exists in test database."""
        with RootsMagicDatabase(test_database) as db:
            cursor = db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM NameTable")
            name_count = cursor.fetchone()[0]

            assert name_count > 0, "Should have names in database"
            print(f"\nTest database has {name_count:,} names")

    def test_events_data_exists(self, test_database):
        """Test that events data exists in test database."""
        with RootsMagicDatabase(test_database) as db:
            cursor = db.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM EventTable")
            event_count = cursor.fetchone()[0]

            assert event_count > 0, "Should have events in database"

            # Check for events with dates
            cursor.execute("SELECT COUNT(*) FROM EventTable WHERE Date IS NOT NULL AND Date != ''")
            dated_events = cursor.fetchone()[0]

            print(f"\nTest database has {event_count:,} events ({dated_events:,} with dates)")

    def test_checkpoint_functionality(self, test_database):
        """Test database checkpoint functionality."""
        with RootsMagicDatabase(test_database) as db:
            # Execute checkpoint
            db.conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
            db.conn.commit()

            # Should not raise an error
            assert True


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
