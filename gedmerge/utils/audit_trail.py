"""
Audit Trail System for Database Repair Operations.

Tracks all changes made during repair operations for transparency and rollback capability.
"""

import json
import sqlite3
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
from enum import Enum


class OperationType(Enum):
    """Types of repair operations."""
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


@dataclass
class AuditEntry:
    """Single audit log entry."""
    id: Optional[int] = None
    timestamp: Optional[str] = None
    operation_type: str = ""
    table_name: str = ""
    record_id: int = 0
    field_name: str = ""
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    reason: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        if self.metadata:
            result['metadata'] = json.dumps(self.metadata)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AuditEntry':
        """Create from dictionary."""
        if 'metadata' in data and isinstance(data['metadata'], str):
            data['metadata'] = json.loads(data['metadata'])
        return cls(**data)


class AuditTrail:
    """Manages audit trail for database operations.

    The audit trail is stored in a separate SQLite database alongside the main database
    to track all repair operations without modifying the original schema.
    """

    def __init__(self, database_path: str | Path):
        """Initialize audit trail for a database.

        Args:
            database_path: Path to the main RootsMagic database
        """
        self.main_db_path = Path(database_path)

        # Create audit database path (same name with .audit.db suffix)
        self.audit_db_path = self.main_db_path.parent / f"{self.main_db_path.stem}.audit.db"

        # Initialize audit database
        self.conn = sqlite3.connect(str(self.audit_db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        """Create audit trail database schema."""
        cursor = self.conn.cursor()

        # Main audit log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT (datetime('now')),
                operation_type TEXT NOT NULL,
                table_name TEXT NOT NULL,
                record_id INTEGER NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT,
                reason TEXT,
                metadata TEXT
            )
        """)

        # Repair session table to group operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS repair_session (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TEXT NOT NULL DEFAULT (datetime('now')),
                end_time TEXT,
                operation_name TEXT NOT NULL,
                status TEXT NOT NULL,
                total_records_processed INTEGER DEFAULT 0,
                total_records_updated INTEGER DEFAULT 0,
                metadata TEXT
            )
        """)

        # Link audit entries to sessions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_audit_link (
                session_id INTEGER NOT NULL,
                audit_id INTEGER NOT NULL,
                FOREIGN KEY (session_id) REFERENCES repair_session(session_id),
                FOREIGN KEY (audit_id) REFERENCES audit_log(id),
                PRIMARY KEY (session_id, audit_id)
            )
        """)

        # Create indexes for faster querying
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_timestamp
            ON audit_log(timestamp DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_record
            ON audit_log(table_name, record_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_audit_operation
            ON audit_log(operation_type)
        """)

        self.conn.commit()

    def start_session(self, operation_name: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """Start a new repair session.

        Args:
            operation_name: Name of the repair operation (e.g., "repair_places")
            metadata: Optional metadata about the session

        Returns:
            Session ID
        """
        cursor = self.conn.cursor()

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute("""
            INSERT INTO repair_session (operation_name, status, metadata)
            VALUES (?, 'running', ?)
        """, (operation_name, metadata_json))

        self.conn.commit()
        return cursor.lastrowid

    def end_session(
        self,
        session_id: int,
        status: str = "completed",
        total_processed: int = 0,
        total_updated: int = 0
    ):
        """End a repair session.

        Args:
            session_id: The session ID to end
            status: Final status (completed, failed, partial)
            total_processed: Total records processed
            total_updated: Total records updated
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE repair_session
            SET end_time = datetime('now'),
                status = ?,
                total_records_processed = ?,
                total_records_updated = ?
            WHERE session_id = ?
        """, (status, total_processed, total_updated, session_id))

        self.conn.commit()

    def log_change(
        self,
        operation_type: OperationType | str,
        table_name: str,
        record_id: int,
        field_name: str,
        old_value: Any,
        new_value: Any,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        session_id: Optional[int] = None
    ) -> int:
        """Log a single change to the audit trail.

        Args:
            operation_type: Type of operation performed
            table_name: Name of the table modified
            record_id: ID of the record modified
            field_name: Name of the field changed
            old_value: Original value
            new_value: New value
            reason: Optional reason for the change
            metadata: Optional additional metadata
            session_id: Optional session ID to link this change to

        Returns:
            Audit entry ID
        """
        cursor = self.conn.cursor()

        # Convert operation type to string if it's an enum
        if isinstance(operation_type, OperationType):
            operation_type = operation_type.value

        # Convert values to strings for storage
        old_str = str(old_value) if old_value is not None else None
        new_str = str(new_value) if new_value is not None else None

        metadata_json = json.dumps(metadata) if metadata else None

        cursor.execute("""
            INSERT INTO audit_log (
                operation_type, table_name, record_id, field_name,
                old_value, new_value, reason, metadata
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (operation_type, table_name, record_id, field_name,
              old_str, new_str, reason, metadata_json))

        audit_id = cursor.lastrowid

        # Link to session if provided
        if session_id:
            cursor.execute("""
                INSERT INTO session_audit_link (session_id, audit_id)
                VALUES (?, ?)
            """, (session_id, audit_id))

        self.conn.commit()
        return audit_id

    def get_session_changes(self, session_id: int) -> List[AuditEntry]:
        """Get all changes for a specific session.

        Args:
            session_id: The session ID

        Returns:
            List of audit entries
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT a.*
            FROM audit_log a
            INNER JOIN session_audit_link l ON a.id = l.audit_id
            WHERE l.session_id = ?
            ORDER BY a.timestamp
        """, (session_id,))

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_record_history(self, table_name: str, record_id: int) -> List[AuditEntry]:
        """Get change history for a specific record.

        Args:
            table_name: Name of the table
            record_id: Record ID

        Returns:
            List of audit entries
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM audit_log
            WHERE table_name = ? AND record_id = ?
            ORDER BY timestamp
        """, (table_name, record_id))

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_recent_changes(self, limit: int = 100) -> List[AuditEntry]:
        """Get recent changes.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of audit entries
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT *
            FROM audit_log
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))

        return [self._row_to_entry(row) for row in cursor.fetchall()]

    def get_sessions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent repair sessions.

        Args:
            limit: Maximum number of sessions to return

        Returns:
            List of session dictionaries
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                s.*,
                COUNT(l.audit_id) as change_count
            FROM repair_session s
            LEFT JOIN session_audit_link l ON s.session_id = l.session_id
            GROUP BY s.session_id
            ORDER BY s.start_time DESC
            LIMIT ?
        """, (limit,))

        sessions = []
        for row in cursor.fetchall():
            session = dict(row)
            if session.get('metadata'):
                session['metadata'] = json.loads(session['metadata'])
            sessions.append(session)

        return sessions

    def export_session_report(self, session_id: int) -> Dict[str, Any]:
        """Export a detailed report of a session's changes.

        Args:
            session_id: The session ID

        Returns:
            Dictionary containing session info and all changes
        """
        cursor = self.conn.cursor()

        # Get session info
        cursor.execute("""
            SELECT *
            FROM repair_session
            WHERE session_id = ?
        """, (session_id,))

        session_row = cursor.fetchone()
        if not session_row:
            return None

        session = dict(session_row)
        if session.get('metadata'):
            session['metadata'] = json.loads(session['metadata'])

        # Get all changes
        changes = self.get_session_changes(session_id)

        # Group changes by table and operation type
        changes_by_table = {}
        changes_by_operation = {}

        for change in changes:
            # By table
            if change.table_name not in changes_by_table:
                changes_by_table[change.table_name] = []
            changes_by_table[change.table_name].append(change.to_dict())

            # By operation
            if change.operation_type not in changes_by_operation:
                changes_by_operation[change.operation_type] = []
            changes_by_operation[change.operation_type].append(change.to_dict())

        return {
            'session': session,
            'total_changes': len(changes),
            'changes_by_table': changes_by_table,
            'changes_by_operation': changes_by_operation,
            'all_changes': [c.to_dict() for c in changes]
        }

    def _row_to_entry(self, row: sqlite3.Row) -> AuditEntry:
        """Convert database row to AuditEntry."""
        data = dict(row)
        if data.get('metadata'):
            data['metadata'] = json.loads(data['metadata'])
        return AuditEntry.from_dict(data)

    def close(self):
        """Close the audit database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def get_audit_trail(database_path: str | Path) -> AuditTrail:
    """Get audit trail for a database.

    Args:
        database_path: Path to the main RootsMagic database

    Returns:
        AuditTrail instance
    """
    return AuditTrail(database_path)
