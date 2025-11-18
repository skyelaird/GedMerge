# Gazetteer Requirements for GedMerge

## Overview

A gazetteer is a geographical dictionary or directory used for place name disambiguation and validation in genealogical research. This document outlines the requirements for implementing a gazetteer function in GedMerge.

## Problem Statement

Genealogical databases often contain ambiguous or duplicate place names that cannot be resolved without historical geographical context:

### Examples of Issues

1. **Cross-Continental Ambiguity**
   - **Issue**: `Cambridge, Middlesex, England` vs `Cambridge, Middlesex, Massachusetts`
   - **Context Needed**: Event dates (Massachusetts was a colony 1630-1776, then part of USA)
   - **Solution**: Gazetteer should know:
     - Middlesex County, Massachusetts, USA (1643-present)
     - Middlesex County, England (historic county, 1889-1965)

2. **Historical Administrative Changes**
   - **Issue**: County boundaries and names changed over time
   - **Examples**:
     - `Burton, Oxfordshire, England` - which county is accurate to the time period?
     - Massachusetts was a colony (1620-1776), then a state (1776-present)
   - **Solution**: Gazetteer should track valid date ranges for place names

3. **Regional Variations**
   - **Issue**: `Warwick` vs `Warwickshire` (UK county variations)
   - **Issue**: `Carcassonne, Aude, France` vs `Carcassonne, Aude, Languedoc, France`
   - **Solution**: Gazetteer should know canonical names and acceptable variations

4. **Multi-Lingual Place Names**
   - **Issue**: `Spain` (English) vs `España` (Spanish)
   - **Solution**: Gazetteer should store place names in multiple languages with the canonical name in the place's native language

## Core Requirements

### 1. Place Name Storage

```python
@dataclass
class GazetteerPlace:
    """A place in the gazetteer with full historical context."""

    # Unique identifiers
    gazetteer_id: str  # e.g., "geonames:2643743" or "wikidata:Q84"

    # Names in multiple languages
    names: Dict[str, str]  # ISO 639-1 code -> name
    canonical_name: str  # In the place's native language
    canonical_language: str  # ISO 639-1 code

    # Geographical hierarchy
    hierarchy: List[str]  # From most general to most specific
    parent_id: Optional[str]  # Parent place gazetteer_id
    place_type: str  # 'country', 'state', 'county', 'city', 'town', etc.

    # Coordinates
    latitude: Optional[float]
    longitude: Optional[float]

    # Temporal validity
    valid_from: Optional[int]  # Year this place name became valid
    valid_to: Optional[int]  # Year this place name ceased to be valid

    # Alternative names and spellings
    alternate_names: List[str]
    historical_names: List[Tuple[str, int, int]]  # (name, from_year, to_year)

    # Administrative context
    country_code: str  # ISO 3166-1 alpha-2
    admin1_code: Optional[str]  # State/province code
    admin2_code: Optional[str]  # County/district code
```

### 2. Temporal Validation

The gazetteer must support temporal queries:

```python
def get_valid_places_for_date(place_name: str, date_year: int) -> List[GazetteerPlace]:
    """Get all places matching this name that were valid in the given year.

    Examples:
        get_valid_places_for_date("Massachusetts", 1650)
        # Returns: Massachusetts Bay Colony (1620-1776)

        get_valid_places_for_date("Massachusetts", 1800)
        # Returns: Massachusetts, USA (1776-present)
    """
```

### 3. Disambiguation Logic

The gazetteer should provide disambiguation based on context:

```python
def disambiguate_place(
    place_name: str,
    event_date: Optional[int] = None,
    person_birth_place: Optional[str] = None,
    related_places: List[str] = None
) -> List[Tuple[GazetteerPlace, float]]:
    """Disambiguate a place name using context clues.

    Args:
        place_name: The ambiguous place name
        event_date: Year of the event at this place
        person_birth_place: Birth place of the person (for geographic proximity)
        related_places: Other places in the person's family tree

    Returns:
        List of (place, confidence_score) tuples, sorted by confidence

    Example:
        disambiguate_place(
            "Cambridge, Middlesex",
            event_date=1650,
            person_birth_place="London, England"
        )
        # Returns: [
        #   (Cambridge, England, 0.95),  # High confidence - temporal and geographic match
        #   (Cambridge, Massachusetts, 0.05)  # Low confidence - wrong continent
        # ]
    """
```

### 4. Hierarchical Normalization

The gazetteer should normalize place hierarchies:

