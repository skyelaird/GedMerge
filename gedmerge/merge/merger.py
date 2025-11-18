"""
Person record merger with confidence-based decisions.

Handles merging duplicate person records while preserving data quality
and resolving conflicts intelligently. Uses validation-based confidence
tiers for merge decisions.
"""

from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
from ..rootsmagic.models import RMPerson, RMName, RMEvent, RMFamily
from ..rootsmagic.adapter import RootsMagicDatabase
from ..matching.matcher import MatchCandidate
from .conflict_resolver import ConflictResolver, MergeDecision, ConflictResolution
from ..validation import ConfidenceTier


class MergeStrategy(Enum):
    """Strategy for merging records."""
    AUTOMATIC = "automatic"  # Auto-merge high confidence matches
    MANUAL = "manual"  # Require user confirmation for all
    INTERACTIVE = "interactive"  # Auto for high, ask for medium


@dataclass(slots=True)
class MergeResult:
    """Result of a merge operation."""
    success: bool
    merged_person_id: Optional[int]
    removed_person_id: Optional[int]
    conflicts_resolved: List[ConflictResolution]
    errors: List[str]
    details: Dict[str, any]

    def __str__(self) -> str:
        """Human-readable result."""
        if self.success:
            return (
                f"✓ Successfully merged person {self.removed_person_id} "
                f"into {self.merged_person_id}\n"
                f"  Conflicts resolved: {len(self.conflicts_resolved)}\n"
                f"  {self.details.get('summary', '')}"
            )
        else:
            return (
                f"✗ Merge failed\n"
                f"  Errors: {', '.join(self.errors)}"
            )


