"""Integration tests for ML models."""

import pytest
import numpy as np
from pathlib import Path
import tempfile

from gedmerge.ml.models import (
    DuplicateDetectionModel,
    NameMatchingModel,
    LanguageDetectionModel,
    DataQualityClassifier,
)
from gedmerge.ml.utils import MLConfig, FeatureExtractor
from gedmerge.ml.data import TrainingDataGenerator, LabeledPair, PairwiseFeatures


@pytest.fixture
def ml_config():
    """Create ML config for testing."""
    return MLConfig(
        batch_size=8,
        num_epochs=5,  # Reduced for testing
        early_stopping_patience=2,
    )


@pytest.fixture
def feature_extractor():
    """Create feature extractor."""
    return FeatureExtractor()


class TestDuplicateDetectionModel:
    """Test duplicate detection model."""

    def test_model_creation(self, ml_config):
        """Test model can be created."""
        model = DuplicateDetectionModel(model_type="xgboost", config=ml_config)
        assert model is not None
        assert model.model_type == "xgboost"

    def test_model_training(self, ml_config):
        """Test model training."""
        # Create synthetic training data
        np.random.seed(42)
        X = np.random.rand(100, 23)  # 23 features
        y = np.random.randint(0, 2, 100)  # Binary labels

        model = DuplicateDetectionModel(model_type="random_forest", config=ml_config)
        metrics = model.train(X, y, validation_split=0.2)

        assert 'accuracy' in metrics
        assert 'f1' in metrics
        assert 0.0 <= metrics['accuracy'] <= 1.0

    def test_model_save_load(self, ml_config):
        """Test model saving and loading."""
        # Train a simple model
        X = np.random.rand(50, 23)
        y = np.random.randint(0, 2, 50)

        model = DuplicateDetectionModel(model_type="random_forest", config=ml_config)
        model.train(X, y)

        # Save
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "model.pkl"
            model.save(filepath)

            # Load
            loaded_model = DuplicateDetectionModel.load(filepath)
            assert loaded_model is not None
            assert loaded_model.model_type == "random_forest"

            # Test predictions are the same
            pred1 = model.predict_batch(X[:5])
            pred2 = loaded_model.predict_batch(X[:5])
            np.testing.assert_array_equal(pred1[0], pred2[0])

    def test_feature_importance(self, ml_config):
        """Test feature importance extraction."""
        X = np.random.rand(50, 23)
        y = np.random.randint(0, 2, 50)

        model = DuplicateDetectionModel(model_type="random_forest", config=ml_config)
        model.train(X, y)

        importance = model.get_feature_importance()
        assert len(importance) == 23
        assert all(0.0 <= v <= 1.0 for v in importance.values())
        assert abs(sum(importance.values()) - 1.0) < 0.01  # Should sum to ~1


class TestNameMatchingModel:
    """Test name matching model."""

    def test_model_creation(self, ml_config):
        """Test model can be created."""
        model = NameMatchingModel(model_type="siamese", config=ml_config, device="cpu")
        assert model is not None
        assert model.model_type == "siamese"

    def test_character_encoding(self, ml_config):
        """Test character encoding."""
        model = NameMatchingModel(model_type="siamese", config=ml_config)

        encoded = model.encode_name("John Smith", max_length=64)
        assert encoded.shape == (64,)
        assert encoded[0] > 0  # 'J' should be encoded

    def test_prediction_siamese(self, ml_config):
        """Test Siamese network prediction."""
        model = NameMatchingModel(model_type="siamese", config=ml_config, device="cpu")
        model.create_model()

        result = model.predict("John Smith", "Jean Smith")

        assert hasattr(result, 'similarity')
        assert hasattr(result, 'is_match')
        assert 0.0 <= result.similarity <= 1.0


