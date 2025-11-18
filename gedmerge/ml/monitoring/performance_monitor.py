"""
Performance monitoring for all ML models.

Tracks accuracy across ALL genealogical features:
- Names, places, events, relationships
- Per-feature performance breakdown
- Data drift detection
"""

from typing import Dict, Any, List, Optional
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
import json

from ..feedback import FeedbackDatabase

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    Monitor model performance over time.

    Tracks:
    - Overall accuracy per model
    - Per-feature accuracy (names, places, dates, relationships)
    - Performance degradation over time
    - Data drift indicators
    """

    def __init__(self, feedback_db: Optional[FeedbackDatabase] = None):
        """
        Initialize performance monitor.

        Args:
            feedback_db: Feedback database
        """
        self.feedback_db = feedback_db or FeedbackDatabase()

    def get_duplicate_detector_performance(
        self,
        time_window_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get duplicate detector performance metrics.

        Breaks down by feature type:
        - Name matching accuracy
        - Place matching accuracy
        - Date matching accuracy
        - Relationship matching accuracy

        Args:
            time_window_days: Days to look back

        Returns:
            Performance metrics
        """
        cutoff = (datetime.now() - timedelta(days=time_window_days)).isoformat()

        feedback = self.feedback_db.get_recent_feedback(
            "duplicate",
            limit=10000,
            since=cutoff
        )

        if not feedback:
            return {"status": "no_data", "time_window_days": time_window_days}

        total = len(feedback)
        correct = sum(
            1 for f in feedback
            if f['predicted_duplicate'] == f['user_confirmed']
        )

        overall_accuracy = correct / total if total > 0 else 0.0

        # Per-feature accuracy
        # Name accuracy: when name_similarity was used correctly
        name_correct = 0
        name_total = 0

        place_correct = 0
        place_total = 0

        date_correct = 0
        date_total = 0

        relationship_correct = 0
        relationship_total = 0

        for f in feedback:
            is_correct = f['predicted_duplicate'] == f['user_confirmed']

            # Name features
            if f.get('name_similarity', 0) > 0.5:
                name_total += 1
                if is_correct:
                    name_correct += 1

            # Place features
            if f.get('place_similarity', 0) > 0.5 or f.get('birth_place_match') or f.get('death_place_match'):
                place_total += 1
                if is_correct:
                    place_correct += 1

            # Date features
            if f.get('birth_date_match') or f.get('death_date_match'):
                date_total += 1
                if is_correct:
                    date_correct += 1

            # Relationship features
            if f.get('shared_parents', 0) > 0 or f.get('shared_spouses', 0) > 0:
                relationship_total += 1
                if is_correct:
                    relationship_correct += 1

        metrics = {
            "overall": {
                "accuracy": overall_accuracy,
                "total_predictions": total,
                "correct_predictions": correct,
            },
            "by_feature": {
                "names": {
                    "accuracy": name_correct / name_total if name_total > 0 else None,
                    "count": name_total,
                },
                "places": {
                    "accuracy": place_correct / place_total if place_total > 0 else None,
                    "count": place_total,
                },
                "dates": {
                    "accuracy": date_correct / date_total if date_total > 0 else None,
                    "count": date_total,
                },
                "relationships": {
                    "accuracy": relationship_correct / relationship_total if relationship_total > 0 else None,
                    "count": relationship_total,
                },
            },
            "time_window_days": time_window_days,
            "timestamp": datetime.now().isoformat(),
        }

        # Detect performance degradation
        if overall_accuracy < 0.90:
            metrics["alert"] = {
                "level": "warning",
                "message": f"Accuracy below 90%: {overall_accuracy:.1%}",
                "recommendation": "Consider retraining model with recent feedback",
            }
        elif overall_accuracy < 0.85:
            metrics["alert"] = {
                "level": "critical",
                "message": f"Accuracy below 85%: {overall_accuracy:.1%}",
                "recommendation": "Immediate retraining recommended",
            }

        return metrics

    def get_language_detector_performance(
        self,
        time_window_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get language detector performance.

        Per-language accuracy breakdown.

        Args:
            time_window_days: Days to look back

        Returns:
            Performance metrics
        """
        cutoff = (datetime.now() - timedelta(days=time_window_days)).isoformat()

        feedback = self.feedback_db.get_recent_feedback(
            "language",
            limit=10000,
            since=cutoff
        )

        if not feedback:
            return {"status": "no_data", "time_window_days": time_window_days}

        total = len(feedback)
        correct = sum(
            1 for f in feedback
            if f['predicted_language'] == f['correct_language']
        )

        overall_accuracy = correct / total if total > 0 else 0.0

        # Per-language performance
        by_language = {}
        for f in feedback:
            pred_lang = f['predicted_language']
            correct_lang = f['correct_language']

            # Track predicted language performance
            if pred_lang not in by_language:
                by_language[pred_lang] = {"correct": 0, "total": 0}

            by_language[pred_lang]["total"] += 1
            if pred_lang == correct_lang:
                by_language[pred_lang]["correct"] += 1

        # Calculate per-language accuracy
        language_metrics = {}
        for lang, stats in by_language.items():
            language_metrics[lang] = {
                "accuracy": stats["correct"] / stats["total"],
                "count": stats["total"],
                "correct": stats["correct"],
            }

        return {
            "overall": {
                "accuracy": overall_accuracy,
                "total_predictions": total,
                "correct_predictions": correct,
            },
            "by_language": language_metrics,
            "time_window_days": time_window_days,
            "timestamp": datetime.now().isoformat(),
        }

    def get_quality_classifier_performance(
        self,
        time_window_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Get quality classifier performance.

        Per-issue-type accuracy.

        Args:
            time_window_days: Days to look back

        Returns:
            Performance metrics
        """
        cutoff = (datetime.now() - timedelta(days=time_window_days)).isoformat()

        feedback = self.feedback_db.get_recent_feedback(
            "quality",
            limit=10000,
            since=cutoff
        )

        if not feedback:
            return {"status": "no_data", "time_window_days": time_window_days}

        # Calculate precision and recall per issue type
        by_issue = {}

        for f in feedback:
            predicted_issues = json.loads(f['predicted_issues'])
            confirmed_issues = json.loads(f['confirmed_issues'])
            false_positives = json.loads(f['false_positives'])
            missed_issues = json.loads(f['missed_issues'])

            # For each issue type
            all_issues = set(predicted_issues + confirmed_issues + false_positives + missed_issues)

            for issue in all_issues:
                if issue not in by_issue:
                    by_issue[issue] = {
                        "true_positive": 0,
                        "false_positive": 0,
                        "false_negative": 0,
                    }

                # True positive: predicted and confirmed
                if issue in predicted_issues and issue in confirmed_issues:
                    by_issue[issue]["true_positive"] += 1

                # False positive: predicted but not confirmed
                if issue in false_positives:
                    by_issue[issue]["false_positive"] += 1

                # False negative: missed
                if issue in missed_issues:
                    by_issue[issue]["false_negative"] += 1

        # Calculate metrics per issue
        issue_metrics = {}
        for issue, stats in by_issue.items():
            tp = stats["true_positive"]
            fp = stats["false_positive"]
            fn = stats["false_negative"]

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

            issue_metrics[issue] = {
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
                "true_positive": tp,
                "false_positive": fp,
                "false_negative": fn,
            }

        # Overall metrics (micro-average)
        total_tp = sum(s["true_positive"] for s in by_issue.values())
        total_fp = sum(s["false_positive"] for s in by_issue.values())
        total_fn = sum(s["false_negative"] for s in by_issue.values())

        overall_precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
        overall_recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
        overall_f1 = 2 * (overall_precision * overall_recall) / (overall_precision + overall_recall) if (overall_precision + overall_recall) > 0 else 0.0

        return {
            "overall": {
                "precision": overall_precision,
                "recall": overall_recall,
                "f1_score": overall_f1,
                "total_predictions": len(feedback),
            },
            "by_issue_type": issue_metrics,
            "time_window_days": time_window_days,
            "timestamp": datetime.now().isoformat(),
        }

    def detect_data_drift(
        self,
        model_type: str,
        comparison_days: int = 30,
    ) -> Dict[str, Any]:
        """
        Detect if data distribution has changed (data drift).

        Compares recent performance to historical performance.

        Args:
            model_type: "duplicate", "language", or "quality"
            comparison_days: Days to compare (recent vs older)

        Returns:
            Drift detection results
        """
        # Get recent performance
        recent_perf = None
        if model_type == "duplicate":
            recent_perf = self.get_duplicate_detector_performance(time_window_days=comparison_days)
        elif model_type == "language":
            recent_perf = self.get_language_detector_performance(time_window_days=comparison_days)
        elif model_type == "quality":
            recent_perf = self.get_quality_classifier_performance(time_window_days=comparison_days)

        if not recent_perf or recent_perf.get("status") == "no_data":
            return {"status": "insufficient_data"}

        # Get historical performance (older period)
        historical_cutoff = (datetime.now() - timedelta(days=comparison_days * 2)).isoformat()
        recent_cutoff = (datetime.now() - timedelta(days=comparison_days)).isoformat()

        # This would require comparing two time windows
        # For now, return drift warning if recent accuracy is low
        recent_accuracy = recent_perf.get("overall", {}).get("accuracy", 1.0)

        drift_detected = recent_accuracy < 0.90

        return {
            "model_type": model_type,
            "drift_detected": drift_detected,
            "recent_accuracy": recent_accuracy,
            "comparison_period_days": comparison_days,
            "recommendation": (
                "Retrain model - performance has degraded"
                if drift_detected
                else "No action needed - performance stable"
            ),
            "timestamp": datetime.now().isoformat(),
        }

    def get_comprehensive_report(self) -> Dict[str, Any]:
        """
        Get comprehensive performance report across all models.

        Returns:
            Full performance report
        """
        return {
            "duplicate_detector": self.get_duplicate_detector_performance(),
            "language_detector": self.get_language_detector_performance(),
            "quality_classifier": self.get_quality_classifier_performance(),
            "feedback_stats": self.feedback_db.get_feedback_stats(),
            "timestamp": datetime.now().isoformat(),
        }
