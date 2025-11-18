"""Data models for gazetteer."""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum


class PlaceType(Enum):
    """Types of geographic places (from GeoNames)."""
    COUNTRY = "PCLI"
    STATE = "ADM1"
    COUNTY = "ADM2"
    CITY = "PPL"
    TOWN = "PPLA"
    VILLAGE = "PPLX"
    HISTORIC = "HST"
    CEMETERY = "CMTY"
    CHURCH = "CH"
    FARM = "FRM"
    BUILDING = "BLDG"
    OTHER = "OTHER"


@dataclass
class GazetteerPlace:
    """Represents a place in the gazetteer."""

    # Core identifiers
    geonames_id: Optional[int] = None
    name: str = ""
    ascii_name: str = ""

    # Geographic hierarchy
    country_code: str = ""
    admin1_code: str = ""  # State/Province
    admin2_code: str = ""  # County/District
    admin3_code: str = ""  # Municipality
    admin4_code: str = ""  # Village/Locality

    # Coordinates
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Place type
    feature_class: str = ""
    feature_code: str = ""
    place_type: Optional[PlaceType] = None

    # Population (if applicable)
    population: Optional[int] = None

    # Temporal information
    valid_from: Optional[int] = None  # Year
    valid_to: Optional[int] = None    # Year (None = still valid)

    # Alternative names
    alternate_names: List[str] = None

    # Parent place (for hierarchy)
    parent_id: Optional[int] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.alternate_names is None:
            self.alternate_names = []

        # Determine place type from feature code
        if not self.place_type and self.feature_code:
            try:
                self.place_type = PlaceType(self.feature_code)
            except ValueError:
                self.place_type = PlaceType.OTHER

    @property
    def full_hierarchy(self) -> str:
        """Get full hierarchical name."""
        parts = [self.name]

        if self.admin2_code:
            parts.append(self.admin2_code)
        if self.admin1_code:
            parts.append(self.admin1_code)
        if self.country_code:
            parts.append(self.country_code)

        return ", ".join(parts)

    def is_valid_in_year(self, year: int) -> bool:
        """Check if place was valid in a given year."""
        if self.valid_from and year < self.valid_from:
            return False
        if self.valid_to and year > self.valid_to:
            return False
        return True

    def matches_name(self, name: str, fuzzy: bool = True) -> bool:
        """Check if this place matches a given name."""
        name_lower = name.lower()

        # Exact match
        if self.name.lower() == name_lower:
            return True
        if self.ascii_name.lower() == name_lower:
            return True

        # Check alternates
        if any(alt.lower() == name_lower for alt in self.alternate_names):
            return True

        # Fuzzy match (contains)
        if fuzzy:
            if name_lower in self.name.lower():
                return True
            if name_lower in self.ascii_name.lower():
                return True

        return False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'geonames_id': self.geonames_id,
            'name': self.name,
            'ascii_name': self.ascii_name,
            'country_code': self.country_code,
            'admin1_code': self.admin1_code,
            'admin2_code': self.admin2_code,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'feature_code': self.feature_code,
            'place_type': self.place_type.value if self.place_type else None,
            'population': self.population,
            'valid_from': self.valid_from,
            'valid_to': self.valid_to,
            'alternate_names': self.alternate_names,
            'full_hierarchy': self.full_hierarchy
        }


@dataclass
class PlaceMatch:
    """Represents a match between an input place and gazetteer place."""

    input_place: str
    gazetteer_place: GazetteerPlace
    confidence: float  # 0.0 to 1.0
    match_type: str    # 'exact', 'alternate', 'fuzzy', 'context'
    context_score: float = 0.0  # Additional context-based score

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'input_place': self.input_place,
            'gazetteer_place': self.gazetteer_place.to_dict(),
            'confidence': self.confidence,
            'match_type': self.match_type,
            'context_score': self.context_score,
            'total_score': self.confidence + self.context_score
        }
