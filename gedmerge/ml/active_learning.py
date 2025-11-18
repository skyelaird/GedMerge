"""
Active learning for genealogy ML models.

Identifies uncertain predictions for user review to maximize learning efficiency.
Covers ALL data aspects: names, places, events, relationships.
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from dataclasses import dataclass
import logging

from .models import (
    DuplicateDetectionModel,
    NameMatchingModel,
    LanguageDetectionModel,
    DataQualityClassifier,
)
from .utils import FeatureExtractor
from ..core.person import Person

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class UncertainPrediction:
    """An uncertain prediction that needs user review."""
    prediction_type: str  # "duplicate", "name_match", "language", "quality"
    confidence: float
    uncertainty_score: float  # Higher = more uncertain
    priority_score: float  # Higher = should review first

    # Context for review
    context: Dict[str, Any]

    # Recommendation
    suggested_action: str


class ActiveLearner:
    """
    Active learning coordinator.

    Identifies most valuable examples for user labeling across:
    - Duplicate detection (all features: names, places, dates, relationships)
    - Name matching
    - Language detection
    - Data quality
    """

    def __init__(
        self,
        duplicate_model: Optional[DuplicateDetectionModel] = None,
        name_model: Optional[NameMatchingModel] = None,
        language_model: Optional[LanguageDetectionModel] = None,
        quality_model: Optional[DataQualityClassifier] = None,
    ):
        """
        Initialize active learner.

        Args:
            duplicate_model: Duplicate detection model
            name_model: Name matching model
            language_model: Language detection model
            quality_model: Quality classifier
        """
        self.duplicate_model = duplicate_model
        self.name_model = name_model
        self.language_model = language_model
        self.quality_model = quality_model
        self.feature_extractor = FeatureExtractor()

    def find_uncertain_duplicates(
        self,
        person_pairs: List[Tuple[Person, Person]],
        uncertainty_threshold: float = 0.15,
        max_results: int = 50,
    ) -> List[UncertainPrediction]:
        """
        Find duplicate predictions with high uncertainty.

        Considers uncertainty in ALL features:
        - Name similarity
        - Place matching
        - Date matching
        - Relationship overlap

        Args:
            person_pairs: List of person pairs to check
            uncertainty_threshold: Minimum uncertainty (distance from 0.5 confidence)
            max_results: Maximum uncertain pairs to return

        Returns:
            List of uncertain predictions, sorted by priority
        """
        if not self.duplicate_model:
            logger.warning("No duplicate model loaded")
            return []

        logger.info(f"Searching {len(person_pairs)} pairs for uncertain predictions...")

        uncertain = []

        for person1, person2 in person_pairs:
            prediction = self.duplicate_model.predict(person1, person2)

            # Calculate uncertainty (distance from decision boundary at 0.5)
            uncertainty = abs(prediction.confidence - 0.5)

            # Only consider predictions near the boundary
            if uncertainty <= uncertainty_threshold:
                # Calculate priority score
                # Higher priority for:
                # 1. More uncertain (closer to 0.5)
                # 2. Higher feature importance variance (conflicting signals)
                feature_variance = np.var(list(prediction.feature_importances.values()))

                priority = (uncertainty_threshold - uncertainty) * (1 + feature_variance)

                # Identify which features are conflicting
                feature_imp = prediction.feature_importances
                top_positive = sorted(feature_imp.items(), key=lambda x: -x[1])[:3]
                top_negative = sorted(feature_imp.items(), key=lambda x: x[1])[:3]

                context = {
                    'person1_id': person1.person_id,
                    'person2_id': person2.person_id,
                    'person1_name': str(person1.names[0]) if person1.names else "Unknown",
                    'person2_name': str(person2.names[0]) if person2.names else "Unknown",
                    'predicted_confidence': prediction.confidence,
                    'predicted_duplicate': prediction.is_duplicate,
                    'top_positive_features': [f for f, _ in top_positive],
                    'top_negative_features': [f for f, _ in top_negative],
                    'uncertainty_reason': self._explain_uncertainty(
                        prediction.confidence, feature_imp
                    ),
                }

                suggested_action = (
                    "Review carefully - conflicting signals between features"
                    if feature_variance > 0.1
                    else "Borderline case - needs human judgment"
                )

                uncertain.append(UncertainPrediction(
                    prediction_type="duplicate",
                    confidence=prediction.confidence,
                    uncertainty_score=uncertainty,
                    priority_score=priority,
                    context=context,
                    suggested_action=suggested_action,
                ))

        # Sort by priority (highest first)
        uncertain.sort(key=lambda x: -x.priority_score)

        logger.info(f"Found {len(uncertain)} uncertain duplicate predictions")

        return uncertain[:max_results]

    def find_uncertain_languages(
        self,
        names: List[str],
        uncertainty_threshold: float = 0.3,
        max_results: int = 50,
    ) -> List[UncertainPrediction]:
        """
        Find language predictions with high uncertainty.

        Args:
            names: List of names to check
            uncertainty_threshold: Minimum confidence for certain prediction
            max_results: Maximum results

        Returns:
            List of uncertain language predictions
        """
        if not self.language_model:
            logger.warning("No language model loaded")
            return []

        logger.info(f"Checking {len(names)} names for uncertain language predictions...")

        uncertain = []

        for name in names:
            language, confidence = self.language_model.predict(name)

            # Low confidence = high uncertainty
            if confidence < 1.0 - uncertainty_threshold:
                uncertainty_score = 1.0 - confidence
                priority = uncertainty_score

                # Get all language probabilities if available
                context_info = ""
                if hasattr(self.language_model.model, 'predict_proba'):
                    # Get top 3 predicted languages
                    context_info = f"Could be {language} but uncertain"

                context = {
                    'name': name,
                    'predicted_language': language,
                    'confidence': confidence,
                    'uncertainty_reason': f"Low confidence: {confidence:.1%}",
                }

                suggested_action = (
                    f"Review language classification - appears {language} "
                    f"but only {confidence:.1%} confident"
                )

                uncertain.append(UncertainPrediction(
                    prediction_type="language",
                    confidence=confidence,
                    uncertainty_score=uncertainty_score,
                    priority_score=priority,
                    context=context,
                    suggested_action=suggested_action,
                ))

        uncertain.sort(key=lambda x: -x.priority_score)

        logger.info(f"Found {len(uncertain)} uncertain language predictions")

        return uncertain[:max_results]

    def find_uncertain_quality_issues(
        self,
        persons: List[Person],
        uncertainty_threshold: float = 0.3,
        max_results: int = 50,
    ) -> List[UncertainPrediction]:
        """
        Find quality issue predictions with high uncertainty.

        Args:
            persons: List of persons to check
            uncertainty_threshold: Confidence threshold
            max_results: Maximum results

        Returns:
            List of uncertain quality predictions
        """
        if not self.quality_model:
            logger.warning("No quality model loaded")
            return []

        logger.info(f"Checking {len(persons)} persons for uncertain quality predictions...")

        uncertain = []

        for person in persons:
            predictions = self.quality_model.predict(person)

            # Find issues with uncertain confidence (near 0.5)
            uncertain_issues = []
            for issue, prob in predictions.items():
                uncertainty = abs(prob - 0.5)
                if uncertainty <= uncertainty_threshold:
                    uncertain_issues.append((issue, prob, uncertainty))

            if uncertain_issues:
                # Sort by uncertainty
                uncertain_issues.sort(key=lambda x: x[2])

                # Priority = number of uncertain issues + average uncertainty
                avg_uncertainty = np.mean([u for _, _, u in uncertain_issues])
                priority = len(uncertain_issues) * (1 - avg_uncertainty)

                context = {
                    'person_id': person.person_id,
                    'person_name': str(person.names[0]) if person.names else "Unknown",
                    'uncertain_issues': [
                        {
                            'issue': issue,
                            'probability': prob,
                            'uncertainty': unc
                        }
                        for issue, prob, unc in uncertain_issues
                    ],
                }

                suggested_action = (
                    f"Review {len(uncertain_issues)} borderline quality issues "
                    f"for this person"
                )

                uncertain.append(UncertainPrediction(
                    prediction_type="quality",
                    confidence=1.0 - avg_uncertainty,
                    uncertainty_score=avg_uncertainty,
                    priority_score=priority,
                    context=context,
                    suggested_action=suggested_action,
                ))

        uncertain.sort(key=lambda x: -x.priority_score)

        logger.info(f"Found {len(uncertain)} persons with uncertain quality predictions")

        return uncertain[:max_results]

    def get_priority_review_queue(
        self,
        person_pairs: Optional[List[Tuple[Person, Person]]] = None,
        names: Optional[List[str]] = None,
        persons: Optional[List[Person]] = None,
        max_total: int = 100,
    ) -> List[UncertainPrediction]:
        """
        Get prioritized queue of predictions needing review.

        Combines uncertainty across ALL prediction types and data aspects.

        Args:
            person_pairs: Pairs to check for duplicates
            names: Names to check for language
            persons: Persons to check for quality
            max_total: Maximum total items in queue

        Returns:
            Combined list of uncertain predictions, prioritized
        """
        all_uncertain = []

        # Find uncertain duplicates (covers names, places, dates, relationships)
        if person_pairs and self.duplicate_model:
            uncertain_dups = self.find_uncertain_duplicates(
                person_pairs,
                max_results=max_total // 3
            )
            all_uncertain.extend(uncertain_dups)

        # Find uncertain language predictions
        if names and self.language_model:
            uncertain_langs = self.find_uncertain_languages(
                names,
                max_results=max_total // 3
            )
            all_uncertain.extend(uncertain_langs)

        # Find uncertain quality predictions
        if persons and self.quality_model:
            uncertain_quality = self.find_uncertain_quality_issues(
                persons,
                max_results=max_total // 3
            )
            all_uncertain.extend(uncertain_quality)

        # Sort by priority across all types
        all_uncertain.sort(key=lambda x: -x.priority_score)

        logger.info(f"Total uncertain predictions: {len(all_uncertain)}")
        logger.info(f"  Duplicates: {sum(1 for u in all_uncertain if u.prediction_type == 'duplicate')}")
        logger.info(f"  Languages: {sum(1 for u in all_uncertain if u.prediction_type == 'language')}")
        logger.info(f"  Quality: {sum(1 for u in all_uncertain if u.prediction_type == 'quality')}")

        return all_uncertain[:max_total]

    def _explain_uncertainty(
        self,
        confidence: float,
        feature_importances: Dict[str, float],
    ) -> str:
        """Generate human-readable explanation of uncertainty."""
        if abs(confidence - 0.5) < 0.05:
            return "Prediction confidence very close to 50% - could go either way"

        # Find conflicting features
        top_features = sorted(feature_importances.items(), key=lambda x: -abs(x[1]))[:5]

        positive_features = [f for f, v in top_features if v > 0.1]
        negative_features = [f for f, v in top_features if v < -0.1]

        if positive_features and negative_features:
            return (
                f"Conflicting signals: {', '.join(positive_features)} suggest match, "
                f"but {', '.join(negative_features)} suggest no match"
            )
        elif confidence > 0.5:
            return f"Leaning toward duplicate based on {', '.join(positive_features)}"
        else:
            return "Leaning toward not duplicate, but with some uncertainty"

    def get_learning_impact_estimate(
        self,
        uncertain_predictions: List[UncertainPrediction],
    ) -> Dict[str, Any]:
        """
        Estimate the learning impact of labeling these uncertain predictions.

        Args:
            uncertain_predictions: List of uncertain predictions

        Returns:
            Impact metrics
        """
        # Group by type
        by_type = {}
        for pred in uncertain_predictions:
            if pred.prediction_type not in by_type:
                by_type[pred.prediction_type] = []
            by_type[pred.prediction_type].append(pred)

        impact = {
            "total_predictions": len(uncertain_predictions),
            "by_type": {},
            "estimated_accuracy_gain": 0.0,
            "estimated_labeling_time_minutes": len(uncertain_predictions) * 1.5,  # ~1.5 min per label
        }

        for pred_type, preds in by_type.items():
            avg_uncertainty = np.mean([p.uncertainty_score for p in preds])

            # High uncertainty examples have more learning value
            learning_value = avg_uncertainty * len(preds)

            impact["by_type"][pred_type] = {
                "count": len(preds),
                "avg_uncertainty": avg_uncertainty,
                "learning_value": learning_value,
            }

        # Rough estimate: each uncertain example resolved improves accuracy by ~0.1-0.5%
        impact["estimated_accuracy_gain"] = (
            len(uncertain_predictions) * 0.002  # 0.2% per 100 examples
        )

        return impact