class TestLanguageDetectionModel:
    """Test language detection model."""

    def test_model_creation(self, ml_config):
        """Test model can be created."""
        model = LanguageDetectionModel(model_type="multinomial_nb", config=ml_config)
        assert model is not None
        assert model.model_type == "multinomial_nb"

    def test_model_training(self, ml_config):
        """Test model training."""
        # Create synthetic training data
        training_data = [
            ("John Smith", "en"),
            ("Jean Dupont", "fr"),
            ("Hans Müller", "de"),
            ("Giovanni Rossi", "it"),
            ("José García", "es"),
        ] * 20  # Repeat for more samples

        model = LanguageDetectionModel(model_type="multinomial_nb", config=ml_config)
        metrics = model.train(training_data, validation_split=0.2)

        assert 'accuracy' in metrics
        assert metrics['accuracy'] > 0.0

    def test_prediction(self, ml_config):
        """Test language prediction."""
        training_data = [
            ("John Smith", "en"),
            ("Jean Dupont", "fr"),
            ("Hans Müller", "de"),
        ] * 10

        model = LanguageDetectionModel(model_type="multinomial_nb", config=ml_config)
        model.train(training_data)

        language, confidence = model.predict("François Martin")

        assert language in ['en', 'fr', 'de']
        assert 0.0 <= confidence <= 1.0

    def test_model_save_load(self, ml_config):
        """Test model saving and loading."""
        training_data = [("John Smith", "en"), ("Jean Dupont", "fr")] * 10

        model = LanguageDetectionModel(model_type="multinomial_nb", config=ml_config)
        model.train(training_data)

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "model.pkl"
            model.save(filepath)

            loaded_model = LanguageDetectionModel.load(filepath)
            assert loaded_model is not None

            # Test predictions are the same
            lang1, conf1 = model.predict("Test Name")
            lang2, conf2 = loaded_model.predict("Test Name")
            assert lang1 == lang2
            assert abs(conf1 - conf2) < 0.01


class TestDataQualityClassifier:
    """Test data quality classifier."""

    def test_model_creation(self, ml_config):
        """Test model can be created."""
        model = DataQualityClassifier(config=ml_config)
        assert model is not None
        assert len(model.quality_categories) > 0

    def test_model_training(self, ml_config):
        """Test model training."""
        # Create synthetic multi-label data
        np.random.seed(42)
        X = np.random.rand(100, 25)  # 25 features
        y = np.random.randint(0, 2, (100, 7))  # 7 quality categories

        model = DataQualityClassifier(config=ml_config)
        metrics = model.train(X, y, validation_split=0.2)

        assert 'overall' in metrics
        assert 'accuracy' in metrics['overall']

    def test_batch_prediction(self, ml_config):
        """Test batch prediction."""
        X = np.random.rand(50, 25)
        y = np.random.randint(0, 2, (50, 7))

        model = DataQualityClassifier(config=ml_config)
        model.train(X, y)

        predictions = model.predict_batch(X[:10])
        assert predictions.shape == (10, 7)
        assert np.all((predictions == 0) | (predictions == 1))


class TestFeatureExtractor:
    """Test feature extraction."""

    def test_pairwise_vector_shape(self, feature_extractor):
        """Test pairwise feature vector has correct shape."""
        # Create mock PairwiseFeatures
        features = PairwiseFeatures(
            name_similarity=0.8,
            phonetic_similarity=0.7,
            surname_similarity=0.9,
            given_name_similarity=0.75,
            exact_name_match=False,
            levenshtein_distance=5,
            jaro_winkler_similarity=0.85,
            token_set_ratio=0.9,
            birth_date_match=0.8,
            death_date_match=0.7,
            age_difference=2,
            date_conflict=False,
            birth_place_similarity=0.6,
            death_place_similarity=0.5,
            place_overlap=0.4,
            shared_parents=1,
            shared_spouses=0,
            shared_children=2,
            relationship_overlap_score=0.3,
            sex_conflict=False,
            significant_age_gap=False,
            different_locations=False,
            overall_similarity=0.75,
        )

        vector = feature_extractor.to_pairwise_vector(features)
        assert vector.shape == (23,)
        assert vector.dtype == np.float32


def test_integration_workflow(ml_config):
    """Test complete workflow: generate data -> train -> predict."""
    # This is a simplified integration test
    # In practice, this would use a real database

    # 1. Create synthetic training data
    X = np.random.rand(100, 23)
    y = np.random.randint(0, 2, 100)

    # 2. Train model
    model = DuplicateDetectionModel(model_type="random_forest", config=ml_config)
    metrics = model.train(X, y, validation_split=0.2)

    # 3. Make predictions
    predictions, confidences = model.predict_batch(X[:10])

    assert predictions.shape == (10,)
    assert confidences.shape == (10,)
    assert all(0.0 <= c <= 1.0 for c in confidences)

    # 4. Save and load
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = Path(tmpdir) / "model.pkl"
        model.save(filepath)

        loaded_model = DuplicateDetectionModel.load(filepath)

        # Verify loaded model works
        predictions2, confidences2 = loaded_model.predict_batch(X[:10])
        np.testing.assert_array_equal(predictions, predictions2)
        np.testing.assert_array_almost_equal(confidences, confidences2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
