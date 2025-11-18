"""
Feedback collection and storage for continual learning.

Captures user feedback across ALL genealogical aspects:
- Names (given, surname, variants)
- Places (birth, death, all locations)
- Events (dates, event types)
- Relationships (family structure)
- Data quality issues
"""

import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, asdict
import json
import logging

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DuplicateFeedback:
    """Feedback on duplicate prediction."""
    person1_id: str
    person2_id: str
    predicted_duplicate: bool
    predicted_confidence: float
    user_confirmed: bool
    model_version: str
    timestamp: str

    # Detailed feature breakdown
    name_similarity: float
    surname_match: bool
    given_name_match: bool
    phonetic_match: bool

    # Place feedback
    birth_place_match: bool
    death_place_match: bool
    place_similarity: float

    # Date feedback
    birth_date_match: bool
    death_date_match: bool
    date_conflict: bool
    age_difference: Optional[int]

    # Relationship feedback
    shared_parents: int
    shared_spouses: int
    family_structure_match: bool

    # User corrections
    user_notes: Optional[str] = None
    correction_type: Optional[str] = None  # "name", "date", "place", "relationship"


@dataclass(slots=True)
class NameMatchFeedback:
    """Feedback on name matching."""
    name1: str
    name2: str
    predicted_similarity: float
    predicted_match: bool
    user_confirmed_match: bool
    timestamp: str
    model_version: str

    # Language context
    detected_language1: Optional[str] = None
    detected_language2: Optional[str] = None

    # Name components
    surname_similarity: float = 0.0
    given_name_similarity: float = 0.0

    user_notes: Optional[str] = None


@dataclass(slots=True)
class LanguageFeedback:
    """Feedback on language detection."""
    name: str
    predicted_language: str
    predicted_confidence: float
    correct_language: str
    timestamp: str
    model_version: str

    # Context
    place_context: Optional[str] = None  # Birth/death place might indicate language
    other_names: Optional[str] = None  # Other name variants for same person

    user_notes: Optional[str] = None


@dataclass(slots=True)
class QualityFeedback:
    """Feedback on data quality classification."""
    person_id: str
    predicted_issues: List[str]  # List of issue types
    confidence_scores: Dict[str, float]  # Issue -> confidence
    confirmed_issues: List[str]  # What user confirmed
    false_positives: List[str]  # Incorrectly flagged
    missed_issues: List[str]  # Issues model missed
    timestamp: str
    model_version: str

    # Issue details
    issue_details: Optional[Dict[str, Any]] = None
    user_notes: Optional[str] = None


@dataclass(slots=True)
class PlaceFeedback:
    """Feedback on place matching/standardization."""
    place1: str
    place2: str
    predicted_match: bool
    predicted_similarity: float
    user_confirmed_match: bool
    timestamp: str

    # Geographic context
    country1: Optional[str] = None
    country2: Optional[str] = None
    standardized_place1: Optional[str] = None
    standardized_place2: Optional[str] = None

    user_notes: Optional[str] = None


@dataclass(slots=True)
class EventFeedback:
    """Feedback on event matching."""
    event_type: str  # "birth", "death", "marriage", etc.
    date1: Optional[str]
    date2: Optional[str]
    place1: Optional[str]
    place2: Optional[str]
    predicted_match: bool
    user_confirmed_match: bool
    timestamp: str

    # Date precision
    date1_precision: Optional[str] = None  # "exact", "circa", "range", "year_only"
    date2_precision: Optional[str] = None

    user_notes: Optional[str] = None


