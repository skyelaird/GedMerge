"""
RootsMagic Date Format Decoder and Multi-Language Date Support.

This module handles:
1. Decoding RootsMagic's proprietary 64-bit SortDate format
2. Converting non-English date modifiers to GEDCOM standard format
3. Normalizing various date representations to genealogical standards
"""

import re
from typing import Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class DateModifier(Enum):
    """Standard GEDCOM date modifiers."""
    EXACT = ""
    ABOUT = "ABT"
    ESTIMATED = "EST"
    CALCULATED = "CAL"
    BEFORE = "BEF"
    AFTER = "AFT"
    BETWEEN = "BET"  # Requires AND clause


@dataclass
class DecodedDate:
    """Represents a decoded date with optional modifier and range."""
    year: Optional[int] = None
    month: Optional[int] = None
    day: Optional[int] = None
    modifier: DateModifier = DateModifier.EXACT
    year2: Optional[int] = None  # For date ranges
    month2: Optional[int] = None
    day2: Optional[int] = None
    original_string: Optional[str] = None

    def to_gedcom(self) -> str:
        """Convert to GEDCOM date format."""
        if not self.year:
            return ""

        # Build date string
        parts = []
        if self.day:
            parts.append(str(self.day))
        if self.month:
            months = ['', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                     'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
            parts.append(months[self.month])
        parts.append(str(self.year))

        date1 = ' '.join(parts)

        # Handle range dates
        if self.modifier == DateModifier.BETWEEN and self.year2:
            parts2 = []
            if self.day2:
                parts2.append(str(self.day2))
            if self.month2:
                months = ['', 'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                         'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
                parts2.append(months[self.month2])
            parts2.append(str(self.year2))
            date2 = ' '.join(parts2)
            return f"BET {date1} AND {date2}"

        # Add modifier prefix
        if self.modifier != DateModifier.EXACT:
            return f"{self.modifier.value} {date1}"

        return date1

    def is_valid(self) -> bool:
        """Check if date components are valid."""
        if not self.year:
            return False
        if self.year < -10000 or self.year > 10000:
            return False
        if self.month and (self.month < 1 or self.month > 12):
            return False
        if self.day and (self.day < 1 or self.day > 31):
            return False
        return True


class RootsMagicDateDecoder:
    """Decoder for RootsMagic's proprietary SortDate format.

    RootsMagic uses a 64-bit integer to encode dates with modifiers.
    The format is position-coded starting from 10000 BC.

    Bit structure (bit 0 = LSB):
    - Bits 49-63 (15 bits): Year 1 + 10000
    - Bits 45-48 (4 bits): Month 1 (1-12)
    - Bits 39-44 (6 bits): Day 1 (1-31)
    - Bits 20-38 (19 bits): Year 2 + 10000 (for ranges)
    - Bits 16-19 (4 bits): Month 2
    - Bits 10-15 (6 bits): Day 2
    - Bits 0-9 (10 bits): Flags/modifiers

    Reference: https://sqlitetoolsforrootsmagic.com/Dates-SortDate-Algorithm/
    """

    # Special value for unknown/no date
    UNKNOWN_DATE = 9223372036854775807

    @classmethod
    def decode(cls, sort_date: int) -> DecodedDate:
        """Decode a RootsMagic SortDate value to a DecodedDate object.

        Args:
            sort_date: The 64-bit SortDate integer

        Returns:
            DecodedDate object with decoded components
        """
        if sort_date == cls.UNKNOWN_DATE:
            return DecodedDate(original_string="Unknown")

        # Extract components using bit operations
        # Y1 = (Ds>>49) - 10000
        year1 = (sort_date >> 49) - 10000

        # M1 = (Ds>>45) & 0xf
        month1 = (sort_date >> 45) & 0xf

        # D1 = (Ds>>39) & 0x3f
        day1 = (sort_date >> 39) & 0x3f

        # Y2 = (Ds>>20) & 0x3fff - 10000
        year2 = ((sort_date >> 20) & 0x3fff) - 10000

        # M2 = (Ds>>16) & 0xf
        month2 = (sort_date >> 16) & 0xf

        # D2 = (Ds>>10) & 0x3f
        day2 = (sort_date >> 10) & 0x3f

        # F = Ds & 0x3ff (flags)
        flags = sort_date & 0x3ff

        # Determine modifier from flags
        # Common flag values (based on observation):
        # 0x00C = exact date
        # 0x00D = about
        # 0x00E = before
        # 0x00F = after
        # 0x010 = between (with valid year2)

        modifier = DateModifier.EXACT
        if flags & 0x001:
            modifier = DateModifier.ABOUT
        elif flags & 0x002:
            modifier = DateModifier.BEFORE
        elif flags & 0x004:
            modifier = DateModifier.AFTER
        elif flags & 0x008 and year2 != -10000:
            modifier = DateModifier.BETWEEN

        # Clean up zero values
        if month1 == 0:
            month1 = None
        if day1 == 0:
            day1 = None
        if month2 == 0:
            month2 = None
        if day2 == 0:
            day2 = None
        if year2 == -10000 or year2 == year1:
            year2 = None

        return DecodedDate(
            year=year1 if year1 != -10000 else None,
            month=month1,
            day=day1,
            modifier=modifier,
            year2=year2,
            month2=month2,
            day2=day2
        )

    @classmethod
    def encode(cls, date: DecodedDate) -> int:
        """Encode a DecodedDate to RootsMagic SortDate format.

        Args:
            date: DecodedDate object to encode

        Returns:
            64-bit SortDate integer
        """
        if not date.year:
            return cls.UNKNOWN_DATE

        year1 = date.year + 10000
        month1 = date.month or 0
        day1 = date.day or 0

        # Handle year2 for ranges
        if date.year2:
            year2 = date.year2 + 10000
            month2 = date.month2 or 0
            day2 = date.day2 or 0
        else:
            # Default value when no second date
            year2 = 0
            month2 = 0
            day2 = 0

        # Determine flags from modifier
        flags = 0x00C  # Default: exact date
        if date.modifier == DateModifier.ABOUT or date.modifier == DateModifier.ESTIMATED:
            flags = 0x00D
        elif date.modifier == DateModifier.BEFORE:
            flags = 0x00E
        elif date.modifier == DateModifier.AFTER:
            flags = 0x00F
        elif date.modifier == DateModifier.BETWEEN:
            flags = 0x010

        # Encode using bit operations
        sort_date = (
            (year1 << 49) +
            (month1 << 45) +
            (day1 << 39) +
            (year2 << 20 if year2 else 17178820608) +  # Special value if no year2
            (month2 << 16) +
            (day2 << 10) +
            flags
        )

        return sort_date


class MultiLanguageDateParser:
    """Parser for date modifiers in multiple languages.

    Supports date modifiers from:
    - English
    - French
    - Spanish
    - Italian
    - German
    - Dutch
    - Portuguese
    - Latin
    """

    # Date modifier mappings from various languages to GEDCOM standard
    MODIFIERS = {
        # English (standard GEDCOM)
        'ABT': DateModifier.ABOUT,
        'ABOUT': DateModifier.ABOUT,
        'EST': DateModifier.ESTIMATED,
        'ESTIMATED': DateModifier.ESTIMATED,
        'CAL': DateModifier.CALCULATED,
        'CALCULATED': DateModifier.CALCULATED,
        'BEF': DateModifier.BEFORE,
        'BEFORE': DateModifier.BEFORE,
        'AFT': DateModifier.AFTER,
        'AFTER': DateModifier.AFTER,
        'BET': DateModifier.BETWEEN,
        'BETWEEN': DateModifier.BETWEEN,

        # French
        'VERS': DateModifier.ABOUT,
        'ENVIRON': DateModifier.ABOUT,
        'AVANT': DateModifier.BEFORE,
        'APRES': DateModifier.AFTER,
        'APRÈS': DateModifier.AFTER,
        'ENTRE': DateModifier.BETWEEN,

        # Spanish
        'HACIA': DateModifier.ABOUT,
        'CERCA': DateModifier.ABOUT,
        'ANTES': DateModifier.BEFORE,
        'DESPUES': DateModifier.AFTER,
        'DESPUÉS': DateModifier.AFTER,

        # Italian
        'CIRCA': DateModifier.ABOUT,
        'PRIMA': DateModifier.BEFORE,
        'DOPO': DateModifier.AFTER,
        'TRA': DateModifier.BETWEEN,

        # German
        'UM': DateModifier.ABOUT,
        'ETWA': DateModifier.ABOUT,
        'VOR': DateModifier.BEFORE,
        'NACH': DateModifier.AFTER,
        'ZWISCHEN': DateModifier.BETWEEN,

        # Dutch
        'OMSTREEKS': DateModifier.ABOUT,
        'VOOR': DateModifier.BEFORE,
        'NA': DateModifier.AFTER,
        'TUSSEN': DateModifier.BETWEEN,
        'TUM': DateModifier.BETWEEN,  # Abbreviation of TUSSEN

        # Portuguese
        'CERCA': DateModifier.ABOUT,
        'ANTES': DateModifier.BEFORE,
        'DEPOIS': DateModifier.AFTER,

        # Latin
        'CIRCA': DateModifier.ABOUT,
        'ANTE': DateModifier.BEFORE,
        'POST': DateModifier.AFTER,
    }

    # Month names in various languages
    MONTHS = {
        # English
        'JAN': 1, 'JANUARY': 1,
        'FEB': 2, 'FEBRUARY': 2,
        'MAR': 3, 'MARCH': 3,
        'APR': 4, 'APRIL': 4,
        'MAY': 5,
        'JUN': 6, 'JUNE': 6,
        'JUL': 7, 'JULY': 7,
        'AUG': 8, 'AUGUST': 8,
        'SEP': 9, 'SEPTEMBER': 9,
        'OCT': 10, 'OCTOBER': 10,
        'NOV': 11, 'NOVEMBER': 11,
        'DEC': 12, 'DECEMBER': 12,

        # French
        'JANVIER': 1, 'JANV': 1,
        'FEVRIER': 2, 'FÉVRIER': 2, 'FEVR': 2,
        'MARS': 3,
        'AVRIL': 4, 'AVR': 4,
        'MAI': 5,
        'JUIN': 6,
        'JUILLET': 7, 'JUIL': 7,
        'AOUT': 8, 'AOÛT': 8,
        'SEPTEMBRE': 9, 'SEPT': 9,
        'OCTOBRE': 10,
        'NOVEMBRE': 11,
        'DECEMBRE': 12, 'DÉCEMBRE': 12,

        # Spanish
        'ENERO': 1,
        'FEBRERO': 2,
        'MARZO': 3,
        'ABRIL': 4,
        'MAYO': 5,
        'JUNIO': 6,
        'JULIO': 7,
        'AGOSTO': 8,
        'SEPTIEMBRE': 9,
        'OCTUBRE': 10,
        'NOVIEMBRE': 11,
        'DICIEMBRE': 12,

        # Italian
        'GENNAIO': 1,
        'FEBBRAIO': 2,
        'MARZO': 3,
        'APRILE': 4,
        'MAGGIO': 5,
        'GIUGNO': 6,
        'LUGLIO': 7,
        'AGOSTO': 8,
        'SETTEMBRE': 9,
        'OTTOBRE': 10,
        'NOVEMBRE': 11,
        'DICEMBRE': 12,

        # German
        'JANUAR': 1,
        'FEBRUAR': 2,
        'MÄRZ': 3, 'MARZ': 3,
        'APRIL': 4,
        'MAI': 5,
        'JUNI': 6,
        'JULI': 7,
        'AUGUST': 8,
        'SEPTEMBER': 9,
        'OKTOBER': 10,
        'NOVEMBER': 11,
        'DEZEMBER': 12,
    }

    @classmethod
    def parse(cls, date_str: str) -> Optional[DecodedDate]:
        """Parse a date string with potential non-English modifiers.

        Args:
            date_str: Date string to parse (e.g., "Tum 0781", "Vers 1650")

        Returns:
            DecodedDate object or None if unparseable
        """
        if not date_str or not date_str.strip():
            return None

        original = date_str
        date_str = date_str.strip().upper()

        # Check for modifier prefix
        modifier = DateModifier.EXACT
        for mod_str, mod_enum in cls.MODIFIERS.items():
            if date_str.startswith(mod_str + ' '):
                modifier = mod_enum
                date_str = date_str[len(mod_str):].strip()
                break

        # Handle BETWEEN ... AND ... format
        if modifier == DateModifier.BETWEEN:
            and_match = re.search(r'\b(AND|ET|Y|E|UND|EN)\b', date_str, re.IGNORECASE)
            if and_match:
                date1_str = date_str[:and_match.start()].strip()
                date2_str = date_str[and_match.end():].strip()

                # Parse both dates
                date1 = cls._parse_single_date(date1_str)
                date2 = cls._parse_single_date(date2_str)

                if date1 and date2:
                    return DecodedDate(
                        year=date1[0],
                        month=date1[1],
                        day=date1[2],
                        modifier=modifier,
                        year2=date2[0],
                        month2=date2[1],
                        day2=date2[2],
                        original_string=original
                    )

        # Parse single date
        year, month, day = cls._parse_single_date(date_str)

        if year:
            return DecodedDate(
                year=year,
                month=month,
                day=day,
                modifier=modifier,
                original_string=original
            )

        return None

    @classmethod
    def _parse_single_date(cls, date_str: str) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        """Parse a single date component (no modifier).

        Returns:
            Tuple of (year, month, day)
        """
        date_str = date_str.strip().upper()

        # Try to extract year (4 digits or 3 digits for historical dates like 781)
        year_match = re.search(r'\b(\d{3,4})\b', date_str)
        year = int(year_match.group(1)) if year_match else None

        # Try to extract month
        month = None
        for month_str, month_num in cls.MONTHS.items():
            if month_str in date_str:
                month = month_num
                break

        # Try to extract day (1-2 digits)
        day_match = re.search(r'\b(\d{1,2})\b', date_str)
        day = None
        if day_match:
            potential_day = int(day_match.group(1))
            # Make sure it's not the year
            if potential_day <= 31 and (not year or potential_day != year):
                day = potential_day

        return (year, month, day)

    @classmethod
    def normalize_to_gedcom(cls, date_str: str) -> str:
        """Normalize a date string to GEDCOM format.

        Args:
            date_str: Date string in any supported language

        Returns:
            GEDCOM-formatted date string
        """
        decoded = cls.parse(date_str)
        if decoded:
            return decoded.to_gedcom()
        return date_str  # Return original if unparseable


def decode_rootsmagic_date(date_str: Optional[str], sort_date: Optional[int]) -> str:
    """Decode a RootsMagic date to human-readable GEDCOM format.

    This function handles both:
    1. Date strings that may have non-English modifiers
    2. SortDate integers that need decoding

    Args:
        date_str: The Date field from RootsMagic (may be empty or non-standard)
        sort_date: The SortDate field from RootsMagic (64-bit integer)

    Returns:
        Human-readable GEDCOM date string
    """
    # If we have a valid date string, try to parse and normalize it
    if date_str and date_str.strip():
        # Try multi-language parsing first
        decoded = MultiLanguageDateParser.parse(date_str)
        if decoded and decoded.is_valid():
            return decoded.to_gedcom()

        # If parsing failed but it looks like a reasonable date, return as-is
        if re.search(r'\d{3,4}', date_str):
            return date_str

    # Fall back to decoding SortDate if available
    if sort_date is not None and sort_date != RootsMagicDateDecoder.UNKNOWN_DATE:
        decoded = RootsMagicDateDecoder.decode(sort_date)
        if decoded.is_valid():
            return decoded.to_gedcom()

    # No valid date found
    return ""
