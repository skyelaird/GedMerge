"""Family class for representing family units in GEDCOM files."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Self
from .event import Event


@dataclass(slots=True)
class Family:
    """Represents a family unit (marriage/partnership) in genealogy.

    Attributes:
        id: Unique identifier (e.g., '@F1@')
        husband_id: ID of the husband/partner
        wife_id: ID of the wife/partner
        children_ids: List of child IDs
        marriage_event: Marriage or partnership event
        events: List of family events (marriage, divorce, etc.)
        sources: List of source citations
        notes: Additional notes about the family
        attributes: Additional GEDCOM attributes
    """

    id: str
    husband_id: Optional[str] = None
    wife_id: Optional[str] = None
    children_ids: List[str] = field(default_factory=list)
    events: List[Event] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        parts = [f"Family {self.id}"]
        if self.husband_id:
            parts.append(f"H:{self.husband_id}")
        if self.wife_id:
            parts.append(f"W:{self.wife_id}")
        if self.children_ids:
            parts.append(f"Children:{len(self.children_ids)}")
        return " ".join(parts)

    def __repr__(self) -> str:
        """Return a detailed string representation for debugging."""
        return (f"Family(id={self.id!r}, husband={self.husband_id!r}, "
                f"wife={self.wife_id!r}, children={len(self.children_ids)})")

    def get_parents(self) -> List[str]:
        """Get list of parent IDs.

        Returns:
            List containing husband_id and/or wife_id (excluding None values)
        """
        parents = []
        if self.husband_id:
            parents.append(self.husband_id)
        if self.wife_id:
            parents.append(self.wife_id)
        return parents

    def has_children(self) -> bool:
        """Check if the family has any children.

        Returns:
            True if family has children, False otherwise
        """
        return len(self.children_ids) > 0

    def get_event_by_type(self, event_type: str) -> Optional[Event]:
        """Get the first event of a specific type.

        Args:
            event_type: Type of event (e.g., 'MARR', 'DIV')

        Returns:
            Event object or None if not found
        """
        for event in self.events:
            if event.type == event_type:
                return event
        return None

    def get_marriage_event(self) -> Optional[Event]:
        """Get the marriage event.

        Returns:
            Marriage Event or None
        """
        return self.get_event_by_type('MARR')

    def get_divorce_event(self) -> Optional[Event]:
        """Get the divorce event.

        Returns:
            Divorce Event or None
        """
        return self.get_event_by_type('DIV')

    def get_marriage_year(self) -> Optional[int]:
        """Get the year of marriage.

        Returns:
            Marriage year as integer or None
        """
        marriage = self.get_marriage_event()
        return marriage.get_year() if marriage else None

    def get_marriage_place(self) -> Optional[str]:
        """Get the place of marriage.

        Returns:
            Marriage place or None
        """
        marriage = self.get_marriage_event()
        return marriage.place if marriage else None

    def is_divorced(self) -> bool:
        """Check if the couple is divorced.

        Returns:
            True if divorce event exists, False otherwise
        """
        return self.get_divorce_event() is not None

    def to_dict(self) -> Dict[str, Any]:
        """Convert family to dictionary representation.

        Returns:
            Dictionary containing all family data
        """
        return {
            'id': self.id,
            'husband_id': self.husband_id,
            'wife_id': self.wife_id,
            'children_ids': self.children_ids,
            'events': [event.to_dict() for event in self.events],
            'sources': self.sources,
            'notes': self.notes,
            'attributes': self.attributes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        """Create a Family instance from a dictionary.

        Args:
            data: Dictionary containing family data

        Returns:
            Family instance
        """
        events = [Event.from_dict(e) for e in data.get('events', [])]
        return cls(
            id=data['id'],
            husband_id=data.get('husband_id'),
            wife_id=data.get('wife_id'),
            children_ids=data.get('children_ids', []),
            events=events,
            sources=data.get('sources', []),
            notes=data.get('notes'),
            attributes=data.get('attributes', {})
        )
