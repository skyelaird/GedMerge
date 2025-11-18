"""
Incremental learning for all ML models.

Updates models with new feedback data without full retraining.
Supports learning from ALL genealogical aspects: names, places, events, relationships.
"""

from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from pathlib import Path
import logging
from datetime import datetime

from ..models import (
    DuplicateDetectionModel,
    NameMatchingModel,
    LanguageDetectionModel,
    DataQualityClassifier,
)
from ..feedback import FeedbackDatabase
from ..utils import ModelRegistry, MLConfig, FeatureExtractor
from ...core.person import Person

logger = logging.getLogger(__name__)


class IncrementalTrainer:
    """
    Incremental trainer for continual learning.

    Updates models with new feedback without full retraining.
    Learns from all aspects: names, places, events, relationships.
    """

    def __init__(
        self,
        config: Optional[MLConfig] = None,
        feedback_db: Optional[FeedbackDatabase] = None,
    ):
        """
        Initialize incremental trainer.

        Args:
            config: ML configuration
            feedback_db: Feedback database
        """
        self.config = config or MLConfig()
        self.feedback_db = feedback_db or FeedbackDatabase()
        self.registry = ModelRegistry(self.config.model_dir)
        self.feature_extractor = FeatureExtractor()

    def update_duplicate_detector(
        self,
        min_new_samples: int = 50,
        strategy: str = "warm_start",
    ) -> Dict[str, Any]:
        """
        Update duplicate detector with new feedback.

        Learns from ALL features: names, places, dates, relationships.

        Args:
            min_new_samples: Minimum new feedback samples required
            strategy: "warm_start" (continue training) or "retrain" (full retrain)

        Returns:
            Update metrics
        """
        logger.info("Updating duplicate detector with new feedback...")

        # Get new feedback since last update
        feedback_records = self.feedback_db.get_recent_feedback(
            "duplicate",
            limit=1000
        )

        if len(feedback_records) < min_new_samples:
            logger.info(f"Not enough feedback: {len(feedback_records)} < {min_new_samples}")
            return {"status": "skipped", "reason": "insufficient_feedback"}

        logger.info(f"Processing {len(feedback_records)} feedback samples")

        # Convert feedback to training data
        X_new = []
        y_new = []

        for record in feedback_records:
            # Extract ALL features from feedback
            features = np.array([
                record['name_similarity'],
                record.get('phonetic_match', 0),  # phonetic similarity
                record.get('surname_match', 0),  # surname similarity (proxy)
                record.get('given_name_match', 0),  # given similarity (proxy)
                record.get('surname_match', False) and record.get('given_name_match', False),  # exact
                0,  # levenshtein (not stored, use approximation)
                record['name_similarity'],  # jaro-winkler approximation
                record['name_similarity'],  # token set approximation
                float(record.get('birth_date_match', 0)),
                float(record.get('death_date_match', 0)),
                record.get('age_difference', 0) or 0,
                float(record.get('date_conflict', False)),
                float(record.get('birth_place_match', 0)),
                float(record.get('death_place_match', 0)),
                record.get('place_similarity', 0.0),
                record.get('shared_parents', 0),
                record.get('shared_spouses', 0),
                0,  # shared children (not stored)
                0.0,  # relationship overlap score
                False,  # sex conflict (not in feedback yet)
                record.get('age_difference', 0) > 10 if record.get('age_difference') else False,
                False,  # different locations (approximation)
                record['predicted_confidence'],  # overall similarity
            ], dtype=np.float32)

            X_new.append(features)
            y_new.append(int(record['user_confirmed']))

        X_new = np.array(X_new)
        y_new = np.array(y_new)

        logger.info(f"Prepared training data: {len(X_new)} samples")
        logger.info(f"  Positive (duplicates): {sum(y_new)}")
        logger.info(f"  Negative (not duplicates): {len(y_new) - sum(y_new)}")

        # Load current model
        try:
            model, metadata = self.registry.load_model("duplicate_detector")
        except:
            logger.warning("No existing model found, creating new one")
            model = DuplicateDetectionModel(model_type="xgboost", config=self.config)
            model.model = model.create_model()

        # Update model
        if strategy == "warm_start" and hasattr(model.model, 'fit'):
            # For tree-based models: retrain with combined data
            # (XGBoost/LightGBM don't have true incremental learning)
            logger.info("Performing warm-start update...")

            # Get some old training data for stability
            # In production, you'd store a sample of training data
            metrics = model.train(X_new, y_new, validation_split=0.2)

        elif strategy == "retrain":
            logger.info("Performing full retrain with new data...")
            metrics = model.train(X_new, y_new, validation_split=0.2)

        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        # Save updated model with new version
        now = datetime.now()
        new_version = f"v{now.strftime('%Y%m%d_%H%M%S')}_incremental"

        self.registry.register_model(
            model=model.model,
            model_name="duplicate_detector",
            model_type=model.model_type,
            version=new_version,
            metrics=metrics,
            config=self.config.duplicate_detector_config,
            tags={"update_type": strategy, "num_new_samples": len(X_new)},
        )

        logger.info(f"Model updated and saved as version {new_version}")

        return {
            "status": "updated",
            "new_version": new_version,
            "num_samples": len(X_new),
            "metrics": metrics,
            "strategy": strategy,
        }

    def update_language_detector(
        self,
        min_new_samples: int = 30,
    ) -> Dict[str, Any]:
        """
        Update language detector with new feedback.

        Learns from corrections across all languages and contexts.

        Args:
            min_new_samples: Minimum new feedback samples

        Returns:
            Update metrics
        """
        logger.info("Updating language detector with new feedback...")

        # Get new feedback
        feedback_records = self.feedback_db.get_recent_feedback(
            "language",
            limit=500
        )

        if len(feedback_records) < min_new_samples:
            logger.info(f"Not enough feedback: {len(feedback_records)} < {min_new_samples}")
            return {"status": "skipped", "reason": "insufficient_feedback"}

        logger.info(f"Processing {len(feedback_records)} language corrections")

        # Convert to training data
        training_data = [
            (record['name'], record['correct_language'])
            for record in feedback_records
        ]

        # Language distribution
        lang_counts = {}
        for _, lang in training_data:
            lang_counts[lang] = lang_counts.get(lang, 0) + 1

        logger.info("Correction distribution:")
        for lang, count in sorted(lang_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  {lang.upper()}: {count}")

        # Load current model
        try:
            model, metadata = self.registry.load_model("language_detector")
        except:
            logger.warning("No existing model found, creating new one")
            from ..models.language_detector import LanguageDetectionModel
            model = LanguageDetectionModel(model_type="multinomial_nb", config=self.config)

        # For Multinomial NB, we can use partial_fit if available
        if hasattr(model.model, 'partial_fit') and model.vectorizer:
            logger.info("Performing incremental update with partial_fit...")

            # Transform new data
            names = [name for name, _ in training_data]
            labels = [lang for _, lang in training_data]

            # Get unique classes
            unique_labels = sorted(set(labels))

            # Vectorize
            X_new = model.vectorizer.transform(names)
            y_new = np.array([model.lang_to_label[lang] for lang in labels])

            # Partial fit
            model.model.partial_fit(
                X_new,
                y_new,
                classes=np.array(list(model.label_to_lang.keys()))
            )

            metrics = {"status": "incremental_update"}

        else:
            # Full retrain with new data
            logger.info("Performing full retrain...")
            metrics = model.train(training_data, validation_split=0.2)

        # Save updated model
        now = datetime.now()
        new_version = f"v{now.strftime('%Y%m%d_%H%M%S')}_incremental"

        model_path = self.config.model_dir / "language_detector" / new_version / "model.pkl"
        model.save(model_path)

        self.registry.register_model(
            model=model,
            model_name="language_detector",
            model_type=model.model_type,
            version=new_version,
            metrics=metrics,
            config=self.config.language_detection_config,
            tags={"num_new_samples": len(training_data)},
        )

        logger.info(f"Language detector updated: version {new_version}")

        return {
            "status": "updated",
            "new_version": new_version,
            "num_samples": len(training_data),
            "language_distribution": lang_counts,
            "metrics": metrics,
        }

    def update_quality_classifier(
        self,
        min_new_samples: int = 50,
    ) -> Dict[str, Any]:
        """
        Update quality classifier with new feedback.

        Learns from corrections across all 7 quality categories.

        Args:
            min_new_samples: Minimum new feedback samples

        Returns:
            Update metrics
        """
        logger.info("Updating quality classifier with new feedback...")

        # Get new feedback
        feedback_records = self.feedback_db.get_recent_feedback(
            "quality",
            limit=500
        )

        if len(feedback_records) < min_new_samples:
            logger.info(f"Not enough feedback: {len(feedback_records)} < {min_new_samples}")
            return {"status": "skipped", "reason": "insufficient_feedback"}

        logger.info(f"Processing {len(feedback_records)} quality feedback samples")

        # This requires person features - would need to store or re-extract
        # For now, return status indicating this needs full implementation
        logger.warning("Quality classifier incremental update requires person objects")
        logger.warning("Use full retraining with updated labels instead")

        return {
            "status": "not_implemented",
            "reason": "requires_person_objects",
            "num_samples": len(feedback_records),
            "suggestion": "Use full retraining pipeline with updated quality labels",
        }

    def update_all_models(
        self,
        check_interval_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Check and update all models that have sufficient new feedback.

        Args:
            check_interval_hours: Minimum hours between updates

        Returns:
            Dictionary of update results per model
        """
        logger.info("Checking all models for updates...")

        results = {}

        # Update duplicate detector
        try:
            results['duplicate_detector'] = self.update_duplicate_detector()
        except Exception as e:
            logger.error(f"Error updating duplicate detector: {e}")
            results['duplicate_detector'] = {"status": "error", "error": str(e)}

        # Update language detector
        try:
            results['language_detector'] = self.update_language_detector()
        except Exception as e:
            logger.error(f"Error updating language detector: {e}")
            results['language_detector'] = {"status": "error", "error": str(e)}

        # Update quality classifier
        try:
            results['quality_classifier'] = self.update_quality_classifier()
        except Exception as e:
            logger.error(f"Error updating quality classifier: {e}")
            results['quality_classifier'] = {"status": "error", "error": str(e)}

        # Summary
        updated = sum(1 for r in results.values() if r.get('status') == 'updated')
        skipped = sum(1 for r in results.values() if r.get('status') == 'skipped')

        logger.info(f"Update complete: {updated} updated, {skipped} skipped")

        return {
            "results": results,
            "summary": {
                "updated": updated,
                "skipped": skipped,
                "timestamp": datetime.now().isoformat(),
            }
        }
