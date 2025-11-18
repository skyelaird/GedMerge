"""
Continual learning API endpoints.

Supports:
- Feedback collection (names, places, events, relationships)
- Active learning queries
- Performance monitoring
- Automated retraining
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from ...ml.feedback import (
    FeedbackDatabase,
    DuplicateFeedback,
    NameMatchFeedback,
    LanguageFeedback,
    QualityFeedback,
    PlaceFeedback,
    EventFeedback,
)
from ...ml.training.incremental_trainer import IncrementalTrainer
from ...ml.active_learning import ActiveLearner
from ...ml.monitoring import PerformanceMonitor, RetrainingScheduler
from ...ml.models import (
    DuplicateDetectionModel,
    NameMatchingModel,
    LanguageDetectionModel,
    DataQualityClassifier,
)
from ...ml.utils import ModelRegistry, MLConfig

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/learning", tags=["continual_learning"])

# Initialize components
config = MLConfig()
feedback_db = FeedbackDatabase()
incremental_trainer = IncrementalTrainer(config=config, feedback_db=feedback_db)
performance_monitor = PerformanceMonitor(feedback_db=feedback_db)
scheduler = RetrainingScheduler(feedback_db=feedback_db)
registry = ModelRegistry(config.model_dir)


# Pydantic models for requests
class DuplicateFeedbackRequest(BaseModel):
    person1_id: str
    person2_id: str
    predicted_duplicate: bool
    predicted_confidence: float
    user_confirmed: bool
    model_version: str

    # Feature details
    name_similarity: float
    surname_match: bool = False
    given_name_match: bool = False
    phonetic_match: bool = False
    birth_place_match: bool = False
    death_place_match: bool = False
    place_similarity: float = 0.0
    birth_date_match: bool = False
    death_date_match: bool = False
    date_conflict: bool = False
    age_difference: Optional[int] = None
    shared_parents: int = 0
    shared_spouses: int = 0
    family_structure_match: bool = False

    user_notes: Optional[str] = None
    correction_type: Optional[str] = None


class NameMatchFeedbackRequest(BaseModel):
    name1: str
    name2: str
    predicted_similarity: float
    predicted_match: bool
    user_confirmed_match: bool
    model_version: str

    detected_language1: Optional[str] = None
    detected_language2: Optional[str] = None
    surname_similarity: float = 0.0
    given_name_similarity: float = 0.0
    user_notes: Optional[str] = None


class LanguageFeedbackRequest(BaseModel):
    name: str
    predicted_language: str
    predicted_confidence: float
    correct_language: str
    model_version: str

    place_context: Optional[str] = None
    other_names: Optional[str] = None
    user_notes: Optional[str] = None


class QualityFeedbackRequest(BaseModel):
    person_id: str
    predicted_issues: List[str]
    confidence_scores: Dict[str, float]
    confirmed_issues: List[str]
    false_positives: List[str]
    missed_issues: List[str]
    model_version: str

    issue_details: Optional[Dict[str, Any]] = None
    user_notes: Optional[str] = None


# Feedback submission endpoints
@router.post("/feedback/duplicate")
async def submit_duplicate_feedback(request: DuplicateFeedbackRequest):
    """
    Submit feedback on a duplicate detection prediction.

    Captures ALL features: names, places, dates, relationships.
    """
    try:
        feedback = DuplicateFeedback(
            person1_id=request.person1_id,
            person2_id=request.person2_id,
            predicted_duplicate=request.predicted_duplicate,
            predicted_confidence=request.predicted_confidence,
            user_confirmed=request.user_confirmed,
            model_version=request.model_version,
            timestamp=datetime.now().isoformat(),
            name_similarity=request.name_similarity,
            surname_match=request.surname_match,
            given_name_match=request.given_name_match,
            phonetic_match=request.phonetic_match,
            birth_place_match=request.birth_place_match,
            death_place_match=request.death_place_match,
            place_similarity=request.place_similarity,
            birth_date_match=request.birth_date_match,
            death_date_match=request.death_date_match,
            date_conflict=request.date_conflict,
            age_difference=request.age_difference,
            shared_parents=request.shared_parents,
            shared_spouses=request.shared_spouses,
            family_structure_match=request.family_structure_match,
            user_notes=request.user_notes,
            correction_type=request.correction_type,
        )

        feedback_id = feedback_db.add_duplicate_feedback(feedback)

        logger.info(f"Received duplicate feedback (ID: {feedback_id})")

        return {
            "status": "success",
            "feedback_id": feedback_id,
            "message": "Feedback recorded. Model will learn from this!",
        }

    except Exception as e:
        logger.error(f"Error submitting duplicate feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/name-match")
async def submit_name_match_feedback(request: NameMatchFeedbackRequest):
    """Submit feedback on name matching prediction."""
    try:
        feedback = NameMatchFeedback(
            name1=request.name1,
            name2=request.name2,
            predicted_similarity=request.predicted_similarity,
            predicted_match=request.predicted_match,
            user_confirmed_match=request.user_confirmed_match,
            timestamp=datetime.now().isoformat(),
            model_version=request.model_version,
            detected_language1=request.detected_language1,
            detected_language2=request.detected_language2,
            surname_similarity=request.surname_similarity,
            given_name_similarity=request.given_name_similarity,
            user_notes=request.user_notes,
        )

        feedback_id = feedback_db.add_name_match_feedback(feedback)

        return {
            "status": "success",
            "feedback_id": feedback_id,
            "message": "Name match feedback recorded",
        }

    except Exception as e:
        logger.error(f"Error submitting name match feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/language")
async def submit_language_feedback(request: LanguageFeedbackRequest):
    """Submit feedback on language detection prediction."""
    try:
        feedback = LanguageFeedback(
            name=request.name,
            predicted_language=request.predicted_language,
            predicted_confidence=request.predicted_confidence,
            correct_language=request.correct_language,
            timestamp=datetime.now().isoformat(),
            model_version=request.model_version,
            place_context=request.place_context,
            other_names=request.other_names,
            user_notes=request.user_notes,
        )

        feedback_id = feedback_db.add_language_feedback(feedback)

        return {
            "status": "success",
            "feedback_id": feedback_id,
            "message": "Language feedback recorded",
        }

    except Exception as e:
        logger.error(f"Error submitting language feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/feedback/quality")
async def submit_quality_feedback(request: QualityFeedbackRequest):
    """Submit feedback on quality classification prediction."""
    try:
        feedback = QualityFeedback(
            person_id=request.person_id,
            predicted_issues=request.predicted_issues,
            confidence_scores=request.confidence_scores,
            confirmed_issues=request.confirmed_issues,
            false_positives=request.false_positives,
            missed_issues=request.missed_issues,
            timestamp=datetime.now().isoformat(),
            model_version=request.model_version,
            issue_details=request.issue_details,
            user_notes=request.user_notes,
        )

        feedback_id = feedback_db.add_quality_feedback(feedback)

        return {
            "status": "success",
            "feedback_id": feedback_id,
            "message": "Quality feedback recorded",
        }

    except Exception as e:
        logger.error(f"Error submitting quality feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Active learning endpoints
@router.get("/active/uncertain-duplicates")
async def get_uncertain_duplicates(max_results: int = 20):
    """
    Get uncertain duplicate predictions for review.

    Returns cases where the model is unsure, prioritized by learning value.
    """
    # This would require loading person pairs - simplified for API
    return {
        "status": "not_implemented",
        "message": "Requires person pairs to be provided",
        "suggestion": "Use Python API: active_learner.find_uncertain_duplicates()",
    }


@router.get("/active/learning-queue")
async def get_learning_queue():
    """
    Get prioritized queue of predictions needing review.

    Combines uncertain predictions across all types.
    """
    return {
        "status": "not_implemented",
        "message": "Use Python API for full active learning functionality",
    }


# Performance monitoring endpoints
@router.get("/performance/duplicate-detector")
async def get_duplicate_detector_performance(days: int = 30):
    """
    Get duplicate detector performance metrics.

    Includes breakdown by feature type (names, places, dates, relationships).
    """
    try:
        metrics = performance_monitor.get_duplicate_detector_performance(
            time_window_days=days
        )
        return metrics
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/language-detector")
async def get_language_detector_performance(days: int = 30):
    """Get language detector performance with per-language breakdown."""
    try:
        metrics = performance_monitor.get_language_detector_performance(
            time_window_days=days
        )
        return metrics
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/quality-classifier")
async def get_quality_classifier_performance(days: int = 30):
    """Get quality classifier performance with per-issue-type breakdown."""
    try:
        metrics = performance_monitor.get_quality_classifier_performance(
            time_window_days=days
        )
        return metrics
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/performance/comprehensive")
async def get_comprehensive_performance():
    """Get comprehensive performance report for all models."""
    try:
        report = performance_monitor.get_comprehensive_report()
        return report
    except Exception as e:
        logger.error(f"Error getting performance report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Retraining endpoints
@router.post("/retrain/duplicate-detector")
async def retrain_duplicate_detector():
    """Manually trigger duplicate detector retraining with new feedback."""
    try:
        result = incremental_trainer.update_duplicate_detector()
        return result
    except Exception as e:
        logger.error(f"Error retraining duplicate detector: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrain/language-detector")
async def retrain_language_detector():
    """Manually trigger language detector retraining."""
    try:
        result = incremental_trainer.update_language_detector()
        return result
    except Exception as e:
        logger.error(f"Error retraining language detector: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrain/all")
async def retrain_all_models():
    """Update all models with new feedback."""
    try:
        result = incremental_trainer.update_all_models()
        return result
    except Exception as e:
        logger.error(f"Error retraining models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retrain/auto")
async def auto_retrain():
    """
    Automatically check and retrain models that need updates.

    Triggers retraining based on:
    - Performance degradation
    - Sufficient new feedback
    - Data drift detection
    """
    try:
        result = scheduler.auto_retrain_if_needed()
        return result
    except Exception as e:
        logger.error(f"Error in auto-retrain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retrain/schedule-status")
async def get_schedule_status():
    """Get status of automated retraining schedule."""
    try:
        status = scheduler.get_retraining_schedule_status()
        return status
    except Exception as e:
        logger.error(f"Error getting schedule status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retrain/check")
async def check_retraining_needs():
    """Check which models need retraining."""
    try:
        decisions = scheduler.check_all_models()
        return decisions
    except Exception as e:
        logger.error(f"Error checking retraining needs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Feedback statistics
@router.get("/feedback/stats")
async def get_feedback_stats():
    """Get statistics about collected feedback."""
    try:
        stats = feedback_db.get_feedback_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting feedback stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/feedback/recent/{feedback_type}")
async def get_recent_feedback(feedback_type: str, limit: int = 50):
    """
    Get recent feedback of a specific type.

    feedback_type: "duplicate", "name_match", "language", "quality", "place", "event"
    """
    try:
        feedback = feedback_db.get_recent_feedback(feedback_type, limit=limit)
        return {
            "feedback_type": feedback_type,
            "count": len(feedback),
            "feedback": feedback,
        }
    except Exception as e:
        logger.error(f"Error getting recent feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))
