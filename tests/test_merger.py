"""
Tests for person merging engine.
"""

import pytest
from gedmerge.rootsmagic.models import RMPerson, RMName, RMEvent
from gedmerge.merge import PersonMerger, MergeStrategy, ConflictResolver


class TestConflictResolver:
    """Tests for ConflictResolver class."""

    def test_resolve_name_conflict_empty(self):
        """Test resolving name conflict when one is empty."""
        resolver = ConflictResolver()

        # Empty vs. value
        resolution = resolver.resolve_name_conflict("", "John")
        assert resolution.chosen == "John"
        assert "empty" in resolution.reason.lower()

        # Value vs. empty
        resolution = resolver.resolve_name_conflict("John", "")
        assert resolution.chosen == "John"
        assert "empty" in resolution.reason.lower()

    def test_resolve_name_conflict_nn(self):
        """Test resolving name conflict with NN placeholder."""
        resolver = ConflictResolver()

        # NN vs. actual name
        resolution = resolver.resolve_name_conflict("NN", "John")
        assert resolution.chosen == "John"
        assert "nn" in resolution.reason.lower()

        # Actual name vs. NN
        resolution = resolver.resolve_name_conflict("John", "nn")
        assert resolution.chosen == "John"
        assert "nn" in resolution.reason.lower()

    def test_resolve_name_conflict_both_valid(self):
        """Test resolving name conflict when both are valid."""
        resolver = ConflictResolver()

        resolution = resolver.resolve_name_conflict("John", "Jean")
        assert "John" in resolution.chosen and "Jean" in resolution.chosen
        assert "alternate" in resolution.reason.lower()

    def test_resolve_date_conflict_specificity(self):
        """Test date conflict resolution based on specificity."""
        resolver = ConflictResolver()

        # Full date vs. year only
        resolution = resolver.resolve_date_conflict("1 JAN 1900", "1900")
        assert resolution.chosen == "1 JAN 1900"
        assert "specific" in resolution.reason.lower()

        # Month+year vs. year only
        resolution = resolver.resolve_date_conflict("JAN 1900", "1900")
        assert resolution.chosen == "JAN 1900"
        assert "specific" in resolution.reason.lower()

    def test_resolve_date_conflict_empty(self):
        """Test date conflict when one is empty."""
        resolver = ConflictResolver()

        resolution = resolver.resolve_date_conflict("", "1 JAN 1900")
        assert resolution.chosen == "1 JAN 1900"

        resolution = resolver.resolve_date_conflict("1 JAN 1900", "")
        assert resolution.chosen == "1 JAN 1900"

    def test_resolve_place_conflict_detail(self):
        """Test place conflict resolution based on detail."""
        resolver = ConflictResolver()

        # More detailed vs. less detailed
        resolution = resolver.resolve_place_conflict(
            "London, England",
            "London"
        )
        assert resolution.chosen == "London, England"
        assert "detailed" in resolution.reason.lower()

        # Contains check
        resolution = resolver.resolve_place_conflict(
            "London",
            "London, England, UK"
        )
        assert resolution.chosen == "London, England, UK"

    def test_resolve_sex_conflict_unknown(self):
        """Test sex conflict when one is unknown."""
        resolver = ConflictResolver()

        # Unknown vs. definite
        resolution = resolver.resolve_sex_conflict("U", "M")
        assert resolution.chosen == "M"
        assert "unknown" in resolution.reason.lower()

        # Definite vs. unknown
        resolution = resolver.resolve_sex_conflict("F", "U")
        assert resolution.chosen == "F"

    def test_resolve_sex_conflict_mismatch(self):
        """Test sex conflict when both are different."""
        resolver = ConflictResolver()

        resolution = resolver.resolve_sex_conflict("M", "F")
        assert "manual review" in resolution.reason.lower()
        from gedmerge.merge import MergeDecision
        assert resolution.decision == MergeDecision.MANUAL_REVIEW

    def test_date_specificity_scoring(self):
        """Test date specificity calculation."""
        resolver = ConflictResolver()

        assert resolver._date_specificity("1 JAN 1900") == 3
        assert resolver._date_specificity("JAN 1900") == 2
        assert resolver._date_specificity("1900") == 1
        assert resolver._date_specificity("") == 0
        assert resolver._date_specificity("invalid") == 0


