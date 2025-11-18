"""Place class for representing locations with multilingual support."""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Self


@dataclass(slots=True)
class Place:
    """Represents a geographical location with support for multilingual names.

    This class allows storing place names in multiple languages, which is essential
    for genealogical research involving international locations or historical name changes.

    Attributes:
        names: Dictionary mapping language codes (ISO 639-1) to place names
        primary_language: The primary language code for this place (defaults to 'en')
        latitude: Optional latitude coordinate
        longitude: Optional longitude coordinate
        place_type: Type of place (city, country, region, etc.)
        notes: Additional notes about the place
        hierarchy: List of parent places (e.g., ['USA', 'California', 'Los Angeles'])
        parent_place: Optional reference to parent Place object (for nested hierarchy)
        place_id: Optional database ID for this place
        parent_id: Optional database ID of parent place
    """

    names: Dict[str, str] = field(default_factory=dict)
    primary_language: str = "en"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    place_type: Optional[str] = None
    notes: Optional[str] = None
    hierarchy: List[str] = field(default_factory=list)
    parent_place: Optional['Place'] = None
    place_id: Optional[int] = None
    parent_id: Optional[int] = None

    def __post_init__(self):
        """Ensure names dictionary is initialized and primary language is set."""
        if not isinstance(self.names, dict):
            # If initialized with a string, treat it as English name
            if isinstance(self.names, str):
                self.names = {self.primary_language: self.names}
            else:
                self.names = {}

    def add_name(self, language: str, name: str) -> None:
        """Add a place name in a specific language.

        Args:
            language: ISO 639-1 language code (e.g., 'en', 'de', 'fr', 'es')
            name: The place name in that language
        """
        self.names[language] = name

    def get_name(self, language: Optional[str] = None) -> Optional[str]:
        """Get the place name in a specific language.

        Args:
            language: ISO 639-1 language code. If None, returns primary language name.

        Returns:
            The place name in the requested language, or None if not available.
            Falls back to primary language if requested language is not available.
        """
        if language is None:
            language = self.primary_language

        # Try to get the requested language
        if language in self.names:
            return self.names[language]

        # Fall back to primary language
        if self.primary_language in self.names:
            return self.names[self.primary_language]

        # Fall back to any available name
        if self.names:
            return next(iter(self.names.values()))

        return None

    def get_all_names(self) -> Dict[str, str]:
        """Get all place names in all languages.

        Returns:
            Dictionary mapping language codes to place names
        """
        return self.names.copy()

    def __str__(self) -> str:
        """Return a human-readable string representation using primary language."""
        name = self.get_name()
        if name:
            return name
        return "Unknown Place"

    def __repr__(self) -> str:
        """Return a detailed string representation for debugging."""
        return f"Place(names={self.names!r}, primary_language={self.primary_language!r})"

    def to_dict(self) -> Dict[str, Any]:
        """Convert place to dictionary representation.

        Returns:
            Dictionary containing all place data
        """
        return {
            'names': self.names,
            'primary_language': self.primary_language,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'place_type': self.place_type,
            'notes': self.notes,
            'hierarchy': self.hierarchy,
            'place_id': self.place_id,
            'parent_id': self.parent_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Self:
        """Create a Place instance from a dictionary.

        Args:
            data: Dictionary containing place data

        Returns:
            Place instance
        """
        return cls(
            names=data.get('names', {}),
            primary_language=data.get('primary_language', 'en'),
            latitude=data.get('latitude'),
            longitude=data.get('longitude'),
            place_type=data.get('place_type'),
            notes=data.get('notes'),
            hierarchy=data.get('hierarchy', []),
            place_id=data.get('place_id'),
            parent_id=data.get('parent_id'),
        )

    @classmethod
    def from_string(cls, place_string: str, language: str = 'en') -> Self:
        """Create a Place instance from a simple string.

        This is a convenience method for backward compatibility with existing code
        that uses simple strings for places.

        Args:
            place_string: The place name as a string
            language: The language code for this place name (default: 'en')

        Returns:
            Place instance with the given name
        """
        return cls(names={language: place_string}, primary_language=language)

    def is_empty(self) -> bool:
        """Check if this place has any names defined.

        Returns:
            True if no names are defined, False otherwise
        """
        return len(self.names) == 0

    def has_coordinates(self) -> bool:
        """Check if this place has geographical coordinates.

        Returns:
            True if both latitude and longitude are defined, False otherwise
        """
        return self.latitude is not None and self.longitude is not None

    def get_gedcom_format(self, language: Optional[str] = None) -> str:
        """Get the place name in GEDCOM format.

        GEDCOM typically uses comma-separated hierarchical format:
        City, County, State, Country

        Args:
            language: Language code for the name. If None, uses primary language.

        Returns:
            Place name in GEDCOM format
        """
        name = self.get_name(language)
        if not name:
            return ""

        # If we have hierarchy information, use it
        if self.hierarchy:
            return ", ".join(self.hierarchy)

        return name

    def merge_with(self, other: Self) -> Self:
        """Merge this place with another, combining multilingual names.

        Args:
            other: Another Place instance to merge with

        Returns:
            New Place instance with combined information
        """
        # Combine names from both places
        merged_names = self.names.copy()
        merged_names.update(other.names)

        # Use the more complete hierarchy
        merged_hierarchy = self.hierarchy if len(self.hierarchy) > len(other.hierarchy) else other.hierarchy

        return Place(
            names=merged_names,
            primary_language=self.primary_language,
            latitude=self.latitude or other.latitude,
            longitude=self.longitude or other.longitude,
            place_type=self.place_type or other.place_type,
            notes=self.notes or other.notes,
            hierarchy=merged_hierarchy
        )

    def get_full_hierarchy(self, language: Optional[str] = None) -> List[str]:
        """Get the full hierarchical path from root to this place.

        Traverses parent_place references to build the full hierarchy.

        Args:
            language: Language code for place names (default: primary_language)

        Returns:
            List of place names from most general to most specific
            e.g., ['Canada', 'Québec', 'Québec City', 'Cathédrale Notre-Dame de Québec']
        """
        path = []
        current = self

        # Traverse up to the root
        while current is not None:
            name = current.get_name(language)
            if name:
                path.insert(0, name)  # Insert at beginning to build root-to-leaf path
            current = current.parent_place

        return path

    def get_hierarchy_string(self, language: Optional[str] = None, separator: str = ", ") -> str:
        """Get the full hierarchical path as a formatted string.

        Args:
            language: Language code for place names (default: primary_language)
            separator: String to use between hierarchy levels (default: ", ")

        Returns:
            Formatted hierarchy string
            e.g., "Canada, Québec, Québec City, Cathédrale Notre-Dame de Québec"
        """
        hierarchy = self.get_full_hierarchy(language)
        return separator.join(hierarchy)

    def is_descendant_of(self, ancestor: Self) -> bool:
        """Check if this place is a descendant of another place.

        Args:
            ancestor: Potential ancestor place

        Returns:
            True if this place is a descendant of the given ancestor
        """
        current = self.parent_place

        while current is not None:
            if current == ancestor or (
                current.place_id is not None and
                ancestor.place_id is not None and
                current.place_id == ancestor.place_id
            ):
                return True
            current = current.parent_place

        return False

    def get_depth(self) -> int:
        """Get the depth of this place in the hierarchy.

        Returns:
            Depth level (0 for root places, 1 for their children, etc.)
        """
        depth = 0
        current = self.parent_place

        while current is not None:
            depth += 1
            current = current.parent_place

        return depth

    def set_parent(self, parent: Optional[Self]) -> None:
        """Set the parent place for this place.

        Args:
            parent: Parent Place object, or None to remove parent
        """
        self.parent_place = parent
        if parent is not None and parent.place_id is not None:
            self.parent_id = parent.place_id
        else:
            self.parent_id = None
