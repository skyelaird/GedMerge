"""Person class for representing individuals in GEDCOM files."""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Self
from .event import Event


@dataclass(slots=True)
class Person:
    """Represents an individual person in a genealogy database.

    Attributes:
        id: Unique identifier (e.g., '@I1@')
        names: List of name variations (given name, married name, etc.)
        sex: Gender ('M', 'F', or 'U' for unknown)
        events: List of life events (birth, death, burial, etc.)
        families_as_spouse: List of family IDs where this person is a spouse
        families_as_child: List of family IDs where this person is a child
        sources: List of source citations
        notes: Additional notes about the person
        attributes: Additional GEDCOM attributes
    """

    id: str
    names: List[str] = field(default_factory=list)
    sex: str = 'U'  # M, F, or U (unknown)
    events: List[Event] = field(default_factory=list)
    families_as_spouse: List[str] = field(default_factory=list)
    families_as_child: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    notes: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        name = self.get_primary_name() or "Unknown"
        birth_year = self.get_birth_year()
        death_year = self.get_death_year()

        if birth_year and death_year:
            return f"{name} ({birth_year}-{death_year})"
        elif birth_year:
            return f"{name} (b. {birth_year})"
        elif death_year:
            return f"{name} (d. {death_year})"
        else:
            return name

    def __repr__(self) -> str:
        """Return a detailed string representation for debugging."""
        return f"Person(id={self.id!r}, name={self.get_primary_name()!r})"

    def get_primary_name(self) -> Optional[str]:
        """Get the primary (first) name in the list.

        Returns:
            Primary name or None if no names exist
        """
        return self.names[0] if self.names else None

    def get_surname(self) -> Optional[str]:
        """Extract surname from primary name.

        Assumes GEDCOM format: "Given Name /Surname/"

        Returns:
            Surname or None if cannot be extracted
        """
        primary_name = self.get_primary_name()
        if not primary_name:
            return None

        # Extract surname between slashes
        import re
        surname_match = re.search(r'/([^/]+)/', primary_name)
        if surname_match:
            return surname_match.group(1)
        return None

    def get_given_name(self) -> Optional[str]:
        """Extract given name from primary name.

        Assumes GEDCOM format: "Given Name /Surname/"

        Returns:
            Given name or None if cannot be extracted
        """
        primary_name = self.get_primary_name()
        if not primary_name:
            return None

        # Extract part before the surname
        import re
        given_match = re.match(r'^([^/]+)', primary_name)
        if given_match:
            return given_match.group(1).strip()
        return None

    def get_event_by_type(self, event_type: str) -> Optional[Event]:
        """Get the first event of a specific type.

        Args:
            event_type: Type of event (e.g., 'BIRT', 'DEAT')

        Returns:
            Event object or None if not found
        """
        for event in self.events:
            if event.type == event_type:
                return event
        return None

    def get_birth_event(self) -> Optional[Event]:
        """Get the birth event.

        Returns:
            Birth Event or None
        """
        return self.get_event_by_type('BIRT')

    def get_death_event(self) -> Optional[Event]:
        """Get the death event.

        Returns:
            Death Event or None
        """
        return self.get_event_by_type('DEAT')

    def get_birth_year(self) -> Optional[int]:
        """Get the year of birth.

        Returns:
            Birth year as integer or None
        """
        birth = self.get_birth_event()
        return birth.get_year() if birth else None

    def get_death_year(self) -> Optional[int]:
        """Get the year of death.

        Returns:
            Death year as integer or None
        """
        death = self.get_death_event()
        return death.get_year() if death else None

    def get_birth_place(self) -> Optional[str]:
        """Get the place of birth.

        Returns:
            Birth place or None
        """
        birth = self.get_birth_event()
        return birth.place if birth else None

    def is_living(self) -> bool:
        """Determine if the person is likely still living.

        Returns:
            False if death event exists, True otherwise
        """
        return self.get_death_event() is None

    def to_dict(self) -> Dict[str, Any]:
        """Convert person to dictionary representation.

        Returns:
            Dictionary containing all person data
        """
        return {
            'id': self.id,
            'names': self.names,
            'sex': self.sex,
            'events': [event.to_dict() for event in self.events],
            'families_as_spouse': self.families_as_spouse,
            'families_as_child': self.families_as_child,
            'sources': self.sources,
            'notes': self.notes,
            'attributes': self.attributes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        """Create a Person instance from a dictionary.

        Args:
            data: Dictionary containing person data

        Returns:
            Person instance
        """
        events = [Event.from_dict(e) for e in data.get('events', [])]
        return cls(
            id=data['id'],
            names=data.get('names', []),
            sex=data.get('sex', 'U'),
            events=events,
            families_as_spouse=data.get('families_as_spouse', []),
            families_as_child=data.get('families_as_child', []),
            sources=data.get('sources', []),
            notes=data.get('notes'),
            attributes=data.get('attributes', {})
        )
