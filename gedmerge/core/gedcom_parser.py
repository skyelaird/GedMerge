"""GEDCOM parser for reading and writing genealogy files."""

from typing import Any, Dict, List, Tuple, Optional
from pathlib import Path
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement
from gedcom.element.family import FamilyElement

from .person import Person
from .family import Family
from .event import Event
from .place import Place


class GedcomParser:
    """Parser for GEDCOM files supporting versions 5.5 and 5.5.1."""

    def __init__(self):
        """Initialize the parser."""
        self.parser: Optional[Parser] = None
        self.individuals: Dict[str, Person] = {}
        self.families: Dict[str, Family] = {}

    def load_gedcom(self, filepath: str) -> Tuple[Dict[str, Person], Dict[str, Family]]:
        """Load and parse a GEDCOM file.

        Args:
            filepath: Path to the GEDCOM file

        Returns:
            Tuple of (individuals dict, families dict)

        Raises:
            FileNotFoundError: If the file doesn't exist
            ValueError: If the file is not a valid GEDCOM file
        """
        file_path = Path(filepath)
        if not file_path.exists():
            raise FileNotFoundError(f"GEDCOM file not found: {filepath}")

        # Initialize the parser
        self.parser = Parser()

        # Try parsing with different encodings
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
        last_error = None

        for encoding in encodings:
            try:
                # Read file with specific encoding and re-save as UTF-8
                with open(filepath, 'r', encoding=encoding) as f:
                    content = f.read()

                # Create temporary file with UTF-8 encoding
                import tempfile
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                                 suffix='.ged', delete=False) as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name

                try:
                    self.parser.parse_file(tmp_path, strict=False)
                    break
                finally:
                    # Clean up temporary file
                    import os
                    os.unlink(tmp_path)

            except (UnicodeDecodeError, Exception) as e:
                last_error = e
                continue
        else:
            # All encodings failed
            raise ValueError(f"Could not parse GEDCOM file with any encoding: {last_error}")

        # Extract individuals and families
        self.individuals = self._extract_individuals()
        self.families = self._extract_families()

        return self.individuals, self.families

    def _extract_individuals(self) -> Dict[str, Person]:
        """Extract all individuals from the parsed GEDCOM file.

        Returns:
            Dictionary mapping individual IDs to Person objects
        """
        individuals = {}

        if not self.parser:
            return individuals

        for element in self.parser.get_root_child_elements():
            if isinstance(element, IndividualElement):
                person = self._parse_individual(element)
                individuals[person.id] = person

        return individuals

    def _extract_families(self) -> Dict[str, Family]:
        """Extract all families from the parsed GEDCOM file.

        Returns:
            Dictionary mapping family IDs to Family objects
        """
        families = {}

        if not self.parser:
            return families

        for element in self.parser.get_root_child_elements():
            if isinstance(element, FamilyElement):
                family = self._parse_family(element)
                families[family.id] = family

        return families

    def _parse_individual(self, element: IndividualElement) -> Person:
        """Parse an individual element into a Person object.

        Args:
            element: IndividualElement from python-gedcom

        Returns:
            Person object
        """
        person_id = element.get_pointer()

        # Extract names
        names = []
        name_elements = element.get_name()
        if name_elements:
            for name_elem in name_elements if isinstance(name_elements, list) else [name_elements]:
                if name_elem:
                    # Convert tuple to GEDCOM format string if needed
                    if isinstance(name_elem, tuple):
                        given, surname = name_elem
                        name_str = f"{given} /{surname}/" if surname else given
                        names.append(name_str)
                    elif isinstance(name_elem, str):
                        names.append(name_elem)
                    else:
                        names.append(str(name_elem))

        # Get sex
        sex = element.get_gender() or 'U'

        # Extract events
        events = self._parse_events(element)

        # Get family relationships
        families_as_spouse = []
        families_as_child = []

        for child in element.get_child_elements():
            tag = child.get_tag()
            value = child.get_value()

            if tag == 'FAMS' and value:
                families_as_spouse.append(value)
            elif tag == 'FAMC' and value:
                families_as_child.append(value)

        # Create person object
        person = Person(
            id=person_id,
            names=names,
            sex=sex,
            events=events,
            families_as_spouse=families_as_spouse,
            families_as_child=families_as_child
        )

        return person

    def _parse_family(self, element: FamilyElement) -> Family:
        """Parse a family element into a Family object.

        Args:
            element: FamilyElement from python-gedcom

        Returns:
            Family object
        """
        family_id = element.get_pointer()

        # Get husband and wife
        husband_id = None
        wife_id = None
        children_ids = []

        for child in element.get_child_elements():
            tag = child.get_tag()
            value = child.get_value()

            if tag == 'HUSB' and value:
                husband_id = value
            elif tag == 'WIFE' and value:
                wife_id = value
            elif tag == 'CHIL' and value:
                children_ids.append(value)

        # Extract family events
        events = self._parse_events(element)

        # Create family object
        family = Family(
            id=family_id,
            husband_id=husband_id,
            wife_id=wife_id,
            children_ids=children_ids,
            events=events
        )

        return family

    def _parse_events(self, element) -> List[Event]:
        """Parse events from an individual or family element.

        Args:
            element: Individual or Family element

        Returns:
            List of Event objects
        """
        events = []
        event_tags = ['BIRT', 'DEAT', 'BURI', 'CHR', 'BAPM', 'MARR', 'DIV',
                      'GRAD', 'RETI', 'EVEN', 'OCCU', 'RESI']

        for child in element.get_child_elements():
            tag = child.get_tag()

            if tag in event_tags:
                event = self._parse_event(child, tag)
                if event:
                    events.append(event)

        return events

    def _parse_event(self, element, event_type: str) -> Optional[Event]:
        """Parse a single event element with multilingual place support.

        Args:
            element: Event element
            event_type: Type of event (tag)

        Returns:
            Event object or None
        """
        date = None
        place = None
        notes = None
        attributes = {}

        for child in element.get_child_elements():
            tag = child.get_tag()
            value = child.get_value()

            if tag == 'DATE' and value:
                date = value
            elif tag == 'PLAC' and value:
                # Parse place with multilingual support
                place = self._parse_place(child, value)
            elif tag == 'NOTE' and value:
                notes = value if not notes else notes + ' ' + value
            elif tag == 'TYPE' and value:
                attributes['TYPE'] = value
            elif tag == 'CONC' and value:
                # Continuation of previous field (typically NOTE)
                if notes:
                    notes += value
            elif tag == 'CONT' and value:
                # Continuation with newline
                if notes:
                    notes += '\n' + value

        return Event(
            type=event_type,
            date=date,
            place=place,
            notes=notes,
            attributes=attributes
        )

    def _parse_place(self, element, primary_name: str) -> Place:
        """Parse a place with multilingual variations and coordinates.

        GEDCOM 5.5.1 supports place variations through:
        - ROMN: Romanized variation
        - FONE: Phonetic variation
        - MAP/LATI/LONG: Coordinates

        Args:
            element: PLAC element
            primary_name: The primary place name

        Returns:
            Place object with multilingual support
        """
        names = {'en': primary_name}  # Default to English for primary name
        latitude = None
        longitude = None
        notes = None

        # Parse sub-elements for variations and coordinates
        for child in element.get_child_elements():
            tag = child.get_tag()
            value = child.get_value()

            if tag == 'ROMN' and value:
                # Romanized version (often used for non-Latin scripts)
                # Check for language attribute
                lang = self._get_language_from_element(child) or 'romn'
                names[lang] = value
            elif tag == 'FONE' and value:
                # Phonetic version
                lang = self._get_language_from_element(child) or 'fone'
                names[lang] = value
            elif tag == 'MAP':
                # Parse coordinates from MAP subelement
                for map_child in child.get_child_elements():
                    map_tag = map_child.get_tag()
                    map_value = map_child.get_value()
                    if map_tag == 'LATI' and map_value:
                        latitude = self._parse_coordinate(map_value)
                    elif map_tag == 'LONG' and map_value:
                        longitude = self._parse_coordinate(map_value)
            elif tag == 'NOTE' and value:
                notes = value

        # Create Place object
        place = Place(
            names=names,
            primary_language='en',
            latitude=latitude,
            longitude=longitude,
            notes=notes
        )

        return place

    def _get_language_from_element(self, element) -> Optional[str]:
        """Extract language code from GEDCOM element.

        Args:
            element: GEDCOM element that may have a LANG subtag

        Returns:
            Language code or None
        """
        for child in element.get_child_elements():
            if child.get_tag() == 'LANG':
                return child.get_value()
        return None

    def _parse_coordinate(self, coord_str: str) -> Optional[float]:
        """Parse a GEDCOM coordinate string to decimal degrees.

        GEDCOM coordinates can be in formats like:
        - N18.150833
        - S18.150833
        - E45.234567
        - W45.234567

        Args:
            coord_str: Coordinate string from GEDCOM

        Returns:
            Coordinate as decimal degrees, or None if parsing fails
        """
        if not coord_str:
            return None

        try:
            coord_str = coord_str.strip()
            # Check for directional prefix
            if coord_str[0] in 'NSEW':
                direction = coord_str[0]
                value = float(coord_str[1:])
                # South and West are negative
                if direction in 'SW':
                    value = -value
                return value
            else:
                # Try parsing as plain number
                return float(coord_str)
        except (ValueError, IndexError):
            return None

    def save_gedcom(self, filepath: str, individuals: Dict[str, Person],
                    families: Dict[str, Family]) -> None:
        """Save individuals and families to a GEDCOM file.

        Args:
            filepath: Path where the GEDCOM file will be saved
            individuals: Dictionary of Person objects
            families: Dictionary of Family objects
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            # Write header
            f.write("0 HEAD\n")
            f.write("1 SOUR GEDMerge\n")
            f.write("2 VERS 0.1.0\n")
            f.write("1 GEDC\n")
            f.write("2 VERS 5.5.1\n")
            f.write("2 FORM LINEAGE-LINKED\n")
            f.write("1 CHAR UTF-8\n")

            # Write individuals
            for person in individuals.values():
                self._write_individual(f, person)

            # Write families
            for family in families.values():
                self._write_family(f, family)

            # Write trailer
            f.write("0 TRLR\n")

    def _write_individual(self, f, person: Person) -> None:
        """Write an individual to the GEDCOM file.

        Args:
            f: File object
            person: Person object to write
        """
        f.write(f"0 {person.id} INDI\n")

        # Write names
        for name in person.names:
            f.write(f"1 NAME {name}\n")

        # Write sex
        if person.sex != 'U':
            f.write(f"1 SEX {person.sex}\n")

        # Write events
        for event in person.events:
            self._write_event(f, event, level=1)

        # Write family relationships
        for fam_id in person.families_as_spouse:
            f.write(f"1 FAMS {fam_id}\n")

        for fam_id in person.families_as_child:
            f.write(f"1 FAMC {fam_id}\n")

    def _write_family(self, f, family: Family) -> None:
        """Write a family to the GEDCOM file.

        Args:
            f: File object
            family: Family object to write
        """
        f.write(f"0 {family.id} FAM\n")

        # Write husband
        if family.husband_id:
            f.write(f"1 HUSB {family.husband_id}\n")

        # Write wife
        if family.wife_id:
            f.write(f"1 WIFE {family.wife_id}\n")

        # Write children
        for child_id in family.children_ids:
            f.write(f"1 CHIL {child_id}\n")

        # Write events
        for event in family.events:
            self._write_event(f, event, level=1)

    def _write_event(self, f, event: Event, level: int) -> None:
        """Write an event to the GEDCOM file with multilingual place support.

        Args:
            f: File object
            event: Event object to write
            level: GEDCOM level for the event
        """
        f.write(f"{level} {event.type}\n")

        if event.date:
            f.write(f"{level + 1} DATE {event.date}\n")

        if event.place:
            self._write_place(f, event.place, level + 1)

        if event.notes:
            # Handle long notes (GEDCOM has line length limits)
            self._write_long_text(f, "NOTE", event.notes, level + 1)

        if 'TYPE' in event.attributes:
            f.write(f"{level + 1} TYPE {event.attributes['TYPE']}\n")

    def _write_place(self, f, place, level: int) -> None:
        """Write a place to the GEDCOM file with multilingual support.

        Args:
            f: File object
            place: Place object or string
            level: GEDCOM level for the place
        """
        # Handle backward compatibility with string places
        if isinstance(place, str):
            f.write(f"{level} PLAC {place}\n")
            return

        if not isinstance(place, Place):
            return

        # Write primary place name
        primary_name = place.get_name()
        if not primary_name:
            return

        f.write(f"{level} PLAC {primary_name}\n")

        # Write multilingual variations
        all_names = place.get_all_names()
        for lang_code, name in all_names.items():
            # Skip the primary language (already written)
            if lang_code == place.primary_language:
                continue

            # Write romanized or phonetic variations
            if lang_code == 'romn':
                f.write(f"{level + 1} ROMN {name}\n")
            elif lang_code == 'fone':
                f.write(f"{level + 1} FONE {name}\n")
            else:
                # Write as romanized with language tag
                f.write(f"{level + 1} ROMN {name}\n")
                f.write(f"{level + 2} LANG {lang_code}\n")

        # Write coordinates if available
        if place.has_coordinates():
            f.write(f"{level + 1} MAP\n")
            # Format coordinates in GEDCOM format (N/S for latitude, E/W for longitude)
            lat_str = self._format_coordinate(place.latitude, 'NS')
            lon_str = self._format_coordinate(place.longitude, 'EW')
            if lat_str:
                f.write(f"{level + 2} LATI {lat_str}\n")
            if lon_str:
                f.write(f"{level + 2} LONG {lon_str}\n")

    def _format_coordinate(self, coord: Optional[float], directions: str) -> Optional[str]:
        """Format a coordinate for GEDCOM output.

        Args:
            coord: Coordinate in decimal degrees
            directions: Two-character string for positive/negative (e.g., 'NS' or 'EW')

        Returns:
            Formatted coordinate string or None
        """
        if coord is None:
            return None

        # Determine direction
        if coord >= 0:
            direction = directions[0]
        else:
            direction = directions[1]
            coord = -coord

        return f"{direction}{coord}"

    def _write_long_text(self, f, tag: str, text: str, level: int,
                         max_length: int = 248) -> None:
        """Write long text with proper CONC/CONT handling.

        Args:
            f: File object
            tag: GEDCOM tag (e.g., 'NOTE')
            text: Text to write
            level: GEDCOM level
            max_length: Maximum line length
        """
        if len(text) <= max_length:
            f.write(f"{level} {tag} {text}\n")
        else:
            # Write first line
            f.write(f"{level} {tag} {text[:max_length]}\n")
            remaining = text[max_length:]

            # Write continuation lines
            while remaining:
                chunk = remaining[:max_length]
                f.write(f"{level + 1} CONC {chunk}\n")
                remaining = remaining[max_length:]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the loaded GEDCOM file.

        Returns:
            Dictionary containing statistics
        """
        stats = {
            'num_individuals': len(self.individuals),
            'num_families': len(self.families),
            'num_males': sum(1 for p in self.individuals.values() if p.sex == 'M'),
            'num_females': sum(1 for p in self.individuals.values() if p.sex == 'F'),
            'num_unknown_sex': sum(1 for p in self.individuals.values() if p.sex == 'U'),
        }

        # Calculate date range
        years = []
        for person in self.individuals.values():
            birth_year = person.get_birth_year()
            death_year = person.get_death_year()
            if birth_year:
                years.append(birth_year)
            if death_year:
                years.append(death_year)

        if years:
            stats['earliest_year'] = min(years)
            stats['latest_year'] = max(years)

        return stats


# Convenience functions
def load_gedcom(filepath: str) -> Tuple[Dict[str, Person], Dict[str, Family]]:
    """Load a GEDCOM file and return individuals and families.

    Args:
        filepath: Path to the GEDCOM file

    Returns:
        Tuple of (individuals dict, families dict)
    """
    parser = GedcomParser()
    return parser.load_gedcom(filepath)


def save_gedcom(filepath: str, individuals: Dict[str, Person],
                families: Dict[str, Family]) -> None:
    """Save individuals and families to a GEDCOM file.

    Args:
        filepath: Path where the GEDCOM file will be saved
        individuals: Dictionary of Person objects
        families: Dictionary of Family objects
    """
    parser = GedcomParser()
    parser.save_gedcom(filepath, individuals, families)
