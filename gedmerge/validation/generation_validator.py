"""
Generation gap validation for genealogical data.

Detects impossible generation gaps based on birth year differences
and family relationships.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Set, List, Tuple
from enum import Enum

from .genealogical_rules import (
    MIN_GENERATION_GAP,
    MAX_GENERATION_GAP,
    EXTREME_GENERATION_GAP,
    TYPICAL_GENERATION_YEARS,
    calculate_generation_gap_plausibility,
    get_expected_year_range_for_relationship,
)
from .date_validator import ParsedDate


class RelationshipType(Enum):
    """Types of family relationships."""
    PARENT = "parent"
    CHILD = "child"
    SPOUSE = "spouse"
    SIBLING = "sibling"
    GRANDPARENT = "grandparent"
    GRANDCHILD = "grandchild"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Relationship:
    """A family relationship between two people."""
    person1_id: str
    person2_id: str
    relationship_type: RelationshipType
    generation_distance: int  # 0=same gen, 1=parent/child, 2=grandparent/grandchild, etc.
    family_id: Optional[str] = None


@dataclass(slots=True)
class GenerationGapResult:
    """Result of generation gap validation."""
    is_plausible: bool
    plausibility_score: float  # 0.0-1.0
    birth_year_diff: Optional[int] = None
    generation_distance: Optional[int] = None
    expected_year_range: Optional[Tuple[int, int]] = None
    issues: List[str] = None

    def __post_init__(self):
        if self.issues is None:
            self.issues = []


class GenerationValidator:
    """Validates generation gaps based on family relationships and birth years."""

    def __init__(self):
        """Initialize the generation validator."""
        pass

    def calculate_generation_distance(
        self,
        person1_id: str,
        person2_id: str,
        relationships: List[Relationship]
    ) -> Optional[int]:
        """
        Calculate the generation distance between two people.

        Args:
            person1_id: ID of first person
            person2_id: ID of second person
            relationships: List of all known relationships

        Returns:
            Generation distance (0=same generation, 1=parent/child, etc.)
            or None if not related
        """
        # Build a graph of relationships
        relationship_map = {}
        for rel in relationships:
            if rel.person1_id not in relationship_map:
                relationship_map[rel.person1_id] = []
            if rel.person2_id not in relationship_map:
                relationship_map[rel.person2_id] = []

            relationship_map[rel.person1_id].append((rel.person2_id, rel.generation_distance))
            relationship_map[rel.person2_id].append((rel.person1_id, -rel.generation_distance))

        # BFS to find shortest path
        if person1_id not in relationship_map or person2_id not in relationship_map:
            return None

        visited = {person1_id: 0}
        queue = [(person1_id, 0)]

        while queue:
            current_id, current_distance = queue.pop(0)

            if current_id == person2_id:
                return current_distance

            if current_id in relationship_map:
                for related_id, gen_diff in relationship_map[current_id]:
                    new_distance = current_distance + gen_diff
                    if related_id not in visited or abs(new_distance) < abs(visited[related_id]):
                        visited[related_id] = new_distance
                        queue.append((related_id, new_distance))

        return None

    def extract_relationships_from_families(
        self,
        person1_id: str,
        person2_id: str,
        person1_parent_family_ids: List[str],
        person1_spouse_family_ids: List[str],
        person2_parent_family_ids: List[str],
        person2_spouse_family_ids: List[str],
        family_data: Dict[str, Dict]
    ) -> List[Relationship]:
        """
        Extract relationships between two people from family data.

        Args:
            person1_id: ID of first person
            person2_id: ID of second person
            person1_parent_family_ids: Families where person1 is a child
            person1_spouse_family_ids: Families where person1 is a spouse
            person2_parent_family_ids: Families where person2 is a child
            person2_spouse_family_ids: Families where person2 is a spouse
            family_data: Dict mapping family_id to family info
                        {family_id: {'father_id': ..., 'mother_id': ..., 'child_ids': [...]}}

        Returns:
            List of relationships found
        """
        relationships = []

        # Check if they share a parent family (siblings)
        shared_parent_families = set(person1_parent_family_ids) & set(person2_parent_family_ids)
        if shared_parent_families:
            relationships.append(Relationship(
                person1_id=person1_id,
                person2_id=person2_id,
                relationship_type=RelationshipType.SIBLING,
                generation_distance=0,
                family_id=list(shared_parent_families)[0]
            ))

        # Check if they share a spouse family (spouses)
        shared_spouse_families = set(person1_spouse_family_ids) & set(person2_spouse_family_ids)
        if shared_spouse_families:
            relationships.append(Relationship(
                person1_id=person1_id,
                person2_id=person2_id,
                relationship_type=RelationshipType.SPOUSE,
                generation_distance=0,
                family_id=list(shared_spouse_families)[0]
            ))

        # Check parent-child relationships
        # Person1 is parent of person2
        for family_id in person1_spouse_family_ids:
            if family_id in family_data:
                family = family_data[family_id]
                if person2_id in family.get('child_ids', []):
                    relationships.append(Relationship(
                        person1_id=person1_id,
                        person2_id=person2_id,
                        relationship_type=RelationshipType.CHILD,
                        generation_distance=1,
                        family_id=family_id
                    ))

        # Person2 is parent of person1
        for family_id in person2_spouse_family_ids:
            if family_id in family_data:
                family = family_data[family_id]
                if person1_id in family.get('child_ids', []):
                    relationships.append(Relationship(
                        person1_id=person1_id,
                        person2_id=person2_id,
                        relationship_type=RelationshipType.PARENT,
                        generation_distance=-1,
                        family_id=family_id
                    ))

        # Check grandparent relationships through parent families
        for family_id in person1_parent_family_ids:
            if family_id in family_data:
                family = family_data[family_id]
                father_id = family.get('father_id')
                mother_id = family.get('mother_id')

                # Check if person2 is a parent of person1's parents
                for parent_id in [father_id, mother_id]:
                    if parent_id and parent_id in family_data:
                        # This is getting complex - for now, we'll keep it simple
                        pass

        return relationships

    def validate_generation_gap(
        self,
        birth_date1: Optional[ParsedDate],
        birth_date2: Optional[ParsedDate],
        relationships: List[Relationship]
    ) -> GenerationGapResult:
        """
        Validate that birth year difference is plausible for the relationship.

        Args:
            birth_date1: Birth date of first person
            birth_date2: Birth date of second person
            relationships: List of relationships between the two people

        Returns:
            GenerationGapResult with validation details
        """
        issues = []

        if not birth_date1 or not birth_date2:
            return GenerationGapResult(
                is_plausible=True,
                plausibility_score=0.5,
                issues=["Insufficient date information"]
            )

        birth_year1 = birth_date1.get_best_year()
        birth_year2 = birth_date2.get_best_year()

        if not birth_year1 or not birth_year2:
            return GenerationGapResult(
                is_plausible=True,
                plausibility_score=0.5,
                issues=["Unable to extract birth years"]
            )

        birth_year_diff = abs(birth_year1 - birth_year2)

        # If no relationships known, can't validate
        if not relationships:
            # Just check if the age difference is reasonable for duplicates
            # (should be same person, so ages should match)
            if birth_year_diff == 0:
                return GenerationGapResult(
                    is_plausible=True,
                    plausibility_score=1.0,
                    birth_year_diff=birth_year_diff
                )
            elif birth_year_diff <= 2:
                issues.append(f"Birth years differ by {birth_year_diff} years (possible recording error)")
                return GenerationGapResult(
                    is_plausible=True,
                    plausibility_score=0.8,
                    birth_year_diff=birth_year_diff,
                    issues=issues
                )
            elif birth_year_diff <= 5:
                issues.append(f"Birth years differ by {birth_year_diff} years (unusual for same person)")
                return GenerationGapResult(
                    is_plausible=True,
                    plausibility_score=0.5,
                    birth_year_diff=birth_year_diff,
                    issues=issues
                )
            else:
                issues.append(f"Birth years differ by {birth_year_diff} years (likely different people)")
                return GenerationGapResult(
                    is_plausible=False,
                    plausibility_score=0.1,
                    birth_year_diff=birth_year_diff,
                    issues=issues
                )

        # Validate against each relationship
        max_plausibility = 0.0
        best_relationship = relationships[0]

        for rel in relationships:
            plausibility = calculate_generation_gap_plausibility(
                birth_year_diff,
                abs(rel.generation_distance)
            )

            if plausibility > max_plausibility:
                max_plausibility = plausibility
                best_relationship = rel

        # Use the best (most plausible) relationship
        generation_distance = abs(best_relationship.generation_distance)

        # Determine expected range
        older_year = min(birth_year1, birth_year2)
        relationship_str = best_relationship.relationship_type.value
        if best_relationship.generation_distance > 0:
            # person1 is older generation
            expected_range = get_expected_year_range_for_relationship(
                birth_year1, 'child'
            )
        elif best_relationship.generation_distance < 0:
            # person2 is older generation
            expected_range = get_expected_year_range_for_relationship(
                birth_year2, 'child'
            )
        else:
            # Same generation
            expected_range = get_expected_year_range_for_relationship(
                older_year, 'sibling'
            )

        # Build result
        is_plausible = max_plausibility >= 0.3  # Threshold for plausibility

        if not is_plausible:
            if generation_distance == 0:
                issues.append(
                    f"Same generation but {birth_year_diff} years apart (expected <30)"
                )
            elif generation_distance == 1:
                if birth_year_diff < MIN_GENERATION_GAP:
                    issues.append(
                        f"Parent-child relationship but only {birth_year_diff} years apart "
                        f"(minimum {MIN_GENERATION_GAP})"
                    )
                elif birth_year_diff > MAX_GENERATION_GAP:
                    issues.append(
                        f"Parent-child relationship but {birth_year_diff} years apart "
                        f"(maximum {MAX_GENERATION_GAP})"
                    )
            elif generation_distance == 2:
                expected_min = MIN_GENERATION_GAP * 2
                expected_max = MAX_GENERATION_GAP * 2
                if birth_year_diff < expected_min or birth_year_diff > expected_max:
                    issues.append(
                        f"Grandparent-grandchild relationship but {birth_year_diff} years apart "
                        f"(expected {expected_min}-{expected_max})"
                    )

        elif max_plausibility < 0.7:
            issues.append(
                f"{relationship_str.capitalize()} relationship with {birth_year_diff} year gap is unusual"
            )

        return GenerationGapResult(
            is_plausible=is_plausible,
            plausibility_score=max_plausibility,
            birth_year_diff=birth_year_diff,
            generation_distance=generation_distance,
            expected_year_range=expected_range,
            issues=issues
        )

    def validate_generation_gap_simple(
        self,
        birth_year1: int,
        birth_year2: int,
        assume_same_generation: bool = True
    ) -> GenerationGapResult:
        """
        Simple validation for when relationship info is not available.
        Assumes people are likely the same person (duplicates).

        Args:
            birth_year1: Birth year of first person
            birth_year2: Birth year of second person
            assume_same_generation: If True, assume they should be same generation

        Returns:
            GenerationGapResult
        """
        birth_year_diff = abs(birth_year1 - birth_year2)
        issues = []

        if assume_same_generation:
            # For potential duplicates, birth years should be very close
            if birth_year_diff == 0:
                return GenerationGapResult(
                    is_plausible=True,
                    plausibility_score=1.0,
                    birth_year_diff=birth_year_diff
                )
            elif birth_year_diff <= 2:
                issues.append(
                    f"Birth years differ by {birth_year_diff} (possible transcription error)"
                )
                return GenerationGapResult(
                    is_plausible=True,
                    plausibility_score=0.85,
                    birth_year_diff=birth_year_diff,
                    issues=issues
                )
            elif birth_year_diff <= 5:
                issues.append(
                    f"Birth years differ by {birth_year_diff} (unusual for same person)"
                )
                return GenerationGapResult(
                    is_plausible=True,
                    plausibility_score=0.5,
                    birth_year_diff=birth_year_diff,
                    issues=issues
                )
            elif birth_year_diff <= 10:
                issues.append(
                    f"Birth years differ by {birth_year_diff} (questionable match)"
                )
                return GenerationGapResult(
                    is_plausible=False,
                    plausibility_score=0.2,
                    birth_year_diff=birth_year_diff,
                    issues=issues
                )
            else:
                issues.append(
                    f"Birth years differ by {birth_year_diff} (likely different people)"
                )
                return GenerationGapResult(
                    is_plausible=False,
                    plausibility_score=0.0,
                    birth_year_diff=birth_year_diff,
                    issues=issues
                )
        else:
            # Unknown relationship - just flag extremes
            if birth_year_diff > EXTREME_GENERATION_GAP:
                issues.append(
                    f"Birth years differ by {birth_year_diff} (exceeds maximum plausible gap)"
                )
                return GenerationGapResult(
                    is_plausible=False,
                    plausibility_score=0.0,
                    birth_year_diff=birth_year_diff,
                    issues=issues
                )
            else:
                return GenerationGapResult(
                    is_plausible=True,
                    plausibility_score=0.7,
                    birth_year_diff=birth_year_diff
                )

    def get_relationship_overlap_score(
        self,
        person1_parent_families: List[str],
        person1_spouse_families: List[str],
        person2_parent_families: List[str],
        person2_spouse_families: List[str]
    ) -> float:
        """
        Calculate a score based on family relationship overlap.

        Returns:
            Score 0.0-1.0 indicating strength of relationship overlap
        """
        parent_overlap = len(set(person1_parent_families) & set(person2_parent_families))
        spouse_overlap = len(set(person1_spouse_families) & set(person2_spouse_families))

        if parent_overlap > 0:
            # Share same parents - likely siblings or same person
            return 1.0
        elif spouse_overlap > 0:
            # Share same spouse family - likely spouses or same person
            return 1.0
        else:
            # No direct family overlap
            # Check for any family connections
            all_families_1 = set(person1_parent_families + person1_spouse_families)
            all_families_2 = set(person2_parent_families + person2_spouse_families)

            if all_families_1 & all_families_2:
                # Some family connection exists
                return 0.5
            else:
                # No family connection
                return 0.0
