"""Graph Neural Network for relationship inference in family trees."""

from typing import List, Dict, Optional, Tuple, Any
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, global_mean_pool
from torch_geometric.data import Data, Batch
import networkx as nx
import numpy as np
from pathlib import Path
import logging

from ..utils.config import MLConfig
from ...core.person import Person

logger = logging.getLogger(__name__)


class FamilyTreeGNN(nn.Module):
    """Graph Attention Network for family tree analysis."""

    def __init__(
        self,
        node_features: int = 64,
        hidden_channels: int = 64,
        num_layers: int = 3,
        heads: int = 4,
        dropout: float = 0.3,
        output_dim: int = 32,
    ):
        """
        Initialize GNN.

        Args:
            node_features: Number of input node features
            hidden_channels: Hidden layer dimension
            num_layers: Number of GNN layers
            heads: Number of attention heads
            dropout: Dropout rate
            output_dim: Output embedding dimension
        """
        super().__init__()

        self.num_layers = num_layers
        self.dropout = dropout

        # Input projection
        self.input_proj = nn.Linear(node_features, hidden_channels)

        # GAT layers
        self.gat_layers = nn.ModuleList()
        for i in range(num_layers):
            in_channels = hidden_channels if i == 0 else hidden_channels * heads
            out_channels = hidden_channels

            self.gat_layers.append(
                GATConv(
                    in_channels,
                    out_channels,
                    heads=heads,
                    dropout=dropout,
                    concat=True if i < num_layers - 1 else False,
                )
            )

        # Output projection
        final_dim = hidden_channels * heads if num_layers > 1 else hidden_channels
        self.output_proj = nn.Sequential(
            nn.Linear(final_dim, hidden_channels),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_channels, output_dim),
        )

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x: Node features (num_nodes, node_features)
            edge_index: Edge indices (2, num_edges)

        Returns:
            Node embeddings (num_nodes, output_dim)
        """
        # Project input
        x = self.input_proj(x)
        x = F.relu(x)

        # Apply GAT layers
        for i, gat in enumerate(self.gat_layers):
            x = gat(x, edge_index)

            if i < self.num_layers - 1:
                x = F.relu(x)
                x = F.dropout(x, p=self.dropout, training=self.training)

        # Project output
        x = self.output_proj(x)

        return x


class RelationshipInferenceModel:
    """
    Model for inferring relationships using Graph Neural Networks.

    Learns from family tree structure to:
    - Identify likely relationships between persons
    - Detect missing relationships
    - Improve duplicate detection by considering graph structure
    """

    def __init__(
        self,
        config: Optional[MLConfig] = None,
        device: Optional[str] = None,
    ):
        """
        Initialize model.

        Args:
            config: ML configuration
            device: Device to use
        """
        self.config = config or MLConfig()

        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.model = None
        self.optimizer = None

        logger.info(f"Using device: {self.device}")

    def create_model(self):
        """Create GNN model."""
        gnn_config = self.config.gnn_config

        self.model = FamilyTreeGNN(
            node_features=64,  # Person feature dimension
            hidden_channels=gnn_config.get('hidden_channels', 64),
            num_layers=gnn_config.get('num_layers', 3),
            heads=gnn_config.get('heads', 4),
            dropout=gnn_config.get('dropout', 0.3),
            output_dim=32,
        )

        self.model = self.model.to(self.device)

        self.optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=self.config.learning_rate,
        )

        logger.info("Created GNN model")

    def build_family_graph(
        self,
        persons: List[Person],
        include_features: bool = True,
    ) -> Data:
        """
        Build PyTorch Geometric graph from persons.

        Args:
            persons: List of Person objects
            include_features: Whether to include node features

        Returns:
            PyTorch Geometric Data object
        """
        # Create networkx graph first
        G = nx.DiGraph()

        # Create person ID to index mapping
        person_to_idx = {p.person_id: idx for idx, p in enumerate(persons)}

        # Add nodes
        for idx, person in enumerate(persons):
            G.add_node(idx, person=person)

        # Add edges (relationships)
        edges = []
        edge_types = []

        for idx, person in enumerate(persons):
            # Parent-child relationships
            for family in person.families_as_child:
                if hasattr(family, 'father') and family.father:
                    if family.father.person_id in person_to_idx:
                        parent_idx = person_to_idx[family.father.person_id]
                        edges.append([parent_idx, idx])
                        edge_types.append(0)  # 0 = parent-child

                if hasattr(family, 'mother') and family.mother:
                    if family.mother.person_id in person_to_idx:
                        parent_idx = person_to_idx[family.mother.person_id]
                        edges.append([parent_idx, idx])
                        edge_types.append(0)

            # Spouse relationships
            for family in person.families_as_spouse:
                if hasattr(family, 'spouse') and family.spouse:
                    if family.spouse.person_id in person_to_idx:
                        spouse_idx = person_to_idx[family.spouse.person_id]
                        edges.append([idx, spouse_idx])
                        edges.append([spouse_idx, idx])  # Bidirectional
                        edge_types.append(1)  # 1 = spouse
                        edge_types.append(1)

        # Convert to PyTorch tensors
        if edges:
            edge_index = torch.LongTensor(edges).t().contiguous()
            edge_attr = torch.LongTensor(edge_types)
        else:
            edge_index = torch.LongTensor([[], []])
            edge_attr = torch.LongTensor([])

        # Node features
        if include_features:
            node_features = []
            for person in persons:
                features = self._extract_person_features(person)
                node_features.append(features)
            x = torch.FloatTensor(node_features)
        else:
            x = torch.ones((len(persons), 64))

        # Create PyG Data object
        data = Data(
            x=x,
            edge_index=edge_index,
            edge_attr=edge_attr,
        )

        return data

    def _extract_person_features(self, person: Person) -> np.ndarray:
        """Extract features for a person node."""
        features = np.zeros(64, dtype=np.float32)

        # Name features (0-9)
        if person.names:
            name = person.names[0]
            features[0] = len(name.given) if name.given else 0
            features[1] = len(name.surname) if name.surname else 0
            features[2] = float(bool(name.surname))
            features[3] = float(len(person.names))

        # Date features (10-19)
        birth_event = person.get_birth_event()
        death_event = person.get_death_event()

        if birth_event and birth_event.date:
            year = self._extract_year(birth_event.date)
            if year:
                features[10] = (year - 1700) / 300  # Normalized year
                features[11] = 1.0

        if death_event and death_event.date:
            year = self._extract_year(death_event.date)
            if year:
                features[12] = (year - 1700) / 300
                features[13] = 1.0

        # Sex (20-22)
        if person.sex:
            if person.sex.upper() == 'M':
                features[20] = 1.0
            elif person.sex.upper() == 'F':
                features[21] = 1.0
            else:
                features[22] = 1.0

        # Relationship counts (30-39)
        features[30] = len(person.families_as_child)
        features[31] = len(person.families_as_spouse)

        # Event counts (40-49)
        features[40] = len(person.events)
        features[41] = float(bool(person.get_birth_place()))
        features[42] = float(bool(person.get_death_place()))

        # Data quality indicators (50-59)
        features[50] = 1.0 if person.names else 0.0
        features[51] = 1.0 if birth_event else 0.0
        features[52] = 1.0 if death_event else 0.0

        return features

    def _extract_year(self, date_str: str) -> Optional[int]:
        """Extract year from date string."""
        import re
        if not date_str:
            return None
        year_match = re.search(r'\b(1\d{3}|20\d{2})\b', date_str)
        if year_match:
            return int(year_match.group(1))
        return None

    def train(
        self,
        graphs: List[Data],
        num_epochs: int = 100,
    ) -> Dict[str, Any]:
        """
        Train the GNN.

        Args:
            graphs: List of family tree graphs
            num_epochs: Number of training epochs

        Returns:
            Training history
        """
        if self.model is None:
            self.create_model()

        logger.info(f"Training GNN for {num_epochs} epochs...")

        history = {'loss': []}

        for epoch in range(num_epochs):
            self.model.train()
            total_loss = 0

            for graph in graphs:
                graph = graph.to(self.device)

                # Forward pass
                embeddings = self.model(graph.x, graph.edge_index)

                # Loss: Encourage similar embeddings for related persons
                # This is a simplified contrastive learning approach
                loss = self._compute_relationship_loss(embeddings, graph.edge_index)

                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                self.optimizer.step()

                total_loss += loss.item()

            avg_loss = total_loss / len(graphs)
            history['loss'].append(avg_loss)

            if (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{num_epochs} - Loss: {avg_loss:.4f}")

        return history

    def _compute_relationship_loss(
        self,
        embeddings: torch.Tensor,
        edge_index: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute loss based on relationships.

        Encourage related persons to have similar embeddings.
        """
        if edge_index.size(1) == 0:
            # No edges, return zero loss
            return torch.tensor(0.0, device=self.device)

        # Get pairs of related persons
        src_nodes = edge_index[0]
        dst_nodes = edge_index[1]

        src_emb = embeddings[src_nodes]
        dst_emb = embeddings[dst_nodes]

        # Compute similarity (cosine)
        similarity = F.cosine_similarity(src_emb, dst_emb)

        # Loss: maximize similarity for connected nodes
        loss = 1.0 - similarity.mean()

        return loss

    def get_person_embedding(
        self,
        person: Person,
        family_graph: Data,
        person_idx: int,
    ) -> np.ndarray:
        """
        Get embedding for a person in context of family tree.

        Args:
            person: Person object
            family_graph: Family tree graph
            person_idx: Index of person in graph

        Returns:
            Embedding vector
        """
        if self.model is None:
            raise ValueError("Model not trained.")

        self.model.eval()

        with torch.no_grad():
            family_graph = family_graph.to(self.device)
            embeddings = self.model(family_graph.x, family_graph.edge_index)
            person_emb = embeddings[person_idx].cpu().numpy()

        return person_emb

    def compute_relationship_score(
        self,
        person1: Person,
        person2: Person,
        persons: List[Person],
    ) -> float:
        """
        Compute relationship likelihood score for two persons.

        Args:
            person1: First person
            person2: Second person
            persons: All persons in family tree

        Returns:
            Relationship score (0-1)
        """
        if self.model is None:
            raise ValueError("Model not trained.")

        # Build graph
        graph = self.build_family_graph(persons)

        # Find person indices
        person_to_idx = {p.person_id: idx for idx, p in enumerate(persons)}

        if person1.person_id not in person_to_idx or person2.person_id not in person_to_idx:
            return 0.0

        idx1 = person_to_idx[person1.person_id]
        idx2 = person_to_idx[person2.person_id]

        # Get embeddings
        self.model.eval()
        with torch.no_grad():
            graph = graph.to(self.device)
            embeddings = self.model(graph.x, graph.edge_index)

            emb1 = embeddings[idx1]
            emb2 = embeddings[idx2]

            # Compute similarity
            similarity = F.cosine_similarity(
                emb1.unsqueeze(0),
                emb2.unsqueeze(0)
            ).item()

        # Normalize to 0-1
        score = (similarity + 1) / 2

        return score

    def save(self, filepath: Path):
        """Save model."""
        if self.model is None:
            raise ValueError("No model to save.")

        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)

        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'config': self.config,
        }, filepath)

        logger.info(f"Model saved to {filepath}")

    @classmethod
    def load(cls, filepath: Path, device: Optional[str] = None) -> "RelationshipInferenceModel":
        """Load model."""
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"Model file not found: {filepath}")

        checkpoint = torch.load(filepath, map_location='cpu')

        model_obj = cls(config=checkpoint.get('config'), device=device)
        model_obj.create_model()
        model_obj.model.load_state_dict(checkpoint['model_state_dict'])
        model_obj.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

        logger.info(f"Model loaded from {filepath}")
        return model_obj