```python
def normalize_place_hierarchy(
    place_name: str,
    date_year: Optional[int] = None
) -> str:
    """Normalize place hierarchy to canonical format.

    Examples:
        normalize_place_hierarchy("Canterbury, England", 1500)
        # Returns: "Canterbury, Kent, England"

        normalize_place_hierarchy("Canterbury Cathedral", 1500)
        # Returns: "Canterbury Cathedral, Canterbury, Kent, England"
        # (with suggestion to make Cathedral a child place of Canterbury)
    """
```

## Data Sources

### Primary Sources

1. **GeoNames** (http://www.geonames.org/)
   - Free geographical database
   - 25+ million place names
   - Historical data available
   - Multiple languages
   - **License**: Creative Commons Attribution 4.0

2. **Wikidata** (https://www.wikidata.org/)
   - Structured data from Wikipedia
   - Excellent historical coverage
   - Multi-lingual
   - Administrative divisions with date ranges
   - **License**: CC0 (Public Domain)

3. **Getty Thesaurus of Geographic Names** (TGN)
   - Focus on art/historical places
   - Excellent historical coverage
   - **License**: Open Data Commons Attribution License

### Specialized Sources

1. **Historical Counties of England/Wales/Scotland**
   - GENUKI (http://www.genuki.org.uk/)
   - Historic county boundaries
   - Pre-1974 administrative divisions

2. **US Historical Gazetteer**
   - National Historical Geographic Information System (NHGIS)
   - County boundary changes over time
   - Colonial-era place names

3. **FamilySearch Places Database**
   - Genealogy-focused place authority
   - Historical administrative divisions
   - **API available**

## Implementation Phases

### Phase 1: Basic Gazetteer (MVP)

**Scope**: Core disambiguation for common cases

**Features**:
- Load place data from GeoNames
- Store in SQLite database
- Basic disambiguation by name matching
- Temporal validation (valid_from/valid_to dates)
- Multi-lingual name support

**Database Schema**:
```sql
CREATE TABLE gazetteer_places (
    gazetteer_id TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL,
    canonical_language TEXT,
    place_type TEXT,
    country_code TEXT,
    latitude REAL,
    longitude REAL,
    valid_from INTEGER,
    valid_to INTEGER,
    parent_id TEXT,
    FOREIGN KEY (parent_id) REFERENCES gazetteer_places(gazetteer_id)
);

CREATE TABLE gazetteer_names (
    gazetteer_id TEXT,
    language_code TEXT,
    name TEXT,
    is_canonical BOOLEAN DEFAULT 0,
    PRIMARY KEY (gazetteer_id, language_code),
    FOREIGN KEY (gazetteer_id) REFERENCES gazetteer_places(gazetteer_id)
);

CREATE TABLE gazetteer_historical_names (
    gazetteer_id TEXT,
    name TEXT,
    valid_from INTEGER,
    valid_to INTEGER,
    PRIMARY KEY (gazetteer_id, name, valid_from),
    FOREIGN KEY (gazetteer_id) REFERENCES gazetteer_places(gazetteer_id)
);
```

### Phase 2: Context-Aware Disambiguation

**Features**:
- Use event dates to disambiguate
- Geographic proximity scoring
- Family tree context (if person's parents were in England, likely child is too)
- Administrative hierarchy normalization

### Phase 3: Advanced Features

**Features**:
- Historical county boundary changes
- Colonial-era place names
- Crowdsourced corrections/additions
- Machine learning for disambiguation
- Integration with FamilySearch Places API

## API Design

### Lookup Functions

```python
class Gazetteer:
    """Gazetteer service for place name resolution."""

    def lookup_by_name(
        self,
        name: str,
        country_code: Optional[str] = None,
        place_type: Optional[str] = None,
        date_year: Optional[int] = None
    ) -> List[GazetteerPlace]:
        """Look up places by name with optional filters."""

    def lookup_by_coordinates(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10,
        date_year: Optional[int] = None
    ) -> List[GazetteerPlace]:
        """Find places near coordinates."""

    def lookup_by_id(self, gazetteer_id: str) -> Optional[GazetteerPlace]:
        """Get place by gazetteer ID."""

    def get_hierarchy(self, gazetteer_id: str) -> List[GazetteerPlace]:
        """Get full place hierarchy from root to leaf."""

    def suggest_matches(
        self,
        place_string: str,
        event_date: Optional[int] = None,
        context_places: List[str] = None
    ) -> List[Tuple[GazetteerPlace, float]]:
        """Suggest matching places with confidence scores."""
```

### Integration with Existing Code

The gazetteer should integrate with existing PlaceCleaner:

```python
# In place_cleaner.py
class PlaceCleaner:

    @classmethod
    def clean_and_disambiguate(
        cls,
        place_name: str,
        gazetteer: Optional[Gazetteer] = None,
        event_date: Optional[int] = None,
        **kwargs
    ) -> Tuple[CleanedPlace, Optional[GazetteerPlace]]:
        """Clean place name and optionally disambiguate using gazetteer.

        Returns:
            Tuple of (cleaned_place, gazetteer_match)
        """
```

## Use Cases

### Use Case 1: Cambridge Disambiguation

**Input**:
- Place: "Cambridge, Middlesex"
- Event: Birth
- Date: 1650
- Person's father's birth place: "London, England"

**Process**:
1. PlaceCleaner normalizes to "Cambridge, Middlesex"
2. Gazetteer finds two matches:
   - Cambridge, Middlesex, England (geonames:2653941)
   - Cambridge, Middlesex, Massachusetts (geonames:4931972)
3. Apply temporal filter (1650):
   - Cambridge, England: valid 500-present ✓
   - Cambridge, MA: valid 1630-present ✓
4. Apply geographic context (father born in London):
   - Cambridge, England: same country, 80km away, score: 0.95
   - Cambridge, MA: different continent, 5000km away, score: 0.05
5. Return: Cambridge, Middlesex, England (95% confidence)

### Use Case 2: Historical County Normalization

**Input**:
- Place: "Canterbury, England"
- Event: Marriage
- Date: 1500

**Process**:
1. PlaceCleaner normalizes to "Canterbury, England"
2. Gazetteer recognizes incomplete hierarchy
3. Lookup Canterbury in England for year 1500
4. Find: Canterbury, Kent, England
5. Return normalized: "Canterbury, Kent, England"

### Use Case 3: Massachusetts Colony vs State

**Input**:
- Place: "Boston, Massachusetts"
- Event: Birth
- Date: 1750

**Process**:
1. PlaceCleaner normalizes to "Boston, Massachusetts"
2. Gazetteer lookup for year 1750
3. Find: Boston, Massachusetts Bay Colony (1630-1776)
4. Return: "Boston, Massachusetts Bay Colony" (not "Boston, Massachusetts, USA")

## Maintenance

### Data Updates

- GeoNames updates monthly - automated sync needed
- Historical data rarely changes - annual review sufficient
- User-contributed corrections - manual review process

### Quality Assurance

- Automated tests for common disambiguation scenarios
- User feedback mechanism for incorrect matches
- Periodic review of low-confidence matches

## Future Enhancements

1. **Machine Learning**
   - Train models on genealogical data to improve disambiguation
   - Learn from user corrections

2. **Collaborative Editing**
   - Allow users to contribute corrections
   - Crowdsource historical place data

3. **Integration with External Services**
   - FamilySearch Places API
   - Ancestry place authority
   - FindMyPast location data

4. **Visualization**
   - Map view of person's life events
   - Migration patterns
   - Family geographic distribution

## References

- GeoNames: http://www.geonames.org/
- Wikidata: https://www.wikidata.org/
- Getty TGN: http://www.getty.edu/research/tools/vocabularies/tgn/
- FamilySearch Places: https://www.familysearch.org/developers/docs/guides/places
- GENUKI: http://www.genuki.org.uk/
- Vision of Britain: http://www.visionofbritain.org.uk/

## Notes for Implementation

### Performance Considerations

- **Database Indexing**: Create indexes on name, country_code, valid_from, valid_to
- **Caching**: Cache frequently-accessed places (top 1000 most common)
- **Fuzzy Matching**: Use trigram similarity or Levenshtein distance for approximate matches
- **Geographic Indexing**: Use R-tree or PostGIS for spatial queries

### Privacy and Data Protection

- Gazetteer data is public geographical information
- No personal data stored in gazetteer
- User corrections may need GDPR consideration if they include personal context

### Testing Strategy

1. **Unit Tests**: Test each lookup function
2. **Integration Tests**: Test with real genealogical data
3. **Performance Tests**: Ensure sub-100ms query times
4. **Accuracy Tests**: Validate disambiguation against known-correct samples

---

**Document Version**: 1.0
**Last Updated**: 2025-11-16
**Author**: Claude (GedMerge AI Assistant)
