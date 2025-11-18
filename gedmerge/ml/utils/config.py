"""Configuration for ML models and training."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional


@dataclass(slots=True)
class MLConfig:
    """Configuration for ML models and training."""

    # Model storage
    model_dir: Path = field(default_factory=lambda: Path("models/saved"))
    cache_dir: Path = field(default_factory=lambda: Path("models/cache"))

    # Training parameters
    batch_size: int = 32
    learning_rate: float = 0.001
    num_epochs: int = 100
    early_stopping_patience: int = 10
    validation_split: float = 0.2
    random_seed: int = 42

    # Duplicate Detection Model
    duplicate_detector_config: Dict[str, Any] = field(default_factory=lambda: {
        "model_type": "xgboost",  # or "lightgbm", "random_forest"
        "n_estimators": 100,
        "max_depth": 6,
        "learning_rate": 0.1,
        "min_confidence_threshold": 60.0,
        "high_confidence_threshold": 85.0,
    })

    # Name Matching Model
    name_matching_config: Dict[str, Any] = field(default_factory=lambda: {
        "model_type": "siamese",  # or "transformer"
        "embedding_dim": 128,
        "hidden_dim": 256,
        "dropout": 0.3,
        "margin": 1.0,  # for contrastive loss
        "pretrained_model": "sentence-transformers/all-MiniLM-L6-v2",
    })

    # Language Detection Model
    language_detection_config: Dict[str, Any] = field(default_factory=lambda: {
        "model_type": "fasttext",  # or "multinomial_nb"
        "supported_languages": ["en", "fr", "de", "es", "it", "pt", "la"],
        "min_confidence": 0.7,
        "ngram_range": (2, 5),  # character n-grams
    })

    # Graph Neural Network
    gnn_config: Dict[str, Any] = field(default_factory=lambda: {
        "model_type": "gat",  # Graph Attention Network
        "hidden_channels": 64,
        "num_layers": 3,
        "heads": 4,
        "dropout": 0.3,
    })

    # Data Quality Classifier
    quality_classifier_config: Dict[str, Any] = field(default_factory=lambda: {
        "model_type": "random_forest",
        "n_estimators": 200,
        "max_depth": 10,
        "class_weight": "balanced",
        "quality_categories": [
            "reversed_names",
            "embedded_variants",
            "titles_in_wrong_field",
            "missing_data",
            "invalid_dates",
            "duplicate_entries",
            "inconsistent_formatting",
        ],
    })

    # MLflow tracking
    mlflow_tracking_uri: Optional[str] = None
    mlflow_experiment_name: str = "gedmerge_ml"

    # Performance monitoring
    enable_monitoring: bool = True
    log_predictions: bool = True
    metrics_retention_days: int = 90

    def __post_init__(self):
        """Ensure directories exist."""
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)


# Global configuration instance
default_config = MLConfig()