class TestPersonMerger:
    """Tests for PersonMerger class."""

    def test_select_primary_by_completeness(self):
        """Test primary selection based on data completeness."""
        person1 = RMPerson(
            person_id=1,
            sex='M',
            names=[
                RMName(name_id=1, given='John', surname='Smith'),
                RMName(name_id=2, given='Jack', surname='Smith')
            ],
            events=[
                RMEvent(event_id=1, event_type='Birth', date='1900'),
                RMEvent(event_id=2, event_type='Death', date='1980')
            ]
        )

        person2 = RMPerson(
            person_id=2,
            sex='M',
            names=[
                RMName(name_id=3, given='John', surname='Smith')
            ]
        )

        # Mock database
        from gedmerge.rootsmagic.adapter import RootsMagicDatabase
        import tempfile
        import sqlite3

        # Create temporary database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        # Create minimal schema
        conn.execute("""
            CREATE TABLE PersonTable (
                PersonID INTEGER PRIMARY KEY,
                Sex TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE NameTable (
                NameID INTEGER PRIMARY KEY,
                OwnerID INTEGER,
                Given TEXT,
                Surname TEXT
            )
        """)
        conn.commit()

        db = RootsMagicDatabase(db_path)
        merger = PersonMerger(db, strategy=MergeStrategy.AUTOMATIC)

        primary, secondary = merger._select_primary(person1, person2)

        # person1 has more data, should be primary
        assert primary.person_id == 1
        assert secondary.person_id == 2

        db.close()
        import os
        os.unlink(db_path)

    def test_merge_names_removes_duplicates(self):
        """Test that name merging removes duplicates."""
        from gedmerge.rootsmagic.adapter import RootsMagicDatabase
        import tempfile
        import sqlite3

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE PersonTable (PersonID INTEGER PRIMARY KEY, Sex TEXT)")
        conn.execute("CREATE TABLE NameTable (NameID INTEGER PRIMARY KEY, OwnerID INTEGER)")
        conn.commit()

        db = RootsMagicDatabase(db_path)
        merger = PersonMerger(db)

        names1 = [
            RMName(name_id=1, given='John', surname='Smith', language='en')
        ]

        names2 = [
            RMName(name_id=2, given='John', surname='Smith', language='en'),  # Duplicate
            RMName(name_id=3, given='Jean', surname='Smith', language='fr')   # Variant
        ]

        conflicts = []
        merged = merger._merge_names(names1, names2, conflicts)

        # Should have 2 names: English and French variant
        assert len(merged) == 2

        db.close()
        import os
        os.unlink(db_path)

    def test_merge_events_removes_duplicates(self):
        """Test that event merging removes duplicates."""
        from gedmerge.rootsmagic.adapter import RootsMagicDatabase
        import tempfile
        import sqlite3

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE PersonTable (PersonID INTEGER PRIMARY KEY, Sex TEXT)")
        conn.execute("CREATE TABLE NameTable (NameID INTEGER PRIMARY KEY)")
        conn.commit()

        db = RootsMagicDatabase(db_path)
        merger = PersonMerger(db)

        events1 = [
            RMEvent(event_id=1, event_type='Birth', date='1900', place='London')
        ]

        events2 = [
            RMEvent(event_id=2, event_type='Birth', date='1900', place='London'),  # Duplicate
            RMEvent(event_id=3, event_type='Death', date='1980', place='Paris')     # Different
        ]

        conflicts = []
        merged = merger._merge_events(events1, events2, conflicts)

        # Should have 2 events: birth and death (duplicate removed)
        assert len(merged) == 2

        db.close()
        import os
        os.unlink(db_path)

    def test_are_names_equivalent_same_language(self):
        """Test name equivalence check for same language."""
        from gedmerge.rootsmagic.adapter import RootsMagicDatabase
        import tempfile
        import sqlite3

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE PersonTable (PersonID INTEGER PRIMARY KEY)")
        conn.commit()

        db = RootsMagicDatabase(db_path)
        merger = PersonMerger(db)

        name1 = RMName(
            name_id=1,
            given='John',
            surname='Smith',
            language='en'
        )

        name2 = RMName(
            name_id=2,
            given='John',
            surname='Smith',
            language='en'
        )

        assert merger._are_names_equivalent(name1, name2) is True

        db.close()
        import os
        os.unlink(db_path)

    def test_are_names_equivalent_different_language_phonetic(self):
        """Test name equivalence for different languages using phonetics."""
        from gedmerge.rootsmagic.adapter import RootsMagicDatabase
        import tempfile
        import sqlite3

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE PersonTable (PersonID INTEGER PRIMARY KEY)")
        conn.commit()

        db = RootsMagicDatabase(db_path)
        merger = PersonMerger(db)

        name1 = RMName(
            name_id=1,
            given='Wilhelm',
            surname='Schmidt',
            language='de',
            given_mp='WLM',
            surname_mp='XMT'
        )

        name2 = RMName(
            name_id=2,
            given='William',
            surname='Smith',
            language='en',
            given_mp='WLM',  # Same phonetic
            surname_mp='XMT'  # Same phonetic
        )

        # Should be equivalent via phonetics
        assert merger._are_names_equivalent(name1, name2) is True

        db.close()
        import os
        os.unlink(db_path)