class FeedbackDatabase:
    """Database for storing all types of user feedback."""

    def __init__(self, db_path: Path = Path("models/feedback.db")):
        """
        Initialize feedback database.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Duplicate feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS duplicate_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person1_id TEXT NOT NULL,
                person2_id TEXT NOT NULL,
                predicted_duplicate BOOLEAN NOT NULL,
                predicted_confidence REAL NOT NULL,
                user_confirmed BOOLEAN NOT NULL,
                model_version TEXT NOT NULL,
                timestamp TEXT NOT NULL,

                -- Name features
                name_similarity REAL,
                surname_match BOOLEAN,
                given_name_match BOOLEAN,
                phonetic_match BOOLEAN,

                -- Place features
                birth_place_match BOOLEAN,
                death_place_match BOOLEAN,
                place_similarity REAL,

                -- Date features
                birth_date_match BOOLEAN,
                death_date_match BOOLEAN,
                date_conflict BOOLEAN,
                age_difference INTEGER,

                -- Relationship features
                shared_parents INTEGER,
                shared_spouses INTEGER,
                family_structure_match BOOLEAN,

                -- User input
                user_notes TEXT,
                correction_type TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicate_timestamp ON duplicate_feedback(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicate_model_version ON duplicate_feedback(model_version)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_duplicate_user_confirmed ON duplicate_feedback(user_confirmed)")

        # Name match feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS name_match_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name1 TEXT NOT NULL,
                name2 TEXT NOT NULL,
                predicted_similarity REAL NOT NULL,
                predicted_match BOOLEAN NOT NULL,
                user_confirmed_match BOOLEAN NOT NULL,
                timestamp TEXT NOT NULL,
                model_version TEXT NOT NULL,

                detected_language1 TEXT,
                detected_language2 TEXT,
                surname_similarity REAL,
                given_name_similarity REAL,
                user_notes TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_name_match_timestamp ON name_match_feedback(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_name_match_model_version ON name_match_feedback(model_version)")

        # Language feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS language_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                predicted_language TEXT NOT NULL,
                predicted_confidence REAL NOT NULL,
                correct_language TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                model_version TEXT NOT NULL,

                place_context TEXT,
                other_names TEXT,
                user_notes TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_language_timestamp ON language_feedback(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_language_predicted ON language_feedback(predicted_language)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_language_correct ON language_feedback(correct_language)")

        # Quality feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quality_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id TEXT NOT NULL,
                predicted_issues TEXT NOT NULL,  -- JSON array
                confidence_scores TEXT NOT NULL,  -- JSON object
                confirmed_issues TEXT NOT NULL,  -- JSON array
                false_positives TEXT NOT NULL,  -- JSON array
                missed_issues TEXT NOT NULL,  -- JSON array
                timestamp TEXT NOT NULL,
                model_version TEXT NOT NULL,

                issue_details TEXT,  -- JSON object
                user_notes TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_timestamp ON quality_feedback(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_quality_person_id ON quality_feedback(person_id)")

        # Place feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS place_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                place1 TEXT NOT NULL,
                place2 TEXT NOT NULL,
                predicted_match BOOLEAN NOT NULL,
                predicted_similarity REAL NOT NULL,
                user_confirmed_match BOOLEAN NOT NULL,
                timestamp TEXT NOT NULL,

                country1 TEXT,
                country2 TEXT,
                standardized_place1 TEXT,
                standardized_place2 TEXT,
                user_notes TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_place_timestamp ON place_feedback(timestamp)")

        # Event feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                date1 TEXT,
                date2 TEXT,
                place1 TEXT,
                place2 TEXT,
                predicted_match BOOLEAN NOT NULL,
                user_confirmed_match BOOLEAN NOT NULL,
                timestamp TEXT NOT NULL,

                date1_precision TEXT,
                date2_precision TEXT,
                user_notes TEXT
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_timestamp ON event_feedback(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_type ON event_feedback(event_type)")

        # Performance metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_type TEXT NOT NULL,
                model_version TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                num_samples INTEGER
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_model_type ON performance_metrics(model_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON performance_metrics(timestamp)")

        conn.commit()
        conn.close()

        logger.info(f"Feedback database initialized at {self.db_path}")

    def add_duplicate_feedback(self, feedback: DuplicateFeedback) -> int:
        """Add duplicate detection feedback."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO duplicate_feedback (
                person1_id, person2_id, predicted_duplicate, predicted_confidence,
                user_confirmed, model_version, timestamp,
                name_similarity, surname_match, given_name_match, phonetic_match,
                birth_place_match, death_place_match, place_similarity,
                birth_date_match, death_date_match, date_conflict, age_difference,
                shared_parents, shared_spouses, family_structure_match,
                user_notes, correction_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback.person1_id, feedback.person2_id,
            feedback.predicted_duplicate, feedback.predicted_confidence,
            feedback.user_confirmed, feedback.model_version, feedback.timestamp,
            feedback.name_similarity, feedback.surname_match,
            feedback.given_name_match, feedback.phonetic_match,
            feedback.birth_place_match, feedback.death_place_match,
            feedback.place_similarity,
            feedback.birth_date_match, feedback.death_date_match,
            feedback.date_conflict, feedback.age_difference,
            feedback.shared_parents, feedback.shared_spouses,
            feedback.family_structure_match,
            feedback.user_notes, feedback.correction_type
        ))

        feedback_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Added duplicate feedback (ID: {feedback_id})")
        return feedback_id

    def add_name_match_feedback(self, feedback: NameMatchFeedback) -> int:
        """Add name matching feedback."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO name_match_feedback (
                name1, name2, predicted_similarity, predicted_match,
                user_confirmed_match, timestamp, model_version,
                detected_language1, detected_language2,
                surname_similarity, given_name_similarity, user_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback.name1, feedback.name2,
            feedback.predicted_similarity, feedback.predicted_match,
            feedback.user_confirmed_match, feedback.timestamp, feedback.model_version,
            feedback.detected_language1, feedback.detected_language2,
            feedback.surname_similarity, feedback.given_name_similarity,
            feedback.user_notes
        ))

        feedback_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Added name match feedback (ID: {feedback_id})")
        return feedback_id

    def add_language_feedback(self, feedback: LanguageFeedback) -> int:
        """Add language detection feedback."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO language_feedback (
                name, predicted_language, predicted_confidence, correct_language,
                timestamp, model_version, place_context, other_names, user_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback.name, feedback.predicted_language, feedback.predicted_confidence,
            feedback.correct_language, feedback.timestamp, feedback.model_version,
            feedback.place_context, feedback.other_names, feedback.user_notes
        ))

        feedback_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Added language feedback (ID: {feedback_id})")
        return feedback_id

    def add_quality_feedback(self, feedback: QualityFeedback) -> int:
        """Add quality classification feedback."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO quality_feedback (
                person_id, predicted_issues, confidence_scores,
                confirmed_issues, false_positives, missed_issues,
                timestamp, model_version, issue_details, user_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback.person_id,
            json.dumps(feedback.predicted_issues),
            json.dumps(feedback.confidence_scores),
            json.dumps(feedback.confirmed_issues),
            json.dumps(feedback.false_positives),
            json.dumps(feedback.missed_issues),
            feedback.timestamp, feedback.model_version,
            json.dumps(feedback.issue_details) if feedback.issue_details else None,
            feedback.user_notes
        ))

        feedback_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Added quality feedback (ID: {feedback_id})")
        return feedback_id

    def add_place_feedback(self, feedback: PlaceFeedback) -> int:
        """Add place matching feedback."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO place_feedback (
                place1, place2, predicted_match, predicted_similarity,
                user_confirmed_match, timestamp, country1, country2,
                standardized_place1, standardized_place2, user_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback.place1, feedback.place2,
            feedback.predicted_match, feedback.predicted_similarity,
            feedback.user_confirmed_match, feedback.timestamp,
            feedback.country1, feedback.country2,
            feedback.standardized_place1, feedback.standardized_place2,
            feedback.user_notes
        ))

        feedback_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Added place feedback (ID: {feedback_id})")
        return feedback_id

    def add_event_feedback(self, feedback: EventFeedback) -> int:
        """Add event matching feedback."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO event_feedback (
                event_type, date1, date2, place1, place2,
                predicted_match, user_confirmed_match, timestamp,
                date1_precision, date2_precision, user_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback.event_type, feedback.date1, feedback.date2,
            feedback.place1, feedback.place2,
            feedback.predicted_match, feedback.user_confirmed_match,
            feedback.timestamp, feedback.date1_precision,
            feedback.date2_precision, feedback.user_notes
        ))

        feedback_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Added event feedback (ID: {feedback_id})")
        return feedback_id

    def get_recent_feedback(
        self,
        feedback_type: str,
        limit: int = 100,
        since: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent feedback of a specific type.

        Args:
            feedback_type: "duplicate", "name_match", "language", "quality", "place", "event"
            limit: Maximum number of records
            since: ISO timestamp to get feedback after

        Returns:
            List of feedback records as dictionaries
        """
        table_map = {
            "duplicate": "duplicate_feedback",
            "name_match": "name_match_feedback",
            "language": "language_feedback",
            "quality": "quality_feedback",
            "place": "place_feedback",
            "event": "event_feedback",
        }

        table = table_map.get(feedback_type)
        if not table:
            raise ValueError(f"Unknown feedback type: {feedback_type}")

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if since:
            cursor.execute(
                f"SELECT * FROM {table} WHERE timestamp > ? ORDER BY timestamp DESC LIMIT ?",
                (since, limit)
            )
        else:
            cursor.execute(
                f"SELECT * FROM {table} ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            )

        rows = cursor.fetchall()
        conn.close()

        return [dict(row) for row in rows]

    def get_feedback_stats(self) -> Dict[str, Any]:
        """Get statistics about collected feedback."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {}

        # Count by type
        for table in ["duplicate_feedback", "name_match_feedback", "language_feedback",
                      "quality_feedback", "place_feedback", "event_feedback"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            stats[table.replace("_feedback", "")] = count

        # Duplicate feedback accuracy
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN predicted_duplicate = user_confirmed THEN 1 ELSE 0 END) as correct
            FROM duplicate_feedback
        """)
        row = cursor.fetchone()
        if row[0] > 0:
            stats['duplicate_accuracy'] = row[1] / row[0]

        # Name match accuracy
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN predicted_match = user_confirmed_match THEN 1 ELSE 0 END) as correct
            FROM name_match_feedback
        """)
        row = cursor.fetchone()
        if row[0] > 0:
            stats['name_match_accuracy'] = row[1] / row[0]

        # Language detection accuracy
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN predicted_language = correct_language THEN 1 ELSE 0 END) as correct
            FROM language_feedback
        """)
        row = cursor.fetchone()
        if row[0] > 0:
            stats['language_accuracy'] = row[1] / row[0]

        conn.close()

        return stats
