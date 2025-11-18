"""Unified trainer for all ML models."""

from pathlib import Path
from typing import Dict, Any, Optional
import logging

from ..models import (
    DuplicateDetectionModel,
    NameMatchingModel,
    LanguageDetectionModel,
    RelationshipInferenceModel,
    DataQualityClassifier,
)
from ..data import TrainingDataGenerator
from ..utils import ModelRegistry, MLConfig
from ...rootsmagic.adapter import RootsMagicDatabase

logger = logging.getLogger(__name__)


class ModelTrainer:
    """Unified trainer for all ML models."""

    def __init__(self, config: Optional[MLConfig] = None):
        """
        Initialize trainer.

        Args:
            config: ML configuration
        """
        self.config = config or MLConfig()
        self.registry = ModelRegistry(self.config.model_dir)

    def train_duplicate_detector(
        self,
        database_path: str,
        model_type: str = "xgboost",
        version: str = "v1.0.0",
    ) -> Dict[str, Any]:
        """Train duplicate detection model."""
        logger.info("Training Duplicate Detector...")

        # Load database
        db = RootsMagicDatabase(database_path)

        # Generate training data
        data_gen = TrainingDataGenerator(db)
        labeled_pairs = data_gen.generate_duplicate_pairs(
            high_confidence_threshold=90.0,
            balance_classes=True,
        )

        # Convert to datasets
        from ..data import DuplicateDetectionDataset
        dataset = DuplicateDetectionDataset(labeled_pairs)
        X, y = dataset.to_numpy()

        # Create and train model
        model = DuplicateDetectionModel(model_type=model_type, config=self.config)
        metrics = model.train(X, y)

        # Save model
        model_path = self.registry.register_model(
            model=model.model,
            model_name="duplicate_detector",
            model_type=model_type,
            version=version,
            metrics=metrics,
            config=self.config.duplicate_detector_config,
        )

        logger.info(f"Duplicate detector trained and saved to {model_path}")
        return metrics

    def train_name_matcher(
        self,
        database_path: str,
        model_type: str = "siamese",
        version: str = "v1.0.0",
    ) -> Dict[str, Any]:
        """Train name matching model."""
        logger.info("Training Name Matcher...")

        # Load database
        db = RootsMagicDatabase(database_path)

        # Generate training data
        data_gen = TrainingDataGenerator(db)
        name_pairs = data_gen.generate_name_matching_data(num_samples=10000)

        # Create model
        model = NameMatchingModel(model_type=model_type, config=self.config)
        model.create_model()

        # Train (simplified - would need DataLoader in practice)
        from torch.utils.data import DataLoader
        from ..data import NameMatchingDataset

        dataset = NameMatchingDataset(name_pairs)
        loader = DataLoader(dataset, batch_size=32, shuffle=True)

        history = model.train(loader, num_epochs=50)

        # Save model
        model_path = self.config.model_dir / "name_matcher" / version
        model.save(model_path / "model.pt")

        self.registry.register_model(
            model=model,
            model_name="name_matcher",
            model_type=model_type,
            version=version,
            metrics={'status': 'trained'},
            config=self.config.name_matching_config,
        )

        logger.info(f"Name matcher trained and saved to {model_path}")
        return history

    def train_language_detector(
        self,
        database_path: str,
        model_type: str = "multinomial_nb",
        version: str = "v1.0.0",
    ) -> Dict[str, Any]:
        """Train language detection model."""
        logger.info("Training Language Detector...")

        # Load database
        db = RootsMagicDatabase(database_path)

        # Generate training data
        data_gen = TrainingDataGenerator(db)
        training_data = data_gen.generate_language_detection_data()

        # Create and train model
        model = LanguageDetectionModel(model_type=model_type, config=self.config)
        metrics = model.train(training_data)

        # Save model
        model_path = self.config.model_dir / "language_detector" / version / "model.pkl"
        model.save(model_path)

        self.registry.register_model(
            model=model,
            model_name="language_detector",
            model_type=model_type,
            version=version,
            metrics=metrics,
            config=self.config.language_detection_config,
        )

        logger.info(f"Language detector trained and saved to {model_path}")
        return metrics

    def train_quality_classifier(
        self,
        database_path: str,
        version: str = "v1.0.0",
    ) -> Dict[str, Any]:
        """Train data quality classifier."""
        logger.info("Training Quality Classifier...")

        # Load database
        db = RootsMagicDatabase(database_path)

        # Generate training data
        data_gen = TrainingDataGenerator(db)
        training_data = data_gen.generate_quality_classification_data()

        # Convert to datasets
        from ..data import QualityDataset
        dataset = QualityDataset(training_data)
        X, y = dataset.to_numpy()

        # Create and train model
        model = DataQualityClassifier(config=self.config)
        metrics = model.train(X, y)

        # Save model
        model_path = self.config.model_dir / "quality_classifier" / version / "model.pkl"
        model.save(model_path)

        self.registry.register_model(
            model=model,
            model_name="quality_classifier",
            model_type="random_forest",
            version=version,
            metrics=metrics,
            config=self.config.quality_classifier_config,
        )

        logger.info(f"Quality classifier trained and saved to {model_path}")
        return metrics
