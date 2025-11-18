"""Model registry for managing trained ML models."""

from pathlib import Path
from typing import Dict, Any, Optional, Type
import joblib
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for managing and versioning ML models."""

    def __init__(self, registry_dir: Path):
        """
        Initialize model registry.

        Args:
            registry_dir: Directory to store models and metadata
        """
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_file = self.registry_dir / "registry.json"
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """Load registry metadata."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {"models": {}, "versions": {}}

    def _save_metadata(self):
        """Save registry metadata."""
        with open(self.metadata_file, 'w') as f:
            json.dump(self.metadata, f, indent=2)

    def register_model(
        self,
        model: Any,
        model_name: str,
        model_type: str,
        version: str,
        metrics: Optional[Dict[str, float]] = None,
        config: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
    ) -> Path:
        """
        Register a trained model.

        Args:
            model: The trained model object
            model_name: Name of the model (e.g., "duplicate_detector")
            model_type: Type of model (e.g., "xgboost", "neural_network")
            version: Version string (e.g., "v1.0.0")
            metrics: Performance metrics
            config: Model configuration
            tags: Additional tags

        Returns:
            Path to saved model
        """
        # Create version directory
        model_dir = self.registry_dir / model_name / version
        model_dir.mkdir(parents=True, exist_ok=True)

        # Save model
        model_path = model_dir / "model.pkl"
        joblib.dump(model, model_path)

        # Save metadata
        model_metadata = {
            "model_name": model_name,
            "model_type": model_type,
            "version": version,
            "registered_at": datetime.now().isoformat(),
            "metrics": metrics or {},
            "config": config or {},
            "tags": tags or {},
            "model_path": str(model_path),
        }

        # Save model-specific metadata
        metadata_path = model_dir / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(model_metadata, f, indent=2)

        # Update registry
        if model_name not in self.metadata["models"]:
            self.metadata["models"][model_name] = {}

        self.metadata["models"][model_name][version] = model_metadata

        # Track latest version
        if model_name not in self.metadata["versions"]:
            self.metadata["versions"][model_name] = version
        else:
            # Update if this is newer (simple string comparison)
            if version > self.metadata["versions"][model_name]:
                self.metadata["versions"][model_name] = version

        self._save_metadata()

        logger.info(f"Registered model {model_name} version {version}")
        return model_path

    def load_model(
        self,
        model_name: str,
        version: Optional[str] = None
    ) -> tuple[Any, Dict[str, Any]]:
        """
        Load a registered model.

        Args:
            model_name: Name of the model
            version: Version to load (defaults to latest)

        Returns:
            Tuple of (model, metadata)
        """
        # Get version
        if version is None:
            version = self.get_latest_version(model_name)

        # Check if model exists
        if model_name not in self.metadata["models"]:
            raise ValueError(f"Model {model_name} not found in registry")

        if version not in self.metadata["models"][model_name]:
            raise ValueError(f"Version {version} of model {model_name} not found")

        # Load model
        model_metadata = self.metadata["models"][model_name][version]
        model_path = Path(model_metadata["model_path"])

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        model = joblib.load(model_path)

        logger.info(f"Loaded model {model_name} version {version}")
        return model, model_metadata

    def get_latest_version(self, model_name: str) -> str:
        """
        Get latest version of a model.

        Args:
            model_name: Name of the model

        Returns:
            Latest version string
        """
        if model_name not in self.metadata["versions"]:
            raise ValueError(f"No versions found for model {model_name}")

        return self.metadata["versions"][model_name]

    def list_models(self) -> Dict[str, list]:
        """
        List all registered models.

        Returns:
            Dictionary mapping model names to list of versions
        """
        return {
            name: list(versions.keys())
            for name, versions in self.metadata["models"].items()
        }

    def get_model_info(self, model_name: str, version: Optional[str] = None) -> Dict[str, Any]:
        """
        Get metadata for a model.

        Args:
            model_name: Name of the model
            version: Version (defaults to latest)

        Returns:
            Model metadata
        """
        if version is None:
            version = self.get_latest_version(model_name)

        return self.metadata["models"][model_name][version]

    def compare_versions(
        self,
        model_name: str,
        version1: str,
        version2: str
    ) -> Dict[str, Any]:
        """
        Compare metrics between two versions.

        Args:
            model_name: Name of the model
            version1: First version
            version2: Second version

        Returns:
            Comparison dictionary
        """
        meta1 = self.get_model_info(model_name, version1)
        meta2 = self.get_model_info(model_name, version2)

        comparison = {
            "model_name": model_name,
            "version1": version1,
            "version2": version2,
            "metrics_comparison": {},
        }

        # Compare metrics
        metrics1 = meta1.get("metrics", {})
        metrics2 = meta2.get("metrics", {})

        all_metrics = set(metrics1.keys()) | set(metrics2.keys())
        for metric in all_metrics:
            val1 = metrics1.get(metric, None)
            val2 = metrics2.get(metric, None)

            if val1 is not None and val2 is not None:
                diff = val2 - val1
                pct_change = (diff / val1 * 100) if val1 != 0 else 0
                comparison["metrics_comparison"][metric] = {
                    "v1": val1,
                    "v2": val2,
                    "diff": diff,
                    "pct_change": pct_change,
                }

        return comparison

    def delete_version(self, model_name: str, version: str):
        """
        Delete a model version.

        Args:
            model_name: Name of the model
            version: Version to delete
        """
        if model_name not in self.metadata["models"]:
            raise ValueError(f"Model {model_name} not found")

        if version not in self.metadata["models"][model_name]:
            raise ValueError(f"Version {version} not found")

        # Delete files
        model_dir = self.registry_dir / model_name / version
        if model_dir.exists():
            import shutil
            shutil.rmtree(model_dir)

        # Update metadata
        del self.metadata["models"][model_name][version]

        # Update latest version if needed
        if self.metadata["versions"].get(model_name) == version:
            remaining_versions = list(self.metadata["models"][model_name].keys())
            if remaining_versions:
                self.metadata["versions"][model_name] = max(remaining_versions)
            else:
                del self.metadata["versions"][model_name]
                del self.metadata["models"][model_name]

        self._save_metadata()

        logger.info(f"Deleted model {model_name} version {version}")
