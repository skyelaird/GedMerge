"""Tests for continual learning system."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime
import numpy as np

from gedmerge.ml.feedback import (
    FeedbackDatabase,
    DuplicateFeedback,
    NameMatchFeedback,
    LanguageFeedback,
)
from gedmerge.ml.training.incremental_trainer import IncrementalTrainer
from gedmerge.ml.monitoring import PerformanceMonitor, RetrainingScheduler
from gedmerge.ml.utils import MLConfig


@pytest.fixture
def temp_feedback_db():
    """Create temporary feedback database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_feedback.db"
        db = FeedbackDatabase(db_path)
        yield db


@pytest.fixture
def ml_config_temp():
    """Create temporary ML config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = MLConfig()
        config.model_dir = Path(tmpdir) / "models"
        yield config


class TestFeedbackDatabase:
    """Test feedback database operations."""

    def test_database_creation(self, temp_feedback_db):
        """Test database is created."""
        assert temp_feedback_db.db_path.exists()

    def test_add_duplicate_feedback(self, temp_feedback_db):
        """Test adding duplicate feedback."""
        feedback = DuplicateFeedback(
            person1_id="I001",
            person2_id="I002",
            predicted_duplicate=True,
            predicted_confidence=0.87,
            user_confirmed=True,
            model_version="v1.0.0",
            timestamp=datetime.now().isoformat(),
            name_similarity=0.92,
            surname_match=True,
            given_name_match=True,
            phonetic_match=True,
            birth_place_match=True,
            death_place_match=False,
            place_similarity=0.75,
            birth_date_match=True,
            death_date_match=True,
            date_conflict=False,
            age_difference=0,
            shared_parents=2,
            shared_spouses=0,
            family_structure_match=True,
        )

        feedback_id = temp_feedback_db.add_duplicate_feedback(feedback)
        assert feedback_id > 0

    def test_add_language_feedback(self, temp_feedback_db):
        """Test adding language feedback."""
        feedback = LanguageFeedback(
            name="François Müller",
            predicted_language="de",
            predicted_confidence=0.65,
            correct_language="fr",
            timestamp=datetime.now().isoformat(),
            model_version="v1.0.0",
        )

        feedback_id = temp_feedback_db.add_language_feedback(feedback)
        assert feedback_id > 0

    def test_get_recent_feedback(self, temp_feedback_db):
        """Test retrieving recent feedback."""
        # Add some feedback
        for i in range(5):
            feedback = LanguageFeedback(
                name=f"Name{i}",
                predicted_language="en",
                predicted_confidence=0.8,
                correct_language="fr",
                timestamp=datetime.now().isoformat(),
                model_version="v1.0.0",
            )
            temp_feedback_db.add_language_feedback(feedback)

        # Retrieve
        recent = temp_feedback_db.get_recent_feedback("language", limit=10)
        assert len(recent) == 5

    def test_feedback_stats(self, temp_feedback_db):
        """Test feedback statistics."""
        # Add various types of feedback
        duplicate_fb = DuplicateFeedback(
            person1_id="I001",
            person2_id="I002",
            predicted_duplicate=True,
            predicted_confidence=0.87,
            user_confirmed=True,
            model_version="v1.0.0",
            timestamp=datetime.now().isoformat(),
            name_similarity=0.92,
            surname_match=True,
            given_name_match=True,
            phonetic_match=True,
            birth_place_match=True,
            death_place_match=False,
            place_similarity=0.75,
            birth_date_match=True,
            death_date_match=True,
            date_conflict=False,
            age_difference=0,
            shared_parents=2,
            shared_spouses=0,
            family_structure_match=True,
        )
        temp_feedback_db.add_duplicate_feedback(duplicate_fb)

        stats = temp_feedback_db.get_feedback_stats()
        assert stats["duplicate"] >= 1


class TestPerformanceMonitor:
    """Test performance monitoring."""

    def test_monitor_creation(self, temp_feedback_db):
        """Test monitor can be created."""
        monitor = PerformanceMonitor(temp_feedback_db)
        assert monitor is not None

    def test_get_performance_no_data(self, temp_feedback_db):
        """Test performance metrics with no data."""
        monitor = PerformanceMonitor(temp_feedback_db)

        perf = monitor.get_duplicate_detector_performance(time_window_days=30)
        assert perf.get("status") == "no_data"

    def test_get_performance_with_data(self, temp_feedback_db):
        """Test performance metrics with feedback data."""
        # Add some feedback
        for i in range(10):
            feedback = DuplicateFeedback(
                person1_id=f"I{i:03d}",
                person2_id=f"I{i+100:03d}",
                predicted_duplicate=True,
                predicted_confidence=0.87,
                user_confirmed=(i % 2 == 0),  # 50% accuracy
                model_version="v1.0.0",
                timestamp=datetime.now().isoformat(),
                name_similarity=0.92,
                surname_match=True,
                given_name_match=True,
                phonetic_match=True,
                birth_place_match=True,
                death_place_match=False,
                place_similarity=0.75,
                birth_date_match=True,
                death_date_match=True,
                date_conflict=False,
                age_difference=0,
                shared_parents=2,
                shared_spouses=0,
                family_structure_match=True,
            )
            temp_feedback_db.add_duplicate_feedback(feedback)

        monitor = PerformanceMonitor(temp_feedback_db)
        perf = monitor.get_duplicate_detector_performance(time_window_days=30)

        assert "overall" in perf
        assert "accuracy" in perf["overall"]
        assert 0.0 <= perf["overall"]["accuracy"] <= 1.0


class TestRetrainingScheduler:
    """Test automated retraining scheduler."""

    def test_scheduler_creation(self, temp_feedback_db):
        """Test scheduler can be created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            scheduler = RetrainingScheduler(
                feedback_db=temp_feedback_db,
                state_file=state_file
            )
            assert scheduler is not None

    def test_should_retrain_no_data(self, temp_feedback_db):
        """Test retrain decision with no data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            scheduler = RetrainingScheduler(
                feedback_db=temp_feedback_db,
                state_file=state_file
            )

            decision = scheduler.should_retrain_duplicate_detector()
            assert decision["should_retrain"] is False
            assert "reason" in decision

    def test_check_all_models(self, temp_feedback_db):
        """Test checking all models."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            scheduler = RetrainingScheduler(
                feedback_db=temp_feedback_db,
                state_file=state_file
            )

            decisions = scheduler.check_all_models()
            assert "duplicate_detector" in decisions
            assert "language_detector" in decisions


