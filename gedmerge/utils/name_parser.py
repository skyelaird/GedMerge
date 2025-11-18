"""Comprehensive name parsing utilities for genealogy data.

This module provides robust parsing for NAME, GIVN, SURN, NICK, and other name fields,
handling complex cases like:
- Ordinals and epithets in given names (Thomas II 'The Wise')
- Nobility titles as suffixes (1st Baron, Duke of York)
- Noble surname patterns (von Franconia, de France, van der Berg)
- Honorific prefixes (Frau, Herr, Sir, Lady, etc.)
- Quoted nicknames and epithets
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass(slots=True)
class ParsedName:
    """Represents a fully parsed name with all components."""
    given: Optional[str] = None
    surname: Optional[str] = None
    prefix: Optional[str] = None
    suffix: Optional[str] = None
    nickname: Optional[str] = None

    # Additional parsing metadata
    ordinal: Optional[str] = None  # Roman numerals like II, III
    epithets: List[str] = None  # Quoted epithets like 'The Wise'

    def __post_init__(self):
        if self.epithets is None:
            self.epithets = []


class NameParser:
    """Parser for complex genealogical name fields."""

    # Honorific prefixes by language
    # Note: 'M' for French is handled specially - it can be 'Monsieur' OR 'Marie' for females
    PREFIXES = {
        'English': ['Sir', 'Lady', 'Lord', 'Dame', 'Mr', 'Mrs', 'Miss', 'Ms',
                   'Dr', 'Rev', 'Revd', 'Father', 'Mother'],
        'French': ['M', 'Mme', 'Mlle', 'Sieur', 'Dame', 'Messire'],
        'German': ['Herr', 'Frau', 'Fräulein', 'Freiherr', 'Freiin'],
        'Spanish': ['Sr', 'Sra', 'Srta', 'Don', 'Doña', 'Señor', 'Señora'],
        'Italian': ['Sig', 'Sig.ra', 'Sig.na', 'Signore', 'Signora', 'Donna'],
        'Dutch': ['Heer', 'Mevrouw', 'Juffrouw'],
        'Portuguese': ['Sr', 'Sra', 'Srta', 'Senhor', 'Senhora', 'Dom', 'Dona']
    }

    # Titles that should be treated as suffixes (nobility titles, etc.)
    # These were previously incorrectly classified as prefixes
    TITLE_SUFFIXES = {
        'French': ['Seigneur', 'Seigneure'],
        'English': [],
        'German': [],
    }

    # Flatten prefix list for easy matching
    ALL_PREFIXES = []
    for prefixes in PREFIXES.values():
        ALL_PREFIXES.extend(prefixes)

    # Flatten title suffix list for easy matching
    ALL_TITLE_SUFFIXES = []
    for suffixes in TITLE_SUFFIXES.values():
        ALL_TITLE_SUFFIXES.extend(suffixes)

    # Noble surname particles that indicate surnames, NOT nicknames
    SURNAME_PARTICLES = [
        # German
        'von', 'vom', 'zu', 'zur', 'zum', 'im', 'am',
        # French
        'de', 'du', 'des', 'd\'', 'de la', 'de l\'', 'du',
        # Dutch
        'van', 'van de', 'van den', 'van der', 'van het', 'ter', 'te', 'ten',
        # Italian
        'di', 'da', 'del', 'della', 'degli', 'delle',
        # Spanish/Portuguese
        'del', 'de la', 'de los', 'de las', 'dos', 'das',
        # Irish/Scottish
        'mac', 'mc', 'o\'',
        # Other
        'af', 'av', 'von und zu'
    ]

    # Ordinal patterns (Roman numerals and text ordinals)
    ORDINAL_PATTERN = re.compile(r'\b([IVX]+)\b$')
    # Also match text ordinals like "the First", "the Second", etc.
    TEXT_ORDINAL_PATTERN = re.compile(
        r'\b(?:the\s+)?(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|'
        r'Eleventh|Twelfth|Thirteenth|Fourteenth|Fifteenth)\b',
        re.IGNORECASE
    )

    # Quoted epithet patterns (nicknames in quotes)
    QUOTED_EPITHET_PATTERN = re.compile(r'''['"]([^'"]+)['"]''')

    # Nobility suffix patterns
    NOBILITY_SUFFIX_PATTERNS = [
        # English ordinal titles
        r'\b(\d+(?:st|nd|rd|th)\s+(?:Earl|Baron|Baroness|Lord|Duke|Duchess|Count|Countess)(?:\s+[Oo]f\s+\w+)?)\b',
        # Other English titles
        r'\b(Earl|Baron|Baroness|Lord|Duke|Duchess|Count|Countess|Marquess|Marchioness|Viscount|Viscountess)(?:\s+[Oo]f\s+\w+)?\b',
        # Heiress/Heir of X
        r'\b((?:Heir|Heiress)\s+[Oo]f\s+\w+)\b',
        # German titles
        r'\b(Graf|Herzog|Fürst|Baron)(?:\s+(?:von|im|zu)\s+\w+)?\b',
        # French titles
        r'\b(Comte|Duc|Marquis|Baron)(?:\s+d[e\']\s*\w+)?\b',
    ]

    # Compile nobility patterns
    COMPILED_NOBILITY_PATTERNS = [re.compile(p, re.IGNORECASE) for p in NOBILITY_SUFFIX_PATTERNS]

    @classmethod
    def is_surname_particle(cls, word: str) -> bool:
        """Check if a word is a noble surname particle (von, de, van, etc.)."""
        word_lower = word.lower()
        # Remove trailing apostrophes for matching
        word_normalized = word_lower.rstrip("'")
        return word_normalized in cls.SURNAME_PARTICLES or word_lower in cls.SURNAME_PARTICLES

    @classmethod
    def is_prefix(cls, word: str) -> bool:
        """Check if a word is an honorific prefix."""
        word_clean = word.rstrip('.')
        return word_clean in cls.ALL_PREFIXES or word_clean.lower().capitalize() in cls.ALL_PREFIXES

    @classmethod
    def is_title_suffix(cls, word: str) -> bool:
        """Check if a word is a title that should be treated as a suffix."""
        word_clean = word.rstrip('.')
        return word_clean in cls.ALL_TITLE_SUFFIXES or word_clean.lower().capitalize() in cls.ALL_TITLE_SUFFIXES

    @classmethod
    def extract_quoted_epithets(cls, text: str) -> Tuple[str, List[str]]:
        """Extract quoted epithets from text and return cleaned text and list of epithets.

        Args:
            text: Text potentially containing quoted epithets

        Returns:
            Tuple of (cleaned_text, list_of_epithets)
        """
        epithets = cls.QUOTED_EPITHET_PATTERN.findall(text)
        cleaned = cls.QUOTED_EPITHET_PATTERN.sub('', text).strip()
        # Clean up multiple spaces
        cleaned = re.sub(r'\s+', ' ', cleaned)
        return cleaned, epithets

    @classmethod
    def extract_ordinal(cls, text: str) -> Tuple[str, Optional[str]]:
        """Extract Roman numeral or text ordinal from end of text.

        Args:
            text: Text potentially ending with ordinal (e.g., "Thomas II" or "Thomas the First")

        Returns:
            Tuple of (text_without_ordinal, ordinal)
        """
        # First try Roman numerals
        match = cls.ORDINAL_PATTERN.search(text)
        if match:
            ordinal = match.group(1)
            # Remove ordinal from text
            text_without = text[:match.start()].strip()
            return text_without, ordinal

        # Try text ordinals
        match = cls.TEXT_ORDINAL_PATTERN.search(text)
        if match:
            ordinal = match.group(0)  # Get full match including "the" if present
            # Remove ordinal from text
            text_without = text[:match.start()] + text[match.end():]
            text_without = re.sub(r'\s+', ' ', text_without).strip()
            return text_without, ordinal

        return text, None

    @classmethod
    def extract_nobility_suffix(cls, text: str) -> Tuple[str, Optional[str]]:
        """Extract nobility title suffix from text.

        Args:
            text: Text potentially containing nobility suffix

        Returns:
            Tuple of (text_without_suffix, suffix)
        """
        for pattern in cls.COMPILED_NOBILITY_PATTERNS:
            match = pattern.search(text)
            if match:
                suffix = match.group(0)
                # Remove suffix from text
                text_without = text[:match.start()] + text[match.end():]
                text_without = re.sub(r'\s+', ' ', text_without).strip()
                return text_without, suffix
        return text, None

    @classmethod
    def extract_prefix(cls, text: str, sex: Optional[str] = None) -> Tuple[str, Optional[str]]:
        """Extract honorific prefix from beginning of text.

        Special handling for French 'M.' - if sex is 'F' (female), 'M.' is expanded
        to 'Marie' as part of the given name, not treated as a prefix.

        Args:
            text: Text potentially starting with prefix
            sex: Optional sex indicator ('M', 'F', 'U') for context-aware parsing

        Returns:
            Tuple of (text_without_prefix, prefix)
        """
        words = text.split()
        if not words:
            return text, None

        first_word = words[0].rstrip('.')

        # Special case: French 'M' or 'M.' for female names = Marie
        if sex == 'F' and first_word.upper() == 'M':
            # Replace M. with Marie in the given name
            remaining_words = words[1:]
            expanded = 'Marie ' + ' '.join(remaining_words)
            return expanded, None

        if cls.is_prefix(first_word):
            prefix = words[0]  # Keep original with punctuation
            remaining = ' '.join(words[1:])
            return remaining, prefix

        return text, None

    @classmethod
    def extract_title_suffix(cls, text: str) -> Tuple[str, Optional[str]]:
        """Extract title suffixes like 'Seigneur' that appear in the name.

        This handles titles like 'Seigneur d'Amboise et Chaumont' where 'Seigneur'
        should be moved to the suffix field.

        Args:
            text: Text potentially containing title suffix

        Returns:
            Tuple of (text_without_title, title_suffix)
        """
        words = text.split()
        for i, word in enumerate(words):
            if cls.is_title_suffix(word):
                # Everything from this word onward is the suffix
                title_suffix = ' '.join(words[i:])
                remaining = ' '.join(words[:i]).strip() if i > 0 else ''
                return remaining, title_suffix

        return text, None

    @classmethod
    def has_surname_particle(cls, text: str) -> bool:
        """Check if text contains a surname particle anywhere."""
        if not text:
            return False
        words = text.split()
        return any(cls.is_surname_particle(word) for word in words)

    @classmethod
    def extract_surname_with_particle(cls, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract surname from text that may contain surname particles.

        This is useful for parsing fields that mix given names and surnames.

        Args:
            text: Text potentially containing "Given von Surname" pattern

        Returns:
            Tuple of (remaining_text, surname_with_particle)
        """
        if not text:
            return None, None

        words = text.split()

        # Find first surname particle
        for i, word in enumerate(words):
            if cls.is_surname_particle(word):
                # Everything from this particle onward is the surname
                surname = ' '.join(words[i:])
                remaining = ' '.join(words[:i]).strip() if i > 0 else None
                return remaining, surname

        return text, None

    @classmethod
    def _title_case_single_part(cls, part: str) -> str:
        """Title case a single part, handling apostrophes for particles like d', l'.

        Args:
            part: A single word part (no spaces or hyphens)

        Returns:
            Title-cased part
        """
        if not part:
            return part

        # Check for particles with apostrophes like "d'Angouleme", "l'Eveque"
        if "'" in part:
            # Split on apostrophe
            apos_parts = part.split("'")
            if len(apos_parts) == 2:
                prefix_part, suffix_part = apos_parts
                # Check if prefix is a particle (d, l, etc.)
                if prefix_part.lower() in ["d", "l"]:
                    # Return as "d'Suffix" or "l'Suffix"
                    return prefix_part.lower() + "'" + suffix_part.capitalize()

        # Check if this is a surname particle
        if cls.is_surname_particle(part):
            return part.lower()

        # Check for particles with apostrophes like "d'", "l'" (just the particle)
        if part.lower() in ["d'", "l'"]:
            return part.lower()

        # Regular title case
        return part.capitalize()

    @classmethod
    def smart_title_case(cls, text: str) -> str:
        """Apply smart title casing that respects name particles and conventions.

        This handles ALLCAPS names and converts them properly, keeping particles
        lowercase where appropriate (de, von, van, etc.).

        Args:
            text: Text to title case (may be ALLCAPS)

        Returns:
            Properly title-cased text

        Examples:
            "DE CHANAC DE TURENNE-D'ANGOULEME" -> "de Chanac de Turenne-d'Angouleme"
            "GEOFFROI DE LIMOGES" -> "Geoffroi de Limoges"
        """
        if not text:
            return text

        # Check if text is all uppercase (likely needs fixing)
        if text.isupper():
            # First pass: split on spaces only
            words = text.split()
            result_words = []

            for word in words:
                # Check if word contains hyphens
                if '-' in word:
                    # Split on hyphens, preserving the hyphen
                    hyphen_parts = word.split('-')
                    result_parts = []

                    for part in hyphen_parts:
                        result_parts.append(cls._title_case_single_part(part))

                    result_words.append('-'.join(result_parts))
                else:
                    # No hyphens, process normally
                    result_words.append(cls._title_case_single_part(word))

            return ' '.join(result_words)

        # If not all caps, return as-is
        return text

    @classmethod
    def parse_tagged_name_field(cls, name_value: str) -> ParsedName:
        """Parse a name field with [GIVN] and [Surname] tags.

        Some genealogy data includes inline tags to mark which parts are
        given names vs surnames.

        Example:
            "Geoffroi 'Bocourt' [GIVN] de Limoges Vicomte de Limoges [Surname]"
            -> given: "Geoffroi", nickname: "Bocourt",
               surname: "de Limoges Vicomte de Limoges"

        Args:
            name_value: Name with [GIVN] and/or [Surname] tags

        Returns:
            ParsedName object with extracted components
        """
        result = ParsedName()
        text = name_value.strip()

        if not text:
            return result

        # Extract parts marked as [GIVN]
        givn_match = re.search(r'(.*?)\s*\[GIVN\]', text, re.IGNORECASE)
        givn_text = ""
        if givn_match:
            givn_text = givn_match.group(1).strip()
            # Remove this part from text
            text = text[givn_match.end():].strip()

        # Extract parts marked as [Surname] or [SURN]
        surn_match = re.search(r'(.*?)\s*\[(?:Surname|SURN)\]', text, re.IGNORECASE)
        surn_text = ""
        if surn_match:
            surn_text = surn_match.group(1).strip()
            # Remove this part from text
            text = text[surn_match.end():].strip()

        # Parse the given name part
        if givn_text:
            # Apply smart title casing if needed
            givn_text = cls.smart_title_case(givn_text)
            givn_parsed = cls.parse_givn_field(givn_text)
            result.given = givn_parsed.given
            result.ordinal = givn_parsed.ordinal
            result.nickname = givn_parsed.nickname
            result.epithets = givn_parsed.epithets
            result.prefix = givn_parsed.prefix
            result.suffix = givn_parsed.suffix

        # Parse the surname part (may contain titles or particles)
        if surn_text:
            # Apply smart title casing if needed
            surn_text = cls.smart_title_case(surn_text)
            result.surname = surn_text

        # Any remaining text should be analyzed
        if text:
            # Could be additional suffix or other components
            text, suffix = cls.extract_nobility_suffix(text)
            if suffix:
                result.suffix = result.suffix + " " + suffix if result.suffix else suffix

        return result

    @classmethod
    def parse_givn_field(cls, givn_value: str, sex: Optional[str] = None) -> ParsedName:
        """Parse a GIVN field that may contain ordinals, epithets, and titles.

        Example inputs:
            "Thomas II 'The Wise' 1st Baron" ->
                given: "Thomas II"
                nickname: "The Wise"
                suffix: "1st Baron"
                ordinal: "II"
            "M. Anne" (sex='F') ->
                given: "Marie Anne"

        Args:
            givn_value: Value from GIVN field
            sex: Optional sex indicator ('M', 'F', 'U') for context-aware parsing

        Returns:
            ParsedName object with extracted components
        """
        result = ParsedName()
        text = givn_value.strip()

        if not text:
            return result

        # Step 0: Handle M. -> Marie for female names
        text, prefix = cls.extract_prefix(text, sex=sex)
        if prefix:
            result.prefix = prefix

        # Step 1: Extract quoted epithets (these become nicknames)
        text, epithets = cls.extract_quoted_epithets(text)
        result.epithets = epithets
        if epithets:
            result.nickname = epithets[0]  # Use first epithet as primary nickname

        # Step 2: Extract title suffixes (like "Seigneur")
        text, title_suffix = cls.extract_title_suffix(text)
        if title_suffix:
            result.suffix = title_suffix

        # Step 3: Extract nobility suffix
        if not result.suffix:  # Only if we didn't already find a title suffix
            text, suffix = cls.extract_nobility_suffix(text)
            if suffix:
                result.suffix = suffix

        # Step 4: Extract ordinal (if present, keep it with given name)
        text_without_ordinal, ordinal = cls.extract_ordinal(text)
        if ordinal:
            result.ordinal = ordinal
            result.given = text  # Keep ordinal with given name "Thomas II"
        else:
            result.given = text

        return result

    @classmethod
    def parse_name_field(cls, name_value: str, sex: Optional[str] = None) -> ParsedName:
        """Parse a full NAME field in GEDCOM format.

        GEDCOM NAME format: "Given /Surname/ Suffix"
        But may also contain prefixes, epithets, etc.

        Example inputs:
            "Thomas II /Smith/" -> given: "Thomas II", surname: "Smith"
            "Sir Thomas /Smith/ 1st Baron" -> prefix: "Sir", given: "Thomas",
                                               surname: "Smith", suffix: "1st Baron"
            "Frau Gerberga /von Franconia/" -> prefix: "Frau", given: "Gerberga",
                                                surname: "von Franconia"
            "M. Anne /de Bréval/" (sex='F') -> given: "Marie Anne", surname: "de Bréval"

        Args:
            name_value: Value from NAME field
            sex: Optional sex indicator ('M', 'F', 'U') for context-aware parsing

        Returns:
            ParsedName object with extracted components
        """
        result = ParsedName()
        text = name_value.strip()

        if not text:
            return result

        # Extract surname from /Surname/ format
        surname_match = re.search(r'/([^/]*)/', text)
        if surname_match:
            result.surname = surname_match.group(1).strip()
            # Remove surname from text
            text = text[:surname_match.start()] + text[surname_match.end():]
            text = text.strip()

        # What remains is given name and possibly prefix/suffix
        if not text:
            return result

        # Extract prefix from beginning (handles M. -> Marie for females)
        text, prefix = cls.extract_prefix(text, sex=sex)
        if prefix:
            result.prefix = prefix

        # Extract quoted epithets
        text, epithets = cls.extract_quoted_epithets(text)
        result.epithets = epithets
        if epithets:
            result.nickname = epithets[0]

        # Extract title suffixes (like "Seigneur")
        text, title_suffix = cls.extract_title_suffix(text)
        if title_suffix:
            result.suffix = title_suffix

        # Extract nobility suffix
        if not result.suffix:  # Only if we didn't already find a title suffix
            text, suffix = cls.extract_nobility_suffix(text)
            if suffix:
                result.suffix = suffix

        # What remains is the given name (possibly with ordinal)
        text_without_ordinal, ordinal = cls.extract_ordinal(text)
        if ordinal:
            result.ordinal = ordinal
            result.given = text  # Keep ordinal with given name
        else:
            result.given = text if text else None

        return result

    @classmethod
    def parse_field_with_surname_particle(cls, field_value: str, field_type: str = 'UNKNOWN', sex: Optional[str] = None) -> ParsedName:
        """Parse a field that incorrectly contains surname particles.

        This handles cases where a field tagged as NICK or GIVN actually contains
        a surname with particles like "von Franconia" or "de France".

        Example:
            "Frau Gerberga von Franconia" (tagged as NICK) ->
                prefix: "Frau"
                given: "Gerberga"
                surname: "von Franconia"

        Args:
            field_value: The field value
            field_type: Type hint (NICK, GIVN, etc.) for better parsing
            sex: Optional sex indicator ('M', 'F', 'U') for context-aware parsing

        Returns:
            ParsedName object with corrected components
        """
        result = ParsedName()
        text = field_value.strip()

        if not text:
            return result

        # Extract prefix first (handles M. -> Marie for females)
        text, prefix = cls.extract_prefix(text, sex=sex)
        if prefix:
            result.prefix = prefix

        # Extract quoted epithets
        text, epithets = cls.extract_quoted_epithets(text)
        result.epithets = epithets

        # Extract title suffixes (like "Seigneur d'Amboise")
        text, title_suffix = cls.extract_title_suffix(text)
        if title_suffix:
            result.suffix = title_suffix

        # Check for surname particle
        remaining, surname = cls.extract_surname_with_particle(text)
        if surname:
            result.surname = surname
            if remaining:
                result.given = remaining
        else:
            # No surname particle found, treat as given name
            result.given = text if text else None

        return result

    @classmethod
    def normalize_name_components(cls, given: Optional[str] = None,
                                  surname: Optional[str] = None,
                                  prefix: Optional[str] = None,
                                  suffix: Optional[str] = None,
                                  nickname: Optional[str] = None,
                                  sex: Optional[str] = None) -> ParsedName:
        """Normalize and validate name components, applying parsing rules.

        This method takes individual name components and applies parsing rules to
        ensure they are in the correct fields. For example, if 'given' contains
        surname particles, it will extract them.

        Args:
            given: Given name value
            surname: Surname value
            prefix: Prefix value
            suffix: Suffix value
            nickname: Nickname value
            sex: Optional sex indicator ('M', 'F', 'U') for context-aware parsing

        Returns:
            ParsedName object with normalized components
        """
        result = ParsedName()

        # Process given name for embedded components
        if given:
            given_parsed = cls.parse_givn_field(given, sex=sex)
            result.given = given_parsed.given
            result.ordinal = given_parsed.ordinal
            if not nickname and given_parsed.nickname:
                result.nickname = given_parsed.nickname
            if not suffix and given_parsed.suffix:
                result.suffix = given_parsed.suffix
            if not prefix and given_parsed.prefix:
                result.prefix = given_parsed.prefix

        # Process nickname for embedded surname particles
        if nickname and cls.has_surname_particle(nickname):
            nick_parsed = cls.parse_field_with_surname_particle(nickname, 'NICK', sex=sex)
            # If it contains surname particles, it's misclassified
            if nick_parsed.surname and not surname:
                result.surname = nick_parsed.surname
                if nick_parsed.given and not result.given:
                    result.given = nick_parsed.given
                if nick_parsed.prefix and not prefix:
                    result.prefix = nick_parsed.prefix
                # Don't use this as a nickname
                nickname = None

        # Set remaining components
        result.surname = result.surname or surname
        result.prefix = result.prefix or prefix
        result.suffix = result.suffix or suffix
        result.nickname = result.nickname or nickname

        return result
