"""Data Quality Classification using Random Forest."""

from typing import List, Dict, Optional, Any
import numpy as np
from pathlib import Path
import logging

from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    classification_report,
    multilabel_confusion_matrix,
)
import joblib

from ..utils.config import MLConfig
from ..utils.feature_extractor import FeatureExtractor, PersonFeatures
from ...core.person import Person

logger = logging.getLogger(__name__)


class DataQualityClassifier:
    """
    Multi-label classifier for data quality issues.

    Identifies multiple quality issues per person record:
    - Reversed names
    - Embedded variants
    - Titles in wrong field
    - Missing data
    - Invalid dates
    - Placeholder names
    - Inconsistent formatting
    """

    def __init__(
        self,
        config: Optional[MLConfig] = None,
    ):
        """
        Initialize classifier.

        Args:
            config: ML configuration
        """
        self.config = config or MLConfig()
        self.model = None
        self.feature_extractor = FeatureExtractor()

        self.quality_categories = self.config.quality_classifier_config.get(
            'quality_categories',
            [
                "reversed_names",
                "embedded_variants",
                "titles_in_wrong_field",
                "missing_data",
                "invalid_dates",
                "placeholder_name",
                "inconsistent_formatting",
            ]
        )

        self.category_to_idx = {
            cat: idx for idx, cat in enumerate(self.quality_categories)
        }

    def create_model(self) -> MultiOutputClassifier:
        """Create multi-label classifier."""
        config = self.config.quality_classifier_config

        base_model = RandomForestClassifier(
            n_estimators=config.get('n_estimators', 200),
            max_depth=config.get('max_depth', 10),
            random_state=self.config.random_seed,
            class_weight=config.get('class_weight', 'balanced'),
            n_jobs=-1,
        )

        # Wrap in MultiOutputClassifier for multi-label
        return MultiOutputClassifier(base_model, n_jobs=-1)

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        validation_split: float = 0.2,
    ) -> Dict[str, Any]:
        """
        Train the classifier.

        Args:
            X: Feature matrix (n_samples, n_features)
            y: Labels (n_samples, n_categories) - multi-label
            validation_split: Fraction for validation

        Returns:
            Training metrics
        """
        logger.info("Training Data Quality Classifier...")
        logger.info(f"Training samples: {len(X)}")
        logger.info(f"Quality categories: {len(self.quality_categories)}")

        # Check label distribution
        logger.info("\nLabel distribution:")
        for idx, category in enumerate(self.quality_categories):
            count = np.sum(y[:, idx])
            pct = count / len(y) * 100
            logger.info(f"  {category}: {count} ({pct:.1f}%)")

        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            X, y,
            test_size=validation_split,
            random_state=self.config.random_seed,
        )

        # Create and train model
        self.model = self.create_model()
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_val)

        # Compute metrics per category
        metrics = {}
        logger.info("\nValidation Results:")

        for idx, category in enumerate(self.quality_categories):
            y_true_cat = y_val[:, idx]
            y_pred_cat = y_pred[:, idx]

            if len(np.unique(y_true_cat)) > 1:  # Only if both classes present
                acc = accuracy_score(y_true_cat, y_pred_cat)
                prec = precision_score(y_true_cat, y_pred_cat, zero_division=0)
                rec = recall_score(y_true_cat, y_pred_cat, zero_division=0)
                f1 = f1_score(y_true_cat, y_pred_cat, zero_division=0)

                metrics[category] = {
                    'accuracy': float(acc),
                    'precision': float(prec),
                    'recall': float(rec),
                    'f1': float(f1),
                }

                logger.info(
                    f"  {category:30s}: acc={acc:.3f}, prec={prec:.3f}, "
                    f"rec={rec:.3f}, f1={f1:.3f}"
                )

        # Overall metrics (micro-average)
        overall_acc = accuracy_score(y_val.ravel(), y_pred.ravel())
        overall_prec = precision_score(y_val, y_pred, average='micro', zero_division=0)
        overall_rec = recall_score(y_val, y_pred, average='micro', zero_division=0)
        overall_f1 = f1_score(y_val, y_pred, average='micro', zero_division=0)

        metrics['overall'] = {
            'accuracy': float(overall_acc),
            'precision': float(overall_prec),
            'recall': float(overall_rec),
            'f1': float(overall_f1),
        }

        logger.info("\nOverall (micro-avg):")
        logger.info(
            f"  acc={overall_acc:.3f}, prec={overall_prec:.3f}, "
            f"rec={overall_rec:.3f}, f1={overall_f1:.3f}"
        )

        return metrics

    def predict(self, person: Person) -> Dict[str, float]:
        """
        Predict quality issues for a person.

        Args:
            person: Person object

        Returns:
            Dictionary mapping category to probability
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        # Extract features
        person_features = self.feature_extractor.extract_person_features(person)
        X = self.feature_extractor.to_feature_vector(person_features).reshape(1, -1)

        # Predict probabilities
        predictions = {}

        # Get predictions for each category
        for idx, estimator in enumerate(self.model.estimators_):
            category = self.quality_categories[idx]

            # Get probability of positive class
            if hasattr(estimator, 'predict_proba'):
                proba = estimator.predict_proba(X)[0]
                if len(proba) > 1:
                    predictions[category] = float(proba[1])
                else:
                    predictions[category] = float(proba[0])
            else:
                # Fallback to binary prediction
                pred = estimator.predict(X)[0]
                predictions[category] = float(pred)

        return predictions

    def predict_batch(self, X: np.ndarray) -> np.ndarray:
        """
        Predict on batch of features.

        Args:
            X: Feature matrix

        Returns:
            Predictions (n_samples, n_categories)
        """
        if self.model is None:
            raise ValueError("Model not trained.")

        return self.model.predict(X)

    def get_quality_issues(
        self,
        person: Person,
        threshold: float = 0.5,
    ) -> List[str]:
        """
        Get list of quality issues for a person.

        Args:
            person: Person object
            threshold: Probability threshold for flagging issue

        Returns:
            List of issue categories
        """
        predictions = self.predict(person)

        issues = [
            category
            for category, prob in predictions.items()
            if prob >= threshold
        ]

        return issues

    def get_feature_importance(self) -> Dict[str, Dict[str, float]]:
        """Get feature importance per category."""
        if self.model is None:
            raise ValueError("Model not trained.")

        importance_dict = {}

        feature_names = [
            'name_length', 'surname_length', 'given_name_length',
            'has_multiple_names', 'name_complexity', 'language_confidence',
            'is_multilingual', 'has_birth_date', 'has_death_date',
            'birth_year', 'death_year', 'age_at_death', 'date_precision',
            'has_birth_place', 'has_death_place', 'place_count',
            'unique_places', 'num_parents', 'num_spouses', 'num_children',
            'family_connectivity', 'has_missing_surname', 'has_placeholder_name',
            'has_title_in_name', 'data_completeness',
        ]

        for idx, estimator in enumerate(self.model.estimators_):
            category = self.quality_categories[idx]

            if hasattr(estimator, 'feature_importances_'):
                importances = estimator.feature_importances_

                # Normalize
                importances = importances / importances.sum()

                importance_dict[category] = {
                    name: float(imp)
                    for name, imp in zip(feature_names, importances)
                }

        return importance_dict

    def generate_quality_report(
        self,
        persons: List[Person],
        threshold: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Generate quality report for a list of persons.

        Args:
            persons: List of Person objects
            threshold: Threshold for flagging issues

        Returns:
            Quality report dictionary
        """
        logger.info(f"Generating quality report for {len(persons)} persons...")

        issue_counts = {category: 0 for category in self.quality_categories}
        person_issue_count = []

        for person in persons:
            issues = self.get_quality_issues(person, threshold)

            for issue in issues:
                issue_counts[issue] += 1

            person_issue_count.append(len(issues))

        report = {
            'total_persons': len(persons),
            'issue_counts': issue_counts,
            'persons_with_issues': sum(1 for count in person_issue_count if count > 0),
            'avg_issues_per_person': np.mean(person_issue_count),
            'max_issues_per_person': max(person_issue_count) if person_issue_count else 0,
            'issue_percentages': {
                category: (count / len(persons) * 100)
                for category, count in issue_counts.items()
            },
        }

        logger.info("\nQuality Report:")
        logger.info(f"  Total persons: {report['total_persons']}")
        logger.info(f"  Persons with issues: {report['persons_with_issues']}")
        logger.info(f"  Avg issues/person: {report['avg_issues_per_person']:.2f}")
        logger.info("\n  Issue breakdown:")
        for category, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
            pct = report['issue_percentages'][category]
            logger.info(f"    {category:30s}: {count:5d} ({pct:5.1f}%)")

        return report

    def save(self, filepath: Path):
        """Save model."""
        if self.model is None:
            raise ValueError("No model to save.")

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        joblib.dump({
            'model': self.model,
            'quality_categories': self.quality_categories,
            'category_to_idx': self.category_to_idx,
            'config': self.config,
        }, filepath)

        logger.info(f"Model saved to {filepath}")

    @classmethod
    def load(cls, filepath: Path) -> "DataQualityClassifier":
        """Load model."""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")

        data = joblib.load(filepath)

        model_obj = cls(config=data.get('config'))
        model_obj.model = data['model']
        model_obj.quality_categories = data['quality_categories']
        model_obj.category_to_idx = data['category_to_idx']

        logger.info(f"Model loaded from {filepath}")
        return model_obj
