"""Generate training data from genealogy databases."""

from typing import List, Tuple, Dict, Any, Optional
import numpy as np
import pandas as pd
from pathlib import Path
import logging
from dataclasses import dataclass
import random
from collections import defaultdict

from ...core.person import Person
from ...rootsmagic.adapter import RootsMagicDatabase
from ...matching import PersonMatcher
from ..utils.feature_extractor import FeatureExtractor, PairwiseFeatures, PersonFeatures

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LabeledPair:
    """A labeled person pair for training."""

    person1: Person
    person2: Person
    is_duplicate: bool
    confidence: float  # How confident we are in the label
    features: PairwiseFeatures
    source: str  # How this label was generated


class TrainingDataGenerator:
    """Generate labeled training data from genealogy databases."""

    def __init__(
        self,
        database: RootsMagicDatabase,
        feature_extractor: Optional[FeatureExtractor] = None,
    ):
        """
        Initialize data generator.

        Args:
            database: RootsMagic database
            feature_extractor: Feature extractor (creates new if None)
        """
        self.db = database
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.matcher = PersonMatcher(database)

    def generate_duplicate_pairs(
        self,
        high_confidence_threshold: float = 90.0,
        num_pairs: Optional[int] = None,
        balance_classes: bool = True,
    ) -> List[LabeledPair]:
        """
        Generate labeled pairs of duplicates and non-duplicates.

        Args:
            high_confidence_threshold: Threshold for auto-labeling as duplicate
            num_pairs: Maximum number of pairs to generate
            balance_classes: Whether to balance positive/negative examples

        Returns:
            List of labeled pairs
        """
        logger.info("Generating duplicate detection training data...")

        labeled_pairs = []

        # 1. Find high-confidence duplicates (positive examples)
        logger.info("Finding high-confidence duplicate pairs...")
        matches = self.matcher.find_duplicates(
            min_confidence=high_confidence_threshold,
            limit=num_pairs // 2 if num_pairs else None
        )

        for match in matches:
            features = self.feature_extractor.extract_pairwise_features(
                match.person1,
                match.person2
            )

            labeled_pairs.append(LabeledPair(
                person1=match.person1,
                person2=match.person2,
                is_duplicate=True,
                confidence=match.confidence / 100.0,
                features=features,
                source="high_confidence_match"
            ))

        num_positives = len(labeled_pairs)
        logger.info(f"Found {num_positives} high-confidence duplicate pairs")

        # 2. Generate negative examples (non-duplicates)
        logger.info("Generating negative examples...")

        # Strategy: Sample random pairs with low similarity
        all_persons = list(self.db.get_all_persons())
        num_negatives_needed = num_positives if balance_classes else num_positives // 2

        negative_pairs = self._generate_negative_pairs(
            all_persons,
            num_negatives_needed,
            max_similarity_threshold=0.4  # Only pairs with < 40% similarity
        )

        labeled_pairs.extend(negative_pairs)
        logger.info(f"Generated {len(negative_pairs)} negative examples")

        # 3. Generate hard negatives (similar but not duplicates)
        logger.info("Generating hard negative examples...")

        hard_negatives = self._generate_hard_negatives(
            all_persons,
            num_samples=num_positives // 4,  # 25% of positives
            similarity_range=(0.4, 0.6)  # Medium similarity but not duplicates
        )

        labeled_pairs.extend(hard_negatives)
        logger.info(f"Generated {len(hard_negatives)} hard negative examples")

        # Shuffle
        random.shuffle(labeled_pairs)

        logger.info(f"Total training pairs generated: {len(labeled_pairs)}")
        logger.info(f"  Positives: {sum(1 for p in labeled_pairs if p.is_duplicate)}")
        logger.info(f"  Negatives: {sum(1 for p in labeled_pairs if not p.is_duplicate)}")

        return labeled_pairs

    def _generate_negative_pairs(
        self,
        persons: List[Person],
        num_samples: int,
        max_similarity_threshold: float = 0.4,
    ) -> List[LabeledPair]:
        """Generate negative pairs (non-duplicates)."""
        negative_pairs = []
        max_attempts = num_samples * 10  # Prevent infinite loop
        attempts = 0

        while len(negative_pairs) < num_samples and attempts < max_attempts:
            attempts += 1

            # Sample two random persons
            p1, p2 = random.sample(persons, 2)

            # Skip if same sex (more likely to be duplicates)
            if p1.sex and p2.sex and p1.sex == p2.sex:
                continue

            # Extract features
            features = self.feature_extractor.extract_pairwise_features(p1, p2)

            # Only keep if similarity is low
            if features.overall_similarity < max_similarity_threshold:
                negative_pairs.append(LabeledPair(
                    person1=p1,
                    person2=p2,
                    is_duplicate=False,
                    confidence=1.0 - features.overall_similarity,  # High confidence it's NOT a dup
                    features=features,
                    source="random_negative"
                ))

        return negative_pairs

    def _generate_hard_negatives(
        self,
        persons: List[Person],
        num_samples: int,
        similarity_range: Tuple[float, float] = (0.4, 0.6),
    ) -> List[LabeledPair]:
        """Generate hard negative pairs (similar but not duplicates)."""
        hard_negatives = []
        max_attempts = num_samples * 20
        attempts = 0

        # Index persons by surname for finding similar names
        surname_index = defaultdict(list)
        for person in persons:
            if person.names:
                surname = person.names[0].surname.lower() if person.names[0].surname else ""
                if surname:
                    surname_index[surname].append(person)

        while len(hard_negatives) < num_samples and attempts < max_attempts:
            attempts += 1

            # Pick a random surname group
            if not surname_index:
                break

            surname = random.choice(list(surname_index.keys()))
            persons_with_surname = surname_index[surname]

            if len(persons_with_surname) < 2:
                continue

            # Sample two persons with same surname
            p1, p2 = random.sample(persons_with_surname, 2)

            # Extract features
            features = self.feature_extractor.extract_pairwise_features(p1, p2)

            # Check if in desired similarity range
            min_sim, max_sim = similarity_range
            if min_sim <= features.overall_similarity <= max_sim:
                # Additional check: they should have conflicting info or different dates
                if features.sex_conflict or features.date_conflict or features.different_locations:
                    hard_negatives.append(LabeledPair(
                        person1=p1,
                        person2=p2,
                        is_duplicate=False,
                        confidence=0.7,  # Medium confidence (hard example)
                        features=features,
                        source="hard_negative"
                    ))

        return hard_negatives

    def generate_name_matching_data(
        self,
        num_samples: int = 10000,
    ) -> List[Tuple[str, str, float]]:
        """
        Generate name pairs for name matching model.

        Args:
            num_samples: Number of samples to generate

        Returns:
            List of (name1, name2, similarity_score) tuples
        """
        logger.info(f"Generating {num_samples} name matching samples...")

        samples = []
        all_persons = list(self.db.get_all_persons())

        # 1. Exact matches (from same person with multiple name variations)
        for person in all_persons:
            if len(person.names) > 1:
                for i in range(len(person.names)):
                    for j in range(i + 1, len(person.names)):
                        name1 = str(person.names[i])
                        name2 = str(person.names[j])
                        samples.append((name1, name2, 1.0))  # Same person = perfect match

        # 2. High similarity matches (from high-confidence duplicates)
        matches = self.matcher.find_duplicates(min_confidence=85.0)
        for match in matches[:num_samples // 3]:
            if match.person1.names and match.person2.names:
                name1 = str(match.person1.names[0])
                name2 = str(match.person2.names[0])
                similarity = match.confidence / 100.0
                samples.append((name1, name2, similarity))

        # 3. Low similarity matches (random pairs)
        for _ in range(num_samples // 3):
            p1, p2 = random.sample(all_persons, 2)
            if p1.names and p2.names:
                name1 = str(p1.names[0])
                name2 = str(p2.names[0])
                # Compute actual similarity
                features = self.feature_extractor.extract_pairwise_features(p1, p2)
                samples.append((name1, name2, features.name_similarity))

        # Trim to requested size and shuffle
        samples = samples[:num_samples]
        random.shuffle(samples)

        logger.info(f"Generated {len(samples)} name matching samples")
        return samples

    def generate_language_detection_data(
        self,
    ) -> List[Tuple[str, str]]:
        """
        Generate name-language pairs for language detection.

        Returns:
            List of (name, language) tuples
        """
        logger.info("Generating language detection training data...")

        samples = []
        all_persons = list(self.db.get_all_persons())

        for person in all_persons:
            for name in person.names:
                if name.language:
                    full_name = str(name)
                    samples.append((full_name, name.language))

        logger.info(f"Generated {len(samples)} language detection samples")
        logger.info(f"Languages: {set(lang for _, lang in samples)}")

        return samples

    def generate_quality_classification_data(
        self,
    ) -> List[Tuple[Person, List[str]]]:
        """
        Generate data for quality classification.

        Returns:
            List of (person, quality_issues) tuples
        """
        logger.info("Generating data quality classification training data...")

        samples = []
        all_persons = list(self.db.get_all_persons())

        for person in all_persons:
            issues = self._detect_quality_issues(person)
            if issues:  # Only include persons with at least one issue
                samples.append((person, issues))

        logger.info(f"Generated {len(samples)} quality classification samples")
        logger.info(f"Issue distribution:")

        issue_counts = defaultdict(int)
        for _, issues in samples:
            for issue in issues:
                issue_counts[issue] += 1

        for issue, count in sorted(issue_counts.items(), key=lambda x: -x[1]):
            logger.info(f"  {issue}: {count}")

        return samples

    def _detect_quality_issues(self, person: Person) -> List[str]:
        """Detect data quality issues in a person record."""
        issues = []

        if not person.names:
            return ["missing_data"]

        primary_name = person.names[0]
        given = primary_name.given or ""
        surname = primary_name.surname or ""
        full_name = str(primary_name)

        # Reversed names (surname in given field or vice versa)
        if given and surname:
            # Check if given name looks like a surname (all caps, etc.)
            if given.isupper() and not surname.isupper():
                issues.append("reversed_names")

        # Embedded variants
        if "/" in full_name or "(" in full_name:
            issues.append("embedded_variants")

        # Titles in wrong field
        titles = ["Mr", "Mrs", "Dr", "Sir", "Lady", "Lord", "Rev", "Prof"]
        for title in titles:
            if title.lower() in given.lower() or title.lower() in surname.lower():
                issues.append("titles_in_wrong_field")
                break

        # Missing data
        if not given or not surname:
            issues.append("missing_data")

        # Placeholder names
        placeholders = ["unknown", "unnamed", "n.n.", "?", "___"]
        for placeholder in placeholders:
            if placeholder in given.lower() or placeholder in surname.lower():
                issues.append("placeholder_name")
                break

        # Invalid dates
        birth_event = person.get_birth_event()
        death_event = person.get_death_event()

        if birth_event and death_event:
            # Try to extract years
            birth_year = self._extract_year(birth_event.date) if birth_event.date else None
            death_year = self._extract_year(death_event.date) if death_event.date else None

            if birth_year and death_year:
                if death_year < birth_year:
                    issues.append("invalid_dates")
                elif death_year - birth_year > 120:
                    issues.append("invalid_dates")

        # Inconsistent formatting
        # Check for mixed case issues, extra spaces, etc.
        if "  " in full_name:  # Double spaces
            issues.append("inconsistent_formatting")

        if full_name != full_name.strip():  # Leading/trailing spaces
            issues.append("inconsistent_formatting")

        return list(set(issues))  # Remove duplicates

    def _extract_year(self, date_str: str) -> Optional[int]:
        """Extract year from date string."""
        import re
        if not date_str:
            return None
        year_match = re.search(r'\b(1\d{3}|20\d{2})\b', date_str)
        if year_match:
            return int(year_match.group(1))
        return None

    def save_dataset(
        self,
        data: List[LabeledPair],
        output_path: Path,
        format: str = "csv",
    ):
        """
        Save dataset to file.

        Args:
            data: List of labeled pairs
            output_path: Path to save to
            format: Format ('csv', 'parquet', 'pickle')
        """
        # Convert to DataFrame
        records = []
        for pair in data:
            feature_dict = {
                'name_similarity': pair.features.name_similarity,
                'phonetic_similarity': pair.features.phonetic_similarity,
                'surname_similarity': pair.features.surname_similarity,
                'given_name_similarity': pair.features.given_name_similarity,
                'exact_name_match': pair.features.exact_name_match,
                'levenshtein_distance': pair.features.levenshtein_distance,
                'jaro_winkler_similarity': pair.features.jaro_winkler_similarity,
                'token_set_ratio': pair.features.token_set_ratio,
                'birth_date_match': pair.features.birth_date_match,
                'death_date_match': pair.features.death_date_match,
                'age_difference': pair.features.age_difference,
                'date_conflict': pair.features.date_conflict,
                'birth_place_similarity': pair.features.birth_place_similarity,
                'death_place_similarity': pair.features.death_place_similarity,
                'place_overlap': pair.features.place_overlap,
                'shared_parents': pair.features.shared_parents,
                'shared_spouses': pair.features.shared_spouses,
                'shared_children': pair.features.shared_children,
                'relationship_overlap_score': pair.features.relationship_overlap_score,
                'sex_conflict': pair.features.sex_conflict,
                'significant_age_gap': pair.features.significant_age_gap,
                'different_locations': pair.features.different_locations,
                'overall_similarity': pair.features.overall_similarity,
                'is_duplicate': pair.is_duplicate,
                'confidence': pair.confidence,
                'source': pair.source,
            }
            records.append(feature_dict)

        df = pd.DataFrame(records)

        # Save
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "csv":
            df.to_csv(output_path, index=False)
        elif format == "parquet":
            df.to_parquet(output_path, index=False)
        elif format == "pickle":
            df.to_pickle(output_path)
        else:
            raise ValueError(f"Unknown format: {format}")

        logger.info(f"Saved dataset to {output_path} ({len(df)} rows)")