class TestIncrementalTrainer:
    """Test incremental training."""

    def test_trainer_creation(self, temp_feedback_db, ml_config_temp):
        """Test trainer can be created."""
        trainer = IncrementalTrainer(
            config=ml_config_temp,
            feedback_db=temp_feedback_db
        )
        assert trainer is not None

    def test_update_with_insufficient_data(self, temp_feedback_db, ml_config_temp):
        """Test update with insufficient feedback."""
        trainer = IncrementalTrainer(
            config=ml_config_temp,
            feedback_db=temp_feedback_db
        )

        result = trainer.update_duplicate_detector(min_new_samples=50)
        assert result["status"] == "skipped"
        assert result["reason"] == "insufficient_feedback"


def test_integration_feedback_to_retrain(temp_feedback_db, ml_config_temp):
    """Test full workflow from feedback to retraining."""
    # 1. Add feedback
    for i in range(60):  # Enough to trigger retrain
        feedback = DuplicateFeedback(
            person1_id=f"I{i:03d}",
            person2_id=f"I{i+100:03d}",
            predicted_duplicate=True,
            predicted_confidence=0.87,
            user_confirmed=True,
            model_version="v1.0.0",
            timestamp=datetime.now().isoformat(),
            name_similarity=0.92,
            surname_match=True,
            given_name_match=True,
            phonetic_match=True,
            birth_place_match=True,
            death_place_match=False,
            place_similarity=0.75,
            birth_date_match=True,
            death_date_match=True,
            date_conflict=False,
            age_difference=0,
            shared_parents=2,
            shared_spouses=0,
            family_structure_match=True,
        )
        temp_feedback_db.add_duplicate_feedback(feedback)

    # 2. Check stats
    stats = temp_feedback_db.get_feedback_stats()
    assert stats["duplicate"] >= 60

    # 3. Check if retraining needed
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = Path(tmpdir) / "state.json"
        scheduler = RetrainingScheduler(
            feedback_db=temp_feedback_db,
            state_file=state_file
        )

        decision = scheduler.should_retrain_duplicate_detector(min_new_samples=50)
        assert decision["should_retrain"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
