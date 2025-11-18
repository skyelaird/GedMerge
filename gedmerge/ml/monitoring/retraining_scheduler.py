"""
Automated retraining scheduler for continual learning.

Triggers model updates based on:
- Performance degradation
- Sufficient new feedback collected
- Scheduled intervals
- Data drift detection
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging
import json

from .performance_monitor import PerformanceMonitor
from ..training.incremental_trainer import IncrementalTrainer
from ..feedback import FeedbackDatabase

logger = logging.getLogger(__name__)


class RetrainingScheduler:
    """
    Scheduler for automated model retraining.

    Monitors performance and triggers updates when needed.
    """

    def __init__(
        self,
        feedback_db: Optional[FeedbackDatabase] = None,
        state_file: Path = Path("models/retraining_state.json"),
    ):
        """
        Initialize scheduler.

        Args:
            feedback_db: Feedback database
            state_file: File to store scheduler state
        """
        self.feedback_db = feedback_db or FeedbackDatabase()
        self.monitor = PerformanceMonitor(self.feedback_db)
        self.trainer = IncrementalTrainer(feedback_db=self.feedback_db)
        self.state_file = Path(state_file)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load scheduler state."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "last_check": None,
            "last_retrain": {},
            "retrain_count": {},
        }

    def _save_state(self):
        """Save scheduler state."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def should_retrain_duplicate_detector(
        self,
        min_accuracy: float = 0.90,
        min_new_samples: int = 50,
        min_days_since_retrain: int = 7,
    ) -> Dict[str, Any]:
        """
        Check if duplicate detector should be retrained.

        Args:
            min_accuracy: Minimum acceptable accuracy
            min_new_samples: Minimum new feedback samples
            min_days_since_retrain: Minimum days between retrains

        Returns:
            Decision with reasoning
        """
        # Check last retrain time
        last_retrain = self.state["last_retrain"].get("duplicate_detector")
        if last_retrain:
            last_retrain_date = datetime.fromisoformat(last_retrain)
            days_since = (datetime.now() - last_retrain_date).days

            if days_since < min_days_since_retrain:
                return {
                    "should_retrain": False,
                    "reason": f"Too soon since last retrain ({days_since} < {min_days_since_retrain} days)",
                }

        # Check performance
        performance = self.monitor.get_duplicate_detector_performance(time_window_days=30)

        if performance.get("status") == "no_data":
            return {
                "should_retrain": False,
                "reason": "No feedback data available",
            }

        current_accuracy = performance["overall"]["accuracy"]

        # Check if accuracy is below threshold
        if current_accuracy < min_accuracy:
            return {
                "should_retrain": True,
                "reason": f"Accuracy below threshold: {current_accuracy:.1%} < {min_accuracy:.1%}",
                "trigger": "performance_degradation",
                "current_accuracy": current_accuracy,
            }

        # Check if enough new feedback
        total_feedback = performance["overall"]["total_predictions"]
        if total_feedback >= min_new_samples:
            return {
                "should_retrain": True,
                "reason": f"Sufficient new feedback: {total_feedback} >= {min_new_samples}",
                "trigger": "new_feedback",
                "num_samples": total_feedback,
            }

        return {
            "should_retrain": False,
            "reason": "No retraining triggers met",
            "current_accuracy": current_accuracy,
            "num_samples": total_feedback,
        }

    def should_retrain_language_detector(
        self,
        min_accuracy: float = 0.90,
        min_new_samples: int = 30,
        min_days_since_retrain: int = 7,
    ) -> Dict[str, Any]:
        """Check if language detector should be retrained."""
        last_retrain = self.state["last_retrain"].get("language_detector")
        if last_retrain:
            last_retrain_date = datetime.fromisoformat(last_retrain)
            days_since = (datetime.now() - last_retrain_date).days

            if days_since < min_days_since_retrain:
                return {
                    "should_retrain": False,
                    "reason": f"Too soon since last retrain ({days_since} < {min_days_since_retrain} days)",
                }

        performance = self.monitor.get_language_detector_performance(time_window_days=30)

        if performance.get("status") == "no_data":
            return {
                "should_retrain": False,
                "reason": "No feedback data available",
            }

        current_accuracy = performance["overall"]["accuracy"]

        if current_accuracy < min_accuracy:
            return {
                "should_retrain": True,
                "reason": f"Accuracy below threshold: {current_accuracy:.1%} < {min_accuracy:.1%}",
                "trigger": "performance_degradation",
                "current_accuracy": current_accuracy,
            }

        total_feedback = performance["overall"]["total_predictions"]
        if total_feedback >= min_new_samples:
            return {
                "should_retrain": True,
                "reason": f"Sufficient new feedback: {total_feedback} >= {min_new_samples}",
                "trigger": "new_feedback",
                "num_samples": total_feedback,
            }

        return {
            "should_retrain": False,
            "reason": "No retraining triggers met",
            "current_accuracy": current_accuracy,
            "num_samples": total_feedback,
        }

    def check_all_models(self) -> Dict[str, Any]:
        """
        Check all models for retraining needs.

        Returns:
            Dictionary of decisions per model
        """
        logger.info("Checking all models for retraining needs...")

        decisions = {
            "duplicate_detector": self.should_retrain_duplicate_detector(),
            "language_detector": self.should_retrain_language_detector(),
            "quality_classifier": {
                "should_retrain": False,
                "reason": "Quality classifier updates require full retraining",
            },
        }

        # Update state
        self.state["last_check"] = datetime.now().isoformat()
        self._save_state()

        # Log summary
        needs_retrain = [
            name for name, decision in decisions.items()
            if decision.get("should_retrain", False)
        ]

        logger.info(f"Models needing retrain: {len(needs_retrain)}")
        for name in needs_retrain:
            logger.info(f"  {name}: {decisions[name]['reason']}")

        return decisions

    def auto_retrain_if_needed(self) -> Dict[str, Any]:
        """
        Automatically retrain models that need updates.

        Returns:
            Results of retraining operations
        """
        decisions = self.check_all_models()

        results = {}

        # Retrain duplicate detector if needed
        if decisions["duplicate_detector"]["should_retrain"]:
            logger.info("Auto-retraining duplicate detector...")
            try:
                result = self.trainer.update_duplicate_detector()
                results["duplicate_detector"] = result

                # Update state
                self.state["last_retrain"]["duplicate_detector"] = datetime.now().isoformat()
                count = self.state["retrain_count"].get("duplicate_detector", 0)
                self.state["retrain_count"]["duplicate_detector"] = count + 1

            except Exception as e:
                logger.error(f"Error retraining duplicate detector: {e}")
                results["duplicate_detector"] = {"status": "error", "error": str(e)}

        # Retrain language detector if needed
        if decisions["language_detector"]["should_retrain"]:
            logger.info("Auto-retraining language detector...")
            try:
                result = self.trainer.update_language_detector()
                results["language_detector"] = result

                self.state["last_retrain"]["language_detector"] = datetime.now().isoformat()
                count = self.state["retrain_count"].get("language_detector", 0)
                self.state["retrain_count"]["language_detector"] = count + 1

            except Exception as e:
                logger.error(f"Error retraining language detector: {e}")
                results["language_detector"] = {"status": "error", "error": str(e)}

        # Save state
        self._save_state()

        return {
            "decisions": decisions,
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }

    def get_retraining_schedule_status(self) -> Dict[str, Any]:
        """
        Get status of retraining schedule.

        Returns:
            Schedule status
        """
        status = {
            "last_check": self.state.get("last_check"),
            "last_retrain_by_model": self.state.get("last_retrain", {}),
            "retrain_counts": self.state.get("retrain_count", {}),
            "next_check_recommended": (
                datetime.now() + timedelta(hours=24)
            ).isoformat(),
        }

        # Add performance summary
        perf_report = self.monitor.get_comprehensive_report()
        status["current_performance"] = {
            "duplicate_detector": perf_report.get("duplicate_detector", {}).get("overall", {}),
            "language_detector": perf_report.get("language_detector", {}).get("overall", {}),
            "quality_classifier": perf_report.get("quality_classifier", {}).get("overall", {}),
        }

        return status