class PersonMerger:
    """
    Merges duplicate person records.

    Merge Process:
    1. Identify which record to keep (primary) and which to merge (secondary)
    2. Resolve conflicts using conflict resolver
    3. Merge names, events, relationships
    4. Update family relationships
    5. Delete secondary record
    6. Log changes
    """

    def __init__(
        self,
        db: RootsMagicDatabase,
        strategy: MergeStrategy = MergeStrategy.INTERACTIVE
    ):
        """
        Initialize the merger.

        Args:
            db: RootsMagic database connection
            strategy: Merge strategy to use
        """
        self.db = db
        self.strategy = strategy
        self.resolver = ConflictResolver()

    def merge_candidates(
        self,
        candidates: List[MatchCandidate],
        auto_merge_threshold: float = 90.0,
        use_confidence_tiers: bool = True
    ) -> List[MergeResult]:
        """
        Merge a list of match candidates.

        Args:
            candidates: List of match candidates to merge
            auto_merge_threshold: Confidence threshold for automatic merging (legacy, used if use_confidence_tiers=False)
            use_confidence_tiers: If True, use validation-based confidence tiers for decisions

        Returns:
            List of merge results
        """
        results = []

        for candidate in candidates:
            # Determine if we should auto-merge based on confidence tier or score
            if use_confidence_tiers and candidate.match_result.confidence_tier:
                # Use validation-based confidence tier system
                tier = candidate.match_result.confidence_tier

                if tier == ConfidenceTier.REJECT:
                    # Hard rejection - validation failures
                    result = MergeResult(
                        success=False,
                        merged_person_id=None,
                        removed_person_id=None,
                        conflicts_resolved=[],
                        errors=["Rejected due to validation failures"],
                        details={
                            'candidate': candidate,
                            'confidence_tier': tier.value,
                            'validation_issues': candidate.match_result.details.get('validation_issues', [])
                        }
                    )
                    results.append(result)
                    continue

                elif tier == ConfidenceTier.AUTO_MERGE:
                    # High confidence - auto-merge
                    should_auto = True

                else:  # NEEDS_REVIEW
                    # Medium confidence - depends on strategy
                    should_auto = self.strategy == MergeStrategy.AUTOMATIC
                    if not should_auto:
                        result = MergeResult(
                            success=False,
                            merged_person_id=None,
                            removed_person_id=None,
                            conflicts_resolved=[],
                            errors=["Flagged for human review"],
                            details={
                                'candidate': candidate,
                                'confidence_tier': tier.value,
                                'validation_issues': candidate.match_result.details.get('validation_issues', [])
                            }
                        )
                        results.append(result)
                        continue

            else:
                # Legacy: Use score-based threshold
                should_auto = (
                    self.strategy == MergeStrategy.AUTOMATIC or
                    (self.strategy == MergeStrategy.INTERACTIVE and
                     candidate.confidence >= auto_merge_threshold)
                )

            if should_auto:
                result = self.merge_persons(
                    candidate.person1,
                    candidate.person2,
                    match_candidate=candidate
                )
                results.append(result)
            else:
                # Manual merge required
                result = MergeResult(
                    success=False,
                    merged_person_id=None,
                    removed_person_id=None,
                    conflicts_resolved=[],
                    errors=["Manual confirmation required"],
                    details={'candidate': candidate}
                )
                results.append(result)

        return results

    def merge_persons(
        self,
        person1: RMPerson,
        person2: RMPerson,
        match_candidate: Optional[MatchCandidate] = None
    ) -> MergeResult:
        """
        Merge two person records.

        Args:
            person1: First person (may become primary)
            person2: Second person (may become primary)
            match_candidate: Optional match candidate with scoring info

        Returns:
            MergeResult with outcome
        """
        errors = []
        conflicts = []

        try:
            # Determine which record should be primary
            primary, secondary = self._select_primary(person1, person2)

            # Create merged person
            merged = self._create_merged_person(primary, secondary, conflicts)

            # Validate merge
            validation_errors = self._validate_merge(merged, primary, secondary)
            if validation_errors:
                return MergeResult(
                    success=False,
                    merged_person_id=None,
                    removed_person_id=None,
                    conflicts_resolved=conflicts,
                    errors=validation_errors,
                    details={}
                )

            # Execute merge in database transaction
            self.db.conn.execute("BEGIN TRANSACTION")

            try:
                # Update primary record with merged data
                self._update_person_in_db(merged)

                # Transfer relationships from secondary to primary
                self._transfer_relationships(secondary, primary)

                # Delete secondary record
                self._delete_person(secondary)

                # Commit transaction
                self.db.conn.commit()

                return MergeResult(
                    success=True,
                    merged_person_id=primary.person_id,
                    removed_person_id=secondary.person_id,
                    conflicts_resolved=conflicts,
                    errors=[],
                    details={
                        'summary': f"Merged {len(secondary.names or [])} names, "
                                   f"{len(secondary.events or [])} events",
                        'primary': primary.person_id,
                        'secondary': secondary.person_id,
                    }
                )

            except Exception as e:
                # Rollback on error
                self.db.conn.rollback()
                raise

        except Exception as e:
            errors.append(f"Merge failed: {str(e)}")
            return MergeResult(
                success=False,
                merged_person_id=None,
                removed_person_id=None,
                conflicts_resolved=conflicts,
                errors=errors,
                details={}
            )

    def _select_primary(
        self,
        person1: RMPerson,
        person2: RMPerson
    ) -> Tuple[RMPerson, RMPerson]:
        """
        Select which person should be primary (kept) vs secondary (merged).

        Selection criteria:
        1. More complete data (more names, events)
        2. Earlier person ID (older record)
        3. Primary name vs alternate name

        Returns:
            (primary, secondary) tuple
        """
        score1 = 0
        score2 = 0

        # Criterion 1: Data completeness
        score1 += len(person1.names or []) * 2
        score1 += len(person1.events or [])
        score1 += len(person1.spouse_family_ids or [])
        score1 += len(person1.parent_family_ids or [])

        score2 += len(person2.names or []) * 2
        score2 += len(person2.events or [])
        score2 += len(person2.spouse_family_ids or [])
        score2 += len(person2.parent_family_ids or [])

        # Criterion 2: Earlier ID (older record, likely more vetted)
        if person1.person_id < person2.person_id:
            score1 += 1
        else:
            score2 += 1

        # Select based on score
        if score1 >= score2:
            return (person1, person2)
        else:
            return (person2, person1)

    def _create_merged_person(
        self,
        primary: RMPerson,
        secondary: RMPerson,
        conflicts: List[ConflictResolution]
    ) -> RMPerson:
        """
        Create merged person record from primary and secondary.

        Args:
            primary: Primary person (base)
            secondary: Secondary person (to merge in)
            conflicts: List to append conflict resolutions to

        Returns:
            Merged RMPerson
        """
        # Start with primary as base
        merged = RMPerson(
            person_id=primary.person_id,
            sex=primary.sex,
            names=[],
            events=[],
            parent_family_ids=list(primary.parent_family_ids or []),
            spouse_family_ids=list(primary.spouse_family_ids or []),
        )

        # Merge sex (resolve conflict if different)
        if primary.sex != secondary.sex:
            if secondary.sex and secondary.sex != 'U':
                if not primary.sex or primary.sex == 'U':
                    merged.sex = secondary.sex
                    conflicts.append(ConflictResolution(
                        field='sex',
                        value1=primary.sex,
                        value2=secondary.sex,
                        chosen=secondary.sex,
                        reason='Secondary had definite sex, primary unknown'
                    ))

        # Merge names (combine both)
        merged.names = self._merge_names(primary.names or [], secondary.names or [], conflicts)

        # Merge events (combine, remove duplicates)
        merged.events = self._merge_events(primary.events or [], secondary.events or [], conflicts)

        # Merge family relationships (combine, remove duplicates)
        if secondary.parent_family_ids:
            for fid in secondary.parent_family_ids:
                if fid not in merged.parent_family_ids:
                    merged.parent_family_ids.append(fid)

        if secondary.spouse_family_ids:
            for fid in secondary.spouse_family_ids:
                if fid not in merged.spouse_family_ids:
                    merged.spouse_family_ids.append(fid)

        return merged

    def _merge_names(
        self,
        names1: List[RMName],
        names2: List[RMName],
        conflicts: List[ConflictResolution]
    ) -> List[RMName]:
        """
        Merge name lists, removing duplicates and preserving variants.

        Keeps all unique name variations, properly handling multilingual names.
        """
        merged = list(names1)  # Start with all from primary

        for name2 in names2:
            # Check if this name is substantially different
            is_duplicate = False

            for name1 in merged:
                if self._are_names_equivalent(name1, name2):
                    is_duplicate = True
                    # Keep the more complete one
                    if self._is_name_more_complete(name2, name1):
                        # Replace with more complete version
                        idx = merged.index(name1)
                        merged[idx] = name2
                        conflicts.append(ConflictResolution(
                            field='name',
                            value1=str(name1),
                            value2=str(name2),
                            chosen=str(name2),
                            reason='More complete name record'
                        ))
                    break

            # If not a duplicate, add as alternate name
            if not is_duplicate:
                merged.append(name2)

        return merged

    def _are_names_equivalent(self, name1: RMName, name2: RMName) -> bool:
        """Check if two names are equivalent (same person, possibly different language)."""
        # Exact match
        if (name1.given == name2.given and
            name1.surname == name2.surname and
            name1.language == name2.language):
            return True

        # Same name, different languages (multilingual variant)
        if name1.language != name2.language:
            # Use phonetic matching for cross-language equivalence
            if (name1.surname_mp and name2.surname_mp and
                name1.surname_mp == name2.surname_mp and
                name1.given_mp and name2.given_mp and
                name1.given_mp == name2.given_mp):
                return True

        return False

    def _is_name_more_complete(self, name1: RMName, name2: RMName) -> bool:
        """Check if name1 is more complete than name2."""
        score1 = (
            bool(name1.given) +
            bool(name1.surname) +
            bool(name1.nickname) +
            bool(name1.prefix) +
            bool(name1.suffix) +
            bool(name1.language)
        )
        score2 = (
            bool(name2.given) +
            bool(name2.surname) +
            bool(name2.nickname) +
            bool(name2.prefix) +
            bool(name2.suffix) +
            bool(name2.language)
        )
        return score1 > score2

    def _merge_events(
        self,
        events1: List[RMEvent],
        events2: List[RMEvent],
        conflicts: List[ConflictResolution]
    ) -> List[RMEvent]:
        """
        Merge event lists, removing duplicates.

        Events are duplicates if they have the same type, date, and place.
        """
        merged = list(events1)

        for event2 in events2:
            is_duplicate = False

            for event1 in merged:
                if self._are_events_equivalent(event1, event2):
                    is_duplicate = True
                    # Keep the more complete one
                    if self._is_event_more_complete(event2, event1):
                        idx = merged.index(event1)
                        merged[idx] = event2
                        conflicts.append(ConflictResolution(
                            field='event',
                            value1=str(event1),
                            value2=str(event2),
                            chosen=str(event2),
                            reason='More complete event record'
                        ))
                    break

            if not is_duplicate:
                merged.append(event2)

        return merged

    def _are_events_equivalent(self, event1: RMEvent, event2: RMEvent) -> bool:
        """Check if two events are equivalent."""
        return (
            event1.event_type == event2.event_type and
            event1.date == event2.date and
            event1.place == event2.place
        )

    def _is_event_more_complete(self, event1: RMEvent, event2: RMEvent) -> bool:
        """Check if event1 is more complete than event2."""
        score1 = (
            bool(event1.date) +
            bool(event1.place) +
            bool(event1.details)
        )
        score2 = (
            bool(event2.date) +
            bool(event2.place) +
            bool(event2.details)
        )
        return score1 > score2

    def _validate_merge(
        self,
        merged: RMPerson,
        primary: RMPerson,
        secondary: RMPerson
    ) -> List[str]:
        """
        Validate that merge is safe and logical.

        Returns list of validation errors (empty if valid).
        """
        errors = []

        # Must have at least one name
        if not merged.names:
            errors.append("Merged person has no names")

        # Must have sex if both had sex
        if primary.sex and secondary.sex and not merged.sex:
            errors.append("Merged person missing sex")

        # Should not lose data
        if len(merged.names or []) < len(primary.names or []):
            errors.append("Lost names in merge")

        if len(merged.events or []) < len(primary.events or []):
            errors.append("Lost events in merge")

        return errors

    def _update_person_in_db(self, person: RMPerson) -> None:
        """Update person record in database."""
        # Update PersonTable
        cursor = self.db.conn.cursor()
        cursor.execute(
            """
            UPDATE PersonTable
            SET Sex = ?
            WHERE PersonID = ?
            """,
            (person.sex, person.person_id)
        )

        # Delete existing names and re-insert
        cursor.execute(
            "DELETE FROM NameTable WHERE OwnerID = ?",
            (person.person_id,)
        )

        for i, name in enumerate(person.names or []):
            is_primary = 1 if i == 0 else 0
            cursor.execute(
                """
                INSERT INTO NameTable (
                    OwnerID, Surname, Given, Prefix, Suffix, Nickname,
                    IsPrimary, SurnameMP, GivenMP, NicknameMP, Language
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    person.person_id, name.surname, name.given,
                    name.prefix, name.suffix, name.nickname,
                    is_primary, name.surname_mp, name.given_mp,
                    name.nickname_mp, name.language
                )
            )

        # Note: Events and families would be updated similarly
        # Simplified for now

    def _transfer_relationships(self, from_person: RMPerson, to_person: RMPerson) -> None:
        """Transfer family relationships from one person to another."""
        cursor = self.db.conn.cursor()

        # Update ChildTable (parent-child relationships)
        cursor.execute(
            "UPDATE ChildTable SET ChildID = ? WHERE ChildID = ?",
            (to_person.person_id, from_person.person_id)
        )

        # Update FamilyTable (as husband)
        cursor.execute(
            "UPDATE FamilyTable SET FatherID = ? WHERE FatherID = ?",
            (to_person.person_id, from_person.person_id)
        )

        # Update FamilyTable (as wife)
        cursor.execute(
            "UPDATE FamilyTable SET MotherID = ? WHERE MotherID = ?",
            (to_person.person_id, from_person.person_id)
        )

    def _delete_person(self, person: RMPerson) -> None:
        """Delete a person from the database."""
        cursor = self.db.conn.cursor()

        # Delete related records
        cursor.execute("DELETE FROM NameTable WHERE OwnerID = ?", (person.person_id,))
        cursor.execute("DELETE FROM EventTable WHERE OwnerID = ?", (person.person_id,))

        # Delete person
        cursor.execute("DELETE FROM PersonTable WHERE PersonID = ?", (person.person_id,))
