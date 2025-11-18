"""Event class for representing GEDCOM events."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union, Self
from .place import Place


@dataclass(slots=True)
class Event:
    """Represents a genealogical event (birth, death, marriage, etc.).

    Attributes:
        type: The type of event (e.g., 'BIRT', 'DEAT', 'MARR', 'BURI')
        date: The date of the event in GEDCOM format
        place: The place where the event occurred (can be a Place object or string for backward compatibility)
        notes: Additional notes about the event
        sources: List of source citations for this event
        attributes: Additional GEDCOM attributes (e.g., AGE, CAUS)
    """

    type: str
    date: Optional[str] = None
    place: Optional[Union[Place, str]] = None
    notes: Optional[str] = None
    sources: list = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Convert string places to Place objects for consistency."""
        if isinstance(self.place, str) and self.place:
            self.place = Place.from_string(self.place)

    def get_place_name(self, language: Optional[str] = None) -> Optional[str]:
        """Get the place name, handling both Place objects and strings.

        Args:
            language: Optional language code for multilingual places

        Returns:
            The place name as a string, or None if no place is set
        """
        if self.place is None:
            return None
        if isinstance(self.place, Place):
            return self.place.get_name(language)
        return str(self.place)

    def set_place(self, place: Union[Place, str, None], language: str = 'en') -> None:
        """Set the place for this event.

        Args:
            place: Place object, string, or None
            language: Language code if place is a string (default: 'en')
        """
        if place is None:
            self.place = None
        elif isinstance(place, str):
            self.place = Place.from_string(place, language)
        else:
            self.place = place

    def __str__(self) -> str:
        """Return a human-readable string representation of the event."""
        parts = [self.type]
        if self.date:
            parts.append(f"on {self.date}")
        place_name = self.get_place_name()
        if place_name:
            parts.append(f"at {place_name}")
        return " ".join(parts)

    def __repr__(self) -> str:
        """Return a detailed string representation for debugging."""
        return f"Event(type={self.type!r}, date={self.date!r}, place={self.place!r})"

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary representation."""
        place_data = None
        if self.place is not None:
            if isinstance(self.place, Place):
                place_data = self.place.to_dict()
            else:
                place_data = str(self.place)

        return {
            'type': self.type,
            'date': self.date,
            'place': place_data,
            'notes': self.notes,
            'sources': self.sources,
            'attributes': self.attributes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        """Create an Event instance from a dictionary.

        Args:
            data: Dictionary containing event data

        Returns:
            Event instance
        """
        place_data = data.get('place')
        place = None
        if place_data is not None:
            if isinstance(place_data, dict):
                place = Place.from_dict(place_data)
            else:
                place = str(place_data)

        return cls(
            type=data['type'],
            date=data.get('date'),
            place=place,
            notes=data.get('notes'),
            sources=data.get('sources', []),
            attributes=data.get('attributes', {})
        )

    def is_valid(self) -> bool:
        """Check if the event has minimum required information.

        Returns:
            True if event has at least a type, False otherwise
        """
        return bool(self.type)

    def get_year(self) -> Optional[int]:
        """Extract year from date string if possible.

        Returns:
            Year as integer, or None if cannot be extracted
        """
        if not self.date:
            return None

        # Try to find a 4-digit year in the date string
        import re
        year_match = re.search(r'\b(\d{4})\b', self.date)
        if year_match:
            return int(year_match.group(1))
        return None
