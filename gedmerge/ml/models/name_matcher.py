"""Neural Name Matching using Siamese Networks or Transformers."""

from typing import Optional, Tuple, Dict, Any
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
import numpy as np
from pathlib import Path
import logging
from sentence_transformers import SentenceTransformer
from dataclasses import dataclass

from ..utils.config import MLConfig

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class NameMatchResult:
    """Result of name matching."""

    name1: str
    name2: str
    similarity: float
    is_match: bool
    embedding1: Optional[np.ndarray] = None
    embedding2: Optional[np.ndarray] = None


class SiameseNetwork(nn.Module):
    """Siamese neural network for name matching."""

    def __init__(
        self,
        vocab_size: int = 100,
        embedding_dim: int = 128,
        hidden_dim: int = 256,
        dropout: float = 0.3,
    ):
        """
        Initialize Siamese network.

        Args:
            vocab_size: Size of character vocabulary
            embedding_dim: Dimension of character embeddings
            hidden_dim: Hidden layer dimension
            dropout: Dropout rate
        """
        super().__init__()

        # Character embedding layer
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)

        # Shared encoder (LSTM)
        self.encoder = nn.LSTM(
            embedding_dim,
            hidden_dim,
            num_layers=2,
            batch_first=True,
            dropout=dropout,
            bidirectional=True,
        )

        # Projection layer
        self.projection = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, embedding_dim),
        )

    def forward_one(self, x: torch.Tensor) -> torch.Tensor:
        """Encode one name."""
        # Embed characters
        embedded = self.embedding(x)  # (batch, seq_len, embedding_dim)

        # Encode with LSTM
        lstm_out, (hidden, _) = self.encoder(embedded)

        # Use last hidden state (concatenate forward and backward)
        hidden = torch.cat([hidden[-2], hidden[-1]], dim=1)

        # Project to embedding space
        embedding = self.projection(hidden)

        # L2 normalize
        embedding = F.normalize(embedding, p=2, dim=1)

        return embedding

    def forward(
        self,
        name1: torch.Tensor,
        name2: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Forward pass for both names.

        Returns:
            Tuple of (embedding1, embedding2, similarity)
        """
        emb1 = self.forward_one(name1)
        emb2 = self.forward_one(name2)

        # Cosine similarity
        similarity = F.cosine_similarity(emb1, emb2)

        return emb1, emb2, similarity


class NameMatchingModel:
    """
    Neural name matching model.

    Uses either a custom Siamese network or pre-trained transformer model
    for learning name similarity.
    """

    def __init__(
        self,
        model_type: str = "siamese",
        config: Optional[MLConfig] = None,
        device: Optional[str] = None,
    ):
        """
        Initialize model.

        Args:
            model_type: "siamese" or "transformer"
            config: ML configuration
            device: Device to use (cuda/cpu)
        """
        self.model_type = model_type
        self.config = config or MLConfig()

        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model = None
        self.optimizer = None
        self.char_to_idx = self._build_char_vocab()

        logger.info(f"Using device: {self.device}")

    def _build_char_vocab(self) -> Dict[str, int]:
        """Build character vocabulary."""
        # Basic character vocabulary
        chars = ' abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-\''

        char_to_idx = {char: idx + 1 for idx, char in enumerate(chars)}
        char_to_idx['<PAD>'] = 0
        char_to_idx['<UNK>'] = len(char_to_idx)

        return char_to_idx

    def create_model(self):
        """Create the model."""
        if self.model_type == "siamese":
            model_config = self.config.name_matching_config

            model = SiameseNetwork(
                vocab_size=len(self.char_to_idx),
                embedding_dim=model_config.get('embedding_dim', 128),
                hidden_dim=model_config.get('hidden_dim', 256),
                dropout=model_config.get('dropout', 0.3),
            )

            model = model.to(self.device)
            self.model = model

            # Create optimizer
            self.optimizer = torch.optim.Adam(
                model.parameters(),
                lr=self.config.learning_rate,
            )

        elif self.model_type == "transformer":
            # Use pre-trained sentence transformer
            model_name = self.config.name_matching_config.get(
                'pretrained_model',
                'sentence-transformers/all-MiniLM-L6-v2'
            )

            self.model = SentenceTransformer(model_name, device=str(self.device))

        else:
            raise ValueError(f"Unknown model type: {self.model_type}")

        logger.info(f"Created {self.model_type} model")

    def encode_name(self, name: str, max_length: int = 64) -> torch.Tensor:
        """Encode name as character indices."""
        encoded = []

        for char in name[:max_length]:
            if char in self.char_to_idx:
                encoded.append(self.char_to_idx[char])
            else:
                encoded.append(self.char_to_idx['<UNK>'])

        # Pad to max_length
        while len(encoded) < max_length:
            encoded.append(self.char_to_idx['<PAD>'])

        return torch.LongTensor(encoded[:max_length])

    def train(
        self,
        train_loader: DataLoader,
        num_epochs: int = 100,
        validation_loader: Optional[DataLoader] = None,
    ) -> Dict[str, Any]:
        """
        Train the model.

        Args:
            train_loader: Training data loader
            num_epochs: Number of epochs
            validation_loader: Validation data loader

        Returns:
            Training history
        """
        if self.model is None:
            self.create_model()

        if self.model_type == "transformer":
            # For transformers, use built-in training
            return self._train_transformer(train_loader, num_epochs, validation_loader)
        else:
            return self._train_siamese(train_loader, num_epochs, validation_loader)

    def _train_siamese(
        self,
        train_loader: DataLoader,
        num_epochs: int,
        validation_loader: Optional[DataLoader],
    ) -> Dict[str, Any]:
        """Train Siamese network."""
        logger.info(f"Training Siamese network for {num_epochs} epochs...")

        history = {'train_loss': [], 'val_loss': []}
        best_val_loss = float('inf')
        patience = self.config.early_stopping_patience
        patience_counter = 0

        for epoch in range(num_epochs):
            # Training
            self.model.train()
            train_losses = []

            for batch in train_loader:
                name1 = batch['name1'].to(self.device)
                name2 = batch['name2'].to(self.device)
                target_similarity = batch['label'].to(self.device)

                # Forward pass
                emb1, emb2, pred_similarity = self.model(name1, name2)

                # Contrastive loss
                loss = self._contrastive_loss(
                    emb1, emb2,
                    target_similarity,
                    margin=self.config.name_matching_config.get('margin', 1.0)
                )

                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                train_losses.append(loss.item())

            avg_train_loss = np.mean(train_losses)
            history['train_loss'].append(avg_train_loss)

            # Validation
            if validation_loader:
                val_loss = self._validate_siamese(validation_loader)
                history['val_loss'].append(val_loss)

                logger.info(
                    f"Epoch {epoch + 1}/{num_epochs} - "
                    f"Train Loss: {avg_train_loss:.4f}, Val Loss: {val_loss:.4f}"
                )

                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    patience_counter = 0
                else:
                    patience_counter += 1

                if patience_counter >= patience:
                    logger.info(f"Early stopping at epoch {epoch + 1}")
                    break
            else:
                logger.info(f"Epoch {epoch + 1}/{num_epochs} - Train Loss: {avg_train_loss:.4f}")

        return history

    def _validate_siamese(self, val_loader: DataLoader) -> float:
        """Validate Siamese network."""
        self.model.eval()
        val_losses = []

        with torch.no_grad():
            for batch in val_loader:
                name1 = batch['name1'].to(self.device)
                name2 = batch['name2'].to(self.device)
                target_similarity = batch['label'].to(self.device)

                emb1, emb2, pred_similarity = self.model(name1, name2)

                loss = self._contrastive_loss(
                    emb1, emb2,
                    target_similarity,
                    margin=self.config.name_matching_config.get('margin', 1.0)
                )

                val_losses.append(loss.item())

        return np.mean(val_losses)

    def _contrastive_loss(
        self,
        emb1: torch.Tensor,
        emb2: torch.Tensor,
        target_similarity: torch.Tensor,
        margin: float = 1.0,
    ) -> torch.Tensor:
        """
        Contrastive loss function.

        Args:
            emb1: First embeddings
            emb2: Second embeddings
            target_similarity: Target similarity (0 or 1)
            margin: Margin for dissimilar pairs

        Returns:
            Loss value
        """
        # Euclidean distance
        distance = F.pairwise_distance(emb1, emb2)

        # Contrastive loss
        # For similar pairs (target=1): minimize distance
        # For dissimilar pairs (target=0): maximize distance up to margin
        similar_loss = target_similarity * torch.pow(distance, 2)
        dissimilar_loss = (1 - target_similarity) * torch.pow(
            torch.clamp(margin - distance, min=0.0), 2
        )

        loss = torch.mean(similar_loss + dissimilar_loss)
        return loss

    def _train_transformer(
        self,
        train_loader: DataLoader,
        num_epochs: int,
        validation_loader: Optional[DataLoader],
    ) -> Dict[str, Any]:
        """Train transformer model."""
        # For transformers, we can use the sentence-transformers training API
        # This is a simplified version - in practice, you'd use sentence-transformers training

        logger.info("Transformer model training not fully implemented.")
        logger.info("Using pre-trained model as-is for inference.")

        return {'status': 'using_pretrained'}

    def predict(
        self,
        name1: str,
        name2: str,
        return_embeddings: bool = False,
    ) -> NameMatchResult:
        """
        Predict similarity between two names.

        Args:
            name1: First name
            name2: Second name
            return_embeddings: Whether to return embeddings

        Returns:
            Match result
        """
        if self.model is None:
            raise ValueError("Model not created. Call create_model() first.")

        if self.model_type == "siamese":
            return self._predict_siamese(name1, name2, return_embeddings)
        else:
            return self._predict_transformer(name1, name2, return_embeddings)

    def _predict_siamese(
        self,
        name1: str,
        name2: str,
        return_embeddings: bool,
    ) -> NameMatchResult:
        """Predict with Siamese network."""
        self.model.eval()

        with torch.no_grad():
            # Encode names
            enc1 = self.encode_name(name1).unsqueeze(0).to(self.device)
            enc2 = self.encode_name(name2).unsqueeze(0).to(self.device)

            # Get embeddings and similarity
            emb1, emb2, similarity = self.model(enc1, enc2)

            similarity = similarity.item()
            is_match = similarity > 0.7  # Threshold

            embeddings = None
            if return_embeddings:
                embeddings = (
                    emb1.cpu().numpy().flatten(),
                    emb2.cpu().numpy().flatten(),
                )

        return NameMatchResult(
            name1=name1,
            name2=name2,
            similarity=similarity,
            is_match=is_match,
            embedding1=embeddings[0] if embeddings else None,
            embedding2=embeddings[1] if embeddings else None,
        )

    def _predict_transformer(
        self,
        name1: str,
        name2: str,
        return_embeddings: bool,
    ) -> NameMatchResult:
        """Predict with transformer model."""
        # Encode names
        embeddings = self.model.encode([name1, name2])

        # Compute cosine similarity
        from sklearn.metrics.pairwise import cosine_similarity
        similarity = cosine_similarity(
            embeddings[0].reshape(1, -1),
            embeddings[1].reshape(1, -1)
        )[0, 0]

        is_match = similarity > 0.7

        return NameMatchResult(
            name1=name1,
            name2=name2,
            similarity=float(similarity),
            is_match=bool(is_match),
            embedding1=embeddings[0] if return_embeddings else None,
            embedding2=embeddings[1] if return_embeddings else None,
        )

    def save(self, filepath: Path):
        """Save model."""
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        if self.model_type == "siamese":
            torch.save({
                'model_state_dict': self.model.state_dict(),
                'optimizer_state_dict': self.optimizer.state_dict(),
                'char_to_idx': self.char_to_idx,
                'model_type': self.model_type,
                'config': self.config,
            }, filepath)
        else:
            # Save transformer
            self.model.save(str(filepath))

        logger.info(f"Model saved to {filepath}")

    @classmethod
    def load(cls, filepath: Path, device: Optional[str] = None) -> "NameMatchingModel":
        """Load model."""
        filepath = Path(filepath)

        # Try to determine model type
        if filepath.is_dir():
            # Transformer model
            model = cls(model_type="transformer", device=device)
            model.model = SentenceTransformer(str(filepath), device=str(model.device))
        else:
            # Siamese model
            checkpoint = torch.load(filepath, map_location='cpu')

            model = cls(
                model_type=checkpoint['model_type'],
                config=checkpoint.get('config'),
                device=device,
            )

            model.char_to_idx = checkpoint['char_to_idx']
            model.create_model()
            model.model.load_state_dict(checkpoint['model_state_dict'])
            model.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

        logger.info(f"Model loaded from {filepath}")
        return model
