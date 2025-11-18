"""Language Detection using FastText or Multinomial Naive Bayes."""

from typing import List, Tuple, Dict, Optional
import numpy as np
from pathlib import Path
import logging
import tempfile
import subprocess

from sklearn.naive_bayes import MultinomialNB
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib

from ..utils.config import MLConfig

logger = logging.getLogger(__name__)


class LanguageDetectionModel:
    """
    Language detection model for genealogical names.

    Supports FastText or Multinomial Naive Bayes with character n-grams.
    """

    def __init__(
        self,
        model_type: str = "multinomial_nb",
        config: Optional[MLConfig] = None,
    ):
        """
        Initialize model.

        Args:
            model_type: "fasttext" or "multinomial_nb"
            config: ML configuration
        """
        self.model_type = model_type
        self.config = config or MLConfig()
        self.model = None
        self.vectorizer = None
        self.label_to_lang = {}
        self.lang_to_label = {}

        # Supported languages
        self.supported_languages = self.config.language_detection_config.get(
            'supported_languages',
            ['en', 'fr', 'de', 'es', 'it', 'pt', 'la']
        )

    def train(
        self,
        training_data: List[Tuple[str, str]],
        validation_split: float = 0.2,
    ) -> Dict[str, float]:
        """
        Train the model.

        Args:
            training_data: List of (name, language_code) tuples
            validation_split: Fraction for validation

        Returns:
            Training metrics
        """
        logger.info(f"Training {self.model_type} language detector...")
        logger.info(f"Training samples: {len(training_data)}")

        # Extract names and labels
        names = [name for name, _ in training_data]
        languages = [lang for _, lang in training_data]

        # Create label mapping
        unique_langs = sorted(set(languages))
        self.label_to_lang = {i: lang for i, lang in enumerate(unique_langs)}
        self.lang_to_label = {lang: i for i, lang in enumerate(unique_langs)}

        logger.info(f"Languages: {unique_langs}")

        # Convert to numeric labels
        y = np.array([self.lang_to_label[lang] for lang in languages])

        # Split data
        X_train, X_val, y_train, y_val = train_test_split(
            names, y,
            test_size=validation_split,
            random_state=self.config.random_seed,
            stratify=y,
        )

        if self.model_type == "multinomial_nb":
            return self._train_multinomial_nb(X_train, y_train, X_val, y_val)
        elif self.model_type == "fasttext":
            return self._train_fasttext(X_train, y_train, X_val, y_val)
        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

    def _train_multinomial_nb(
        self,
        X_train: List[str],
        y_train: np.ndarray,
        X_val: List[str],
        y_val: np.ndarray,
    ) -> Dict[str, float]:
        """Train Multinomial Naive Bayes model."""
        # Create character n-gram vectorizer
        ngram_range = self.config.language_detection_config.get('ngram_range', (2, 5))

        self.vectorizer = CountVectorizer(
            analyzer='char',
            ngram_range=ngram_range,
            lowercase=True,
            max_features=10000,
        )

        # Vectorize
        X_train_vec = self.vectorizer.fit_transform(X_train)
        X_val_vec = self.vectorizer.transform(X_val)

        # Train model
        self.model = MultinomialNB(alpha=0.1)
        self.model.fit(X_train_vec, y_train)

        # Evaluate
        y_pred = self.model.predict(X_val_vec)
        accuracy = accuracy_score(y_val, y_pred)

        logger.info(f"Validation Accuracy: {accuracy:.4f}")

        # Detailed report
        y_val_langs = [self.label_to_lang[label] for label in y_val]
        y_pred_langs = [self.label_to_lang[label] for label in y_pred]

        report = classification_report(y_val_langs, y_pred_langs, output_dict=True)
        logger.info("\nClassification Report:")
        for lang in self.supported_languages:
            if lang in report:
                metrics = report[lang]
                logger.info(
                    f"  {lang}: precision={metrics['precision']:.3f}, "
                    f"recall={metrics['recall']:.3f}, f1={metrics['f1-score']:.3f}"
                )

        return {
            'accuracy': accuracy,
            'report': report,
        }

    def _train_fasttext(
        self,
        X_train: List[str],
        y_train: np.ndarray,
        X_val: List[str],
        y_val: np.ndarray,
    ) -> Dict[str, float]:
        """Train FastText model."""
        try:
            import fasttext
        except ImportError:
            logger.error("fasttext not installed. Using multinomial_nb instead.")
            return self._train_multinomial_nb(X_train, y_train, X_val, y_val)

        # Create temporary training file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            train_file = f.name
            for name, label in zip(X_train, y_train):
                lang = self.label_to_lang[label]
                # FastText format: __label__<lang> <text>
                f.write(f"__label__{lang} {name}\n")

        # Train model
        self.model = fasttext.train_supervised(
            input=train_file,
            epoch=25,
            lr=1.0,
            wordNgrams=2,
            dim=100,
            loss='softmax',
        )

        # Clean up temp file
        Path(train_file).unlink()

        # Evaluate
        correct = 0
        for name, label in zip(X_val, y_val):
            pred_label, prob = self.predict(name)
            if pred_label == self.label_to_lang[label]:
                correct += 1

        accuracy = correct / len(X_val)
        logger.info(f"Validation Accuracy: {accuracy:.4f}")

        return {'accuracy': accuracy}

    def predict(self, name: str) -> Tuple[str, float]:
        """
        Predict language of a name.

        Args:
            name: Name to classify

        Returns:
            Tuple of (language_code, confidence)
        """
        if self.model is None:
            raise ValueError("Model not trained.")

        if self.model_type == "multinomial_nb":
            # Vectorize
            name_vec = self.vectorizer.transform([name])

            # Predict
            pred_label = self.model.predict(name_vec)[0]
            pred_proba = self.model.predict_proba(name_vec)[0]

            language = self.label_to_lang[pred_label]
            confidence = float(pred_proba[pred_label])

        elif self.model_type == "fasttext":
            # FastText prediction
            predictions = self.model.predict(name, k=1)
            labels, probs = predictions

            # Extract language from label
            language = labels[0].replace('__label__', '')
            confidence = float(probs[0])

        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        return language, confidence

    def predict_batch(
        self,
        names: List[str],
    ) -> List[Tuple[str, float]]:
        """
        Predict languages for batch of names.

        Args:
            names: List of names

        Returns:
            List of (language_code, confidence) tuples
        """
        return [self.predict(name) for name in names]

    def save(self, filepath: Path):
        """Save model."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if self.model_type == "multinomial_nb":
            joblib.dump({
                'model': self.model,
                'vectorizer': self.vectorizer,
                'label_to_lang': self.label_to_lang,
                'lang_to_label': self.lang_to_label,
                'model_type': self.model_type,
                'config': self.config,
            }, filepath)
        elif self.model_type == "fasttext":
            self.model.save_model(str(filepath))
            # Save label mappings separately
            joblib.dump({
                'label_to_lang': self.label_to_lang,
                'lang_to_label': self.lang_to_label,
                'model_type': self.model_type,
            }, filepath.with_suffix('.labels'))

        logger.info(f"Model saved to {filepath}")

    @classmethod
    def load(cls, filepath: Path) -> "LanguageDetectionModel":
        """Load model."""
        filepath = Path(filepath)

        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")

        # Try to load as joblib first
        try:
            data = joblib.load(filepath)
            model_type = data['model_type']

            model_obj = cls(model_type=model_type, config=data.get('config'))
            model_obj.model = data['model']
            model_obj.label_to_lang = data['label_to_lang']
            model_obj.lang_to_label = data['lang_to_label']

            if model_type == "multinomial_nb":
                model_obj.vectorizer = data['vectorizer']

        except:
            # Try to load as FastText
            try:
                import fasttext
                model_obj = cls(model_type="fasttext")
                model_obj.model = fasttext.load_model(str(filepath))

                # Load label mappings
                labels_file = filepath.with_suffix('.labels')
                if labels_file.exists():
                    data = joblib.load(labels_file)
                    model_obj.label_to_lang = data['label_to_lang']
                    model_obj.lang_to_label = data['lang_to_label']
            except Exception as e:
                raise ValueError(f"Could not load model: {e}")

        logger.info(f"Model loaded from {filepath}")
        return model_obj
