"""PyTorch datasets for ML training."""

from typing import List, Tuple, Optional
import torch
from torch.utils.data import Dataset
import numpy as np
import pandas as pd
from pathlib import Path

from .data_generator import LabeledPair
from ..utils.feature_extractor import FeatureExtractor


class DuplicateDetectionDataset(Dataset):
    """Dataset for duplicate detection training."""

    def __init__(
        self,
        data: List[LabeledPair],
        feature_extractor: Optional[FeatureExtractor] = None,
    ):
        """
        Initialize dataset.

        Args:
            data: List of labeled pairs
            feature_extractor: Feature extractor
        """
        self.data = data
        self.feature_extractor = feature_extractor or FeatureExtractor()

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Get item by index.

        Returns:
            Tuple of (features, label)
        """
        pair = self.data[idx]

        # Convert features to tensor
        features = self.feature_extractor.to_pairwise_vector(pair.features)
        label = float(pair.is_duplicate)

        return torch.FloatTensor(features), torch.FloatTensor([label])

    @classmethod
    def from_csv(cls, filepath: Path) -> "DuplicateDetectionDataset":
        """Load dataset from CSV file."""
        df = pd.read_csv(filepath)

        # This is a simplified version - would need to reconstruct Person objects
        # For now, we'll just load the features directly
        raise NotImplementedError("Loading from CSV not yet implemented")

    def to_numpy(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Convert entire dataset to numpy arrays.

        Returns:
            Tuple of (X, y) arrays
        """
        X = []
        y = []

        for pair in self.data:
            features = self.feature_extractor.to_pairwise_vector(pair.features)
            X.append(features)
            y.append(float(pair.is_duplicate))

        return np.array(X), np.array(y)


class NameMatchingDataset(Dataset):
    """Dataset for name matching training (Siamese network)."""

    def __init__(
        self,
        name_pairs: List[Tuple[str, str, float]],
        tokenizer=None,
        max_length: int = 64,
    ):
        """
        Initialize dataset.

        Args:
            name_pairs: List of (name1, name2, similarity) tuples
            tokenizer: Tokenizer for encoding names
            max_length: Maximum sequence length
        """
        self.name_pairs = name_pairs
        self.tokenizer = tokenizer
        self.max_length = max_length

    def __len__(self) -> int:
        return len(self.name_pairs)

    def __getitem__(self, idx: int):
        """Get item by index."""
        name1, name2, similarity = self.name_pairs[idx]

        if self.tokenizer:
            # Tokenize names
            enc1 = self.tokenizer(
                name1,
                max_length=self.max_length,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            )
            enc2 = self.tokenizer(
                name2,
                max_length=self.max_length,
                padding='max_length',
                truncation=True,
                return_tensors='pt'
            )

            return {
                'input_ids_1': enc1['input_ids'].squeeze(),
                'attention_mask_1': enc1['attention_mask'].squeeze(),
                'input_ids_2': enc2['input_ids'].squeeze(),
                'attention_mask_2': enc2['attention_mask'].squeeze(),
                'label': torch.FloatTensor([similarity]),
            }
        else:
            # Character-level encoding
            name1_chars = self._encode_name(name1)
            name2_chars = self._encode_name(name2)

            return {
                'name1': torch.LongTensor(name1_chars),
                'name2': torch.LongTensor(name2_chars),
                'label': torch.FloatTensor([similarity]),
            }

    def _encode_name(self, name: str) -> List[int]:
        """Encode name as character IDs."""
        # Simple character encoding (a=1, b=2, etc.)
        name = name.lower()
        encoded = []

        for char in name[:self.max_length]:
            if char.isalpha():
                encoded.append(ord(char) - ord('a') + 1)
            elif char == ' ':
                encoded.append(27)
            else:
                encoded.append(28)  # Other

        # Pad to max_length
        while len(encoded) < self.max_length:
            encoded.append(0)  # Padding

        return encoded[:self.max_length]


class QualityDataset(Dataset):
    """Dataset for data quality classification."""

    def __init__(
        self,
        data: List[Tuple[any, List[str]]],  # (person, issues)
        feature_extractor: Optional[FeatureExtractor] = None,
        quality_categories: Optional[List[str]] = None,
    ):
        """
        Initialize dataset.

        Args:
            data: List of (person, issues) tuples
            feature_extractor: Feature extractor
            quality_categories: List of quality issue categories
        """
        self.data = data
        self.feature_extractor = feature_extractor or FeatureExtractor()

        self.quality_categories = quality_categories or [
            "reversed_names",
            "embedded_variants",
            "titles_in_wrong_field",
            "missing_data",
            "invalid_dates",
            "placeholder_name",
            "inconsistent_formatting",
        ]

        # Create label mapping
        self.label_to_idx = {label: idx for idx, label in enumerate(self.quality_categories)}

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, idx: int):
        """Get item by index."""
        person, issues = self.data[idx]

        # Extract person features
        person_features = self.feature_extractor.extract_person_features(person)
        features = self.feature_extractor.to_feature_vector(person_features)

        # Create multi-label target (one-hot encoding)
        target = np.zeros(len(self.quality_categories), dtype=np.float32)
        for issue in issues:
            if issue in self.label_to_idx:
                target[self.label_to_idx[issue]] = 1.0

        return torch.FloatTensor(features), torch.FloatTensor(target)

    def to_numpy(self) -> Tuple[np.ndarray, np.ndarray]:
        """Convert to numpy arrays."""
        X = []
        y = []

        for person, issues in self.data:
            person_features = self.feature_extractor.extract_person_features(person)
            features = self.feature_extractor.to_feature_vector(person_features)
            X.append(features)

            # Create multi-label target
            target = np.zeros(len(self.quality_categories), dtype=np.float32)
            for issue in issues:
                if issue in self.label_to_idx:
                    target[self.label_to_idx[issue]] = 1.0
            y.append(target)

        return np.array(X), np.array(y)
