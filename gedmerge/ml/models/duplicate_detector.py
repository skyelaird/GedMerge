"""Smart Duplicate Detection using XGBoost/LightGBM/Random Forest."""

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import pandas as pd
from pathlib import Path
import logging
from dataclasses import dataclass

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
    classification_report,
)
import xgboost as xgb
import lightgbm as lgb
import joblib

from ..utils.config import MLConfig
from ..utils.feature_extractor import FeatureExtractor, PairwiseFeatures
from ...core.person import Person

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DuplicatePrediction:
    """Prediction for a person pair."""

    person1_id: str
    person2_id: str
    is_duplicate: bool
    confidence: float
    feature_importances: Dict[str, float]


class DuplicateDetectionModel:
    """
    ML model for duplicate detection using gradient boosting or random forest.

    Learns optimal feature weights from labeled data instead of using fixed rules.
    """

    def __init__(
        self,
        model_type: str = "xgboost",
        config: Optional[MLConfig] = None,
    ):
        """
        Initialize model.

        Args:
            model_type: One of "xgboost", "lightgbm", "random_forest"
            config: ML configuration
        """
        self.model_type = model_type
        self.config = config or MLConfig()
        self.model = None
        self.feature_extractor = FeatureExtractor()

        self.feature_names = [
            'name_similarity',
            'phonetic_similarity',
            'surname_similarity',
            'given_name_similarity',
            'exact_name_match',
            'levenshtein_distance',
            'jaro_winkler_similarity',
            'token_set_ratio',
            'birth_date_match',
            'death_date_match',
            'age_difference',
            'date_conflict',
            'birth_place_similarity',
            'death_place_similarity',
            'place_overlap',
            'shared_parents',
            'shared_spouses',
            'shared_children',
            'relationship_overlap_score',
            'sex_conflict',
            'significant_age_gap',
            'different_locations',
            'overall_similarity',
        ]

        self.metrics = {}

    def create_model(self) -> Any:
        """Create underlying ML model."""
        if self.model_type == "xgboost":
            params = self.config.duplicate_detector_config.copy()
            return xgb.XGBClassifier(
                n_estimators=params.get('n_estimators', 100),
                max_depth=params.get('max_depth', 6),
                learning_rate=params.get('learning_rate', 0.1),
                random_state=self.config.random_seed,
                eval_metric='logloss',
                use_label_encoder=False,
            )

        elif self.model_type == "lightgbm":
            params = self.config.duplicate_detector_config.copy()
            return lgb.LGBMClassifier(
                n_estimators=params.get('n_estimators', 100),
                max_depth=params.get('max_depth', 6),
                learning_rate=params.get('learning_rate', 0.1),
                random_state=self.config.random_seed,
            )

        elif self.model_type == "random_forest":
            params = self.config.duplicate_detector_config.copy()
            return RandomForestClassifier(
                n_estimators=params.get('n_estimators', 100),
                max_depth=params.get('max_depth', 6),
                random_state=self.config.random_seed,
                n_jobs=-1,
            )

        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2,
    ) -> Dict[str, float]:
        """
        Train the model.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Labels (n_samples,)
            validation_split: Fraction for validation

        Returns:
            Training metrics
        """
        logger.info(f"Training {self.model_type} duplicate detector...")
        logger.info(f"Training samples: {len(X)}")
        logger.info(f"Positive examples: {sum(y)}")
        logger.info(f"Negative examples: {len(y) - sum(y)}")

        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y,
            test_size=validation_split,
            random_state=self.config.random_seed,
            stratify=y,
        )

        # Create and train model
        self.model = self.create_model()

        # Train with validation for early stopping (if supported)
        if self.model_type in ["xgboost", "lightgbm"]:
            self.model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                verbose=False,
            )
        else:
            self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_val)
        y_pred_proba = self.model.predict_proba(X_val)[:, 1]

        metrics = {
            'accuracy': accuracy_score(y_val, y_pred),
            'precision': precision_score(y_val, y_pred),
            'recall': recall_score(y_val, y_pred),
            'f1': f1_score(y_val, y_pred),
            'roc_auc': roc_auc_score(y_val, y_pred_proba),
        }

        self.metrics = metrics

        logger.info("Validation Results:")
        for metric, value in metrics.items():
            logger.info(f"  {metric}: {value:.4f}")

        # Feature importance
        self._log_feature_importance()

        return metrics

    def predict(
        self,
        person1: Person,
        person2: Person,
    ) -> DuplicatePrediction:
        """
        Predict if two persons are duplicates.

        Args:
            person1: First person
            person2: Second person

        Returns:
            Prediction with confidence
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        # Extract features
        features = self.feature_extractor.extract_pairwise_features(person1, person2)
        X = self.feature_extractor.to_pairwise_vector(features).reshape(1, -1)

        # Predict
        is_duplicate = self.model.predict(X)[0]
        confidence = self.model.predict_proba(X)[0, 1]  # Probability of duplicate

        # Get feature importances for this prediction
        feature_importances = self._get_prediction_feature_importances(features)

        return DuplicatePrediction(
            person1_id=str(person1.person_id),
            person2_id=str(person2.person_id),
            is_duplicate=bool(is_duplicate),
            confidence=float(confidence),
            feature_importances=feature_importances,
        )

    def predict_batch(
        self,
        X: np.ndarray,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict on batch of feature vectors.

        Args:
            X: Feature matrix

        Returns:
            Tuple of (predictions, confidences)
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        predictions = self.model.predict(X)
        confidences = self.model.predict_proba(X)[:, 1]

        return predictions, confidences

    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance scores."""
        if self.model is None:
            raise ValueError("Model not trained.")

        if hasattr(self.model, 'feature_importances_'):
            importances = self.model.feature_importances_
        else:
            return {}

        # Normalize to sum to 1
        importances = importances / importances.sum()

        return {
            name: float(importance)
            for name, importance in zip(self.feature_names, importances)
        }

    def _log_feature_importance(self):
        """Log feature importance."""
        importance = self.get_feature_importance()

        if not importance:
            return

        logger.info("\nFeature Importance:")
        for name, score in sorted(importance.items(), key=lambda x: -x[1])[:10]:
            logger.info(f"  {name:30s}: {score:.4f}")

    def _get_prediction_feature_importances(
        self,
        features: PairwiseFeatures
    ) -> Dict[str, float]:
        """Get feature contributions for a specific prediction."""
        importance = self.get_feature_importance()

        # Weight by actual feature values (simplified SHAP-like approach)
        feature_vector = self.feature_extractor.to_pairwise_vector(features)

        weighted_importance = {}
        for i, name in enumerate(self.feature_names):
            if name in importance:
                # Importance * feature value
                weighted_importance[name] = importance[name] * float(feature_vector[i])

        # Normalize
        total = sum(abs(v) for v in weighted_importance.values())
        if total > 0:
            weighted_importance = {
                k: v / total for k, v in weighted_importance.items()
            }

        return weighted_importance

    def cross_validate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        cv: int = 5,
    ) -> Dict[str, Any]:
        """
        Perform cross-validation.

        Args:
            X: Feature matrix
            y: Labels
            cv: Number of folds

        Returns:
            Cross-validation results
        """
        logger.info(f"Performing {cv}-fold cross-validation...")

        self.model = self.create_model()

        # Score metrics
        scoring = ['accuracy', 'precision', 'recall', 'f1', 'roc_auc']
        results = {}

        for metric in scoring:
            scores = cross_val_score(
                self.model,
                X, y,
                cv=cv,
                scoring=metric,
                n_jobs=-1,
            )
            results[metric] = {
                'mean': float(np.mean(scores)),
                'std': float(np.std(scores)),
                'scores': scores.tolist(),
            }

            logger.info(f"{metric}: {results[metric]['mean']:.4f} (+/- {results[metric]['std']:.4f})")

        return results

    def save(self, filepath: Path):
        """Save model to file."""
        if self.model is None:
            raise ValueError("No model to save.")

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Save model and metadata
        save_dict = {
            'model': self.model,
            'model_type': self.model_type,
            'feature_names': self.feature_names,
            'metrics': self.metrics,
            'config': self.config,
        }

        joblib.dump(save_dict, filepath)
        logger.info(f"Model saved to {filepath}")

    @classmethod
    def load(cls, filepath: Path) -> "DuplicateDetectionModel":
        """Load model from file."""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")

        save_dict = joblib.load(filepath)

        model_obj = cls(
            model_type=save_dict['model_type'],
            config=save_dict.get('config'),
        )

        model_obj.model = save_dict['model']
        model_obj.feature_names = save_dict['feature_names']
        model_obj.metrics = save_dict.get('metrics', {})

        logger.info(f"Model loaded from {filepath}")
        return model_obj

    def get_optimal_threshold(
        self,
        X: np.ndarray,
        y: np.ndarray,
        optimize_for: str = "f1",
    ) -> float:
        """
        Find optimal confidence threshold.

        Args:
            X: Feature matrix
            y: True labels
            optimize_for: Metric to optimize ("f1", "precision", "recall")

        Returns:
            Optimal threshold
        """
        if self.model is None:
            raise ValueError("Model not trained.")

        y_pred_proba = self.model.predict_proba(X)[:, 1]

        best_threshold = 0.5
        best_score = 0.0

        # Try different thresholds
        for threshold in np.arange(0.1, 1.0, 0.05):
            y_pred = (y_pred_proba >= threshold).astype(int)

            if optimize_for == "f1":
                score = f1_score(y, y_pred)
            elif optimize_for == "precision":
                score = precision_score(y, y_pred)
            elif optimize_for == "recall":
                score = recall_score(y, y_pred)
            else:
                raise ValueError(f"Unknown metric: {optimize_for}")

            if score > best_score:
                best_score = score
                best_threshold = threshold

        logger.info(f"Optimal threshold for {optimize_for}: {best_threshold:.2f} (score: {best_score:.4f})")
        return best_threshold
