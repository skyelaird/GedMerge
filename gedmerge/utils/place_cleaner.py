"""Comprehensive place name cleaning utilities for genealogy data.

This module provides robust cleaning for place names, handling:
- All uppercase names
- Improper spacing and punctuation
- Blank pieces (empty hierarchy levels)
- Invalid characters
- Abbreviations
- Misplaced details (hierarchy issues)
- UK county 'shire' variations (Warwick vs Warwickshire)
- 'of' prefix removal (e.g., 'of Seavington Saint Michael')
- Postal codes

Follows RootsMagic PlaceClean function standards.
"""

import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass


@dataclass
class CleanedPlace:
    """Result of place cleaning operation."""
    original: str
    cleaned: str
    changes_made: List[str]
    warnings: List[str]
    postal_code: Optional[str] = None
    normalized_hierarchy: List[str] = None

    def __post_init__(self):
        if self.normalized_hierarchy is None:
            self.normalized_hierarchy = []


class PlaceCleaner:
    """Comprehensive place name cleaning utility."""

    # UK counties with optional 'shire' suffix
    UK_COUNTY_VARIATIONS = {
        'Warwick': 'Warwickshire',
        'Oxford': 'Oxfordshire',
        'Stafford': 'Staffordshire',
        'Lincoln': 'Lincolnshire',
        'Nottingham': 'Nottinghamshire',
        'Leicester': 'Leicestershire',
        'Worcester': 'Worcestershire',
        'Gloucester': 'Gloucestershire',
        'Derby': 'Derbyshire',
        'York': 'Yorkshire',
        'Lancaster': 'Lancashire',
        'Cheshire': 'Cheshire',  # Doesn't have a short form
        'Devon': 'Devonshire',
        'Hampshire': 'Hampshire',
        'Berkshire': 'Berkshire',
        'Kent': 'Kent',  # No shire
        'Essex': 'Essex',  # No shire
        'Sussex': 'Sussex',  # No shire (but East/West Sussex)
    }

    # Common abbreviations in place names
    PLACE_ABBREVIATIONS = {
        r'\bSt\b\.?': 'Saint',
        r'\bSt\.\s+': 'Saint ',
        r'\bMt\b\.?': 'Mount',
        r'\bFt\b\.?': 'Fort',
        r'\bN\b\.?(?=\s)': 'North',
        r'\bS\b\.?(?=\s)': 'South',
        r'\bE\b\.?(?=\s)': 'East',
        r'\bW\b\.?(?=\s)': 'West',
        r'\bCo\b\.?': 'County',
        r'\bTwp\b\.?': 'Township',
        r'\bVil\b\.?': 'Village',
        r'\bDept\b\.?': 'Department',
        r'\bProv\b\.?': 'Province',
    }

    # Postal code patterns
    POSTAL_CODE_PATTERNS = [
        r'\b([A-Z]\d[A-Z]\s?\d[A-Z]\d)\b',  # Canadian (e.g., K1A 0B1)
        r'\b(\d{5}(?:-\d{4})?)\b',  # US ZIP (e.g., 12345 or 12345-6789)
        r'\b([A-Z]{1,2}\d{1,2}\s?\d[A-Z]{2})\b',  # UK postal code
    ]

    # Invalid characters in place names
    INVALID_CHARS = r'[<>@#$%^&*()+=\[\]{}\\|;:`~]'

    # Problematic prefixes
    PROBLEMATIC_PREFIXES = ['of ', 'Of ', 'OF ']

    @classmethod
    def clean_place_name(cls, place_name: str, normalize_uk_counties: bool = True,
                        remove_postal_codes: bool = True,
                        expand_abbreviations: bool = True) -> CleanedPlace:
        """Clean a place name comprehensively.

        Args:
            place_name: The place name to clean
            normalize_uk_counties: Normalize UK county variations (Warwick -> Warwickshire)
            remove_postal_codes: Remove postal codes from place names
            expand_abbreviations: Expand common abbreviations (St -> Saint, etc.)

        Returns:
            CleanedPlace object with original, cleaned, and list of changes made
        """
        if not place_name or not place_name.strip():
            return CleanedPlace(
                original=place_name or '',
                cleaned='',
                changes_made=['Empty or blank place name'],
                warnings=[]
            )

        original = place_name
        cleaned = place_name
        changes = []
        warnings = []
        postal_code = None

        # Step 1: Remove postal codes
        if remove_postal_codes:
            cleaned, postal = cls._extract_and_remove_postal_code(cleaned)
            if postal:
                postal_code = postal
                changes.append(f'Removed postal code: {postal}')

        # Step 2: Remove 'of' prefix
        cleaned, removed_of = cls._remove_of_prefix(cleaned)
        if removed_of:
            changes.append("Removed 'of' prefix")

        # Step 3: Fix all uppercase
        if cleaned.isupper() and len(cleaned) > 3:
            cleaned = cls._smart_title_case_place(cleaned)
            changes.append('Converted from all uppercase')

        # Step 4: Expand abbreviations
        if expand_abbreviations:
            cleaned, abbrev_changes = cls._expand_abbreviations(cleaned)
            changes.extend(abbrev_changes)

        # Step 5: Fix spacing issues
        cleaned, spacing_changes = cls._fix_spacing(cleaned)
        changes.extend(spacing_changes)

        # Step 6: Fix punctuation issues
        cleaned, punct_changes = cls._fix_punctuation(cleaned)
        changes.extend(punct_changes)

        # Step 7: Remove invalid characters
        cleaned, invalid_changes = cls._remove_invalid_characters(cleaned)
        changes.extend(invalid_changes)

        # Step 8: Parse hierarchy and remove blank pieces
        hierarchy = cls._parse_hierarchy(cleaned)
        original_count = len(hierarchy)
        hierarchy = [piece for piece in hierarchy if piece.strip()]
        if len(hierarchy) < original_count:
            changes.append(f'Removed {original_count - len(hierarchy)} blank hierarchy pieces')

        # Step 9: Normalize UK counties if requested
        if normalize_uk_counties:
            hierarchy, county_changes = cls._normalize_uk_counties(hierarchy)
            changes.extend(county_changes)

        # Step 10: Check for misplaced details
        hierarchy, detail_warnings = cls._check_misplaced_details(hierarchy)
        warnings.extend(detail_warnings)

        # Rebuild the cleaned place name
        cleaned = ', '.join(hierarchy)

        # Final cleanup
        cleaned = cleaned.strip()

        return CleanedPlace(
            original=original,
            cleaned=cleaned,
            changes_made=changes if changes else ['No changes needed'],
            warnings=warnings,
            postal_code=postal_code,
            normalized_hierarchy=hierarchy
        )

    @classmethod
    def _extract_and_remove_postal_code(cls, text: str) -> Tuple[str, Optional[str]]:
        """Extract and remove postal code from text."""
        postal_code = None
        for pattern in cls.POSTAL_CODE_PATTERNS:
            match = re.search(pattern, text)
            if match:
                postal_code = match.group(1)
                # Remove the postal code and surrounding punctuation
                text = re.sub(r',?\s*' + pattern, '', text)
                break

        # Clean up extra commas and whitespace
        text = re.sub(r',\s*,', ',', text)
        text = re.sub(r',\s*$', '', text)
        text = re.sub(r'^\s*,', '', text)
        text = text.strip()

        return text, postal_code

    @classmethod
    def _remove_of_prefix(cls, text: str) -> Tuple[str, bool]:
        """Remove 'of' prefix from place name."""
        for prefix in cls.PROBLEMATIC_PREFIXES:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                return text, True
        return text, False

    @classmethod
    def _smart_title_case_place(cls, text: str) -> str:
        """Apply smart title casing for place names.

        Handles special cases like:
        - de, du, von, van (lowercase)
        - l', d' (lowercase with apostrophe)
        - Sur, Sous, Les, etc. (French)
        """
        if not text:
            return text

        words = text.split()
        result = []

        # Words that should stay lowercase (unless at start)
        lowercase_words = {
            'de', 'du', 'des', 'de la', 'de l\'',
            'von', 'vom', 'zu', 'zur', 'zum',
            'van', 'van de', 'van den', 'van der',
            'di', 'da', 'del', 'della',
            'sur', 'sous', 'les', 'le', 'la',
            'upon', 'on', 'in', 'at', 'the',
            'and', 'or',
        }

        for i, word in enumerate(words):
            # Check for apostrophe cases like "d'Angouleme"
            if "'" in word and len(word) > 2:
                parts = word.split("'")
                if len(parts) == 2 and parts[0].lower() in ['d', 'l']:
                    result.append(parts[0].lower() + "'" + parts[1].capitalize())
                    continue

            # First word is always capitalized
            if i == 0:
                result.append(word.capitalize())
            # Keep lowercase words lowercase
            elif word.lower() in lowercase_words:
                result.append(word.lower())
            else:
                result.append(word.capitalize())

        return ' '.join(result)

    @classmethod
    def _expand_abbreviations(cls, text: str) -> Tuple[str, List[str]]:
        """Expand common abbreviations in place names."""
        changes = []
        original = text

        for pattern, expansion in cls.PLACE_ABBREVIATIONS.items():
            new_text = re.sub(pattern, expansion, text)
            if new_text != text:
                changes.append(f'Expanded abbreviation: {pattern} -> {expansion}')
                text = new_text

        return text, changes

    @classmethod
    def _fix_spacing(cls, text: str) -> Tuple[str, List[str]]:
        """Fix spacing issues in place names."""
        changes = []
        original = text

        # Fix multiple spaces
        new_text = re.sub(r'\s{2,}', ' ', text)
        if new_text != text:
            changes.append('Fixed multiple spaces')
            text = new_text

        # Fix space before comma
        new_text = re.sub(r'\s+,', ',', text)
        if new_text != text:
            changes.append('Removed space before comma')
            text = new_text

        # Fix missing space after comma
        new_text = re.sub(r',([^\s])', r', \1', text)
        if new_text != text:
            changes.append('Added space after comma')
            text = new_text

        # Trim whitespace
        text = text.strip()

        return text, changes

    @classmethod
    def _fix_punctuation(cls, text: str) -> Tuple[str, List[str]]:
        """Fix punctuation issues in place names."""
        changes = []

        # Remove multiple commas
        new_text = re.sub(r',{2,}', ',', text)
        if new_text != text:
            changes.append('Fixed multiple commas')
            text = new_text

        # Remove leading/trailing commas
        new_text = text.strip(',').strip()
        if new_text != text:
            changes.append('Removed leading/trailing commas')
            text = new_text

        return text, changes

    @classmethod
    def _remove_invalid_characters(cls, text: str) -> Tuple[str, List[str]]:
        """Remove invalid characters from place names."""
        changes = []

        # Find invalid characters
        invalid_found = re.findall(cls.INVALID_CHARS, text)
        if invalid_found:
            unique_invalid = set(invalid_found)
            changes.append(f'Removed invalid characters: {", ".join(unique_invalid)}')

        # Remove invalid characters
        text = re.sub(cls.INVALID_CHARS, '', text)

        return text, changes

    @classmethod
    def _parse_hierarchy(cls, text: str) -> List[str]:
        """Parse place hierarchy (split by commas)."""
        if not text:
            return []

        pieces = [piece.strip() for piece in text.split(',')]
        return pieces

    @classmethod
    def _normalize_uk_counties(cls, hierarchy: List[str]) -> Tuple[List[str], List[str]]:
        """Normalize UK county names (Warwick -> Warwickshire).

        Args:
            hierarchy: List of place hierarchy pieces

        Returns:
            Tuple of (normalized_hierarchy, changes_made)
        """
        changes = []
        normalized = []

        for piece in hierarchy:
            # Check if this piece matches a UK county short form
            normalized_piece = piece
            for short_form, long_form in cls.UK_COUNTY_VARIATIONS.items():
                # Exact match (case insensitive)
                if piece.lower() == short_form.lower():
                    normalized_piece = long_form
                    if piece != long_form:
                        changes.append(f'Normalized UK county: {piece} -> {long_form}')
                    break

            normalized.append(normalized_piece)

        return normalized, changes

    @classmethod
    def _check_misplaced_details(cls, hierarchy: List[str]) -> Tuple[List[str], List[str]]:
        """Check for misplaced details in hierarchy.

        For example, a cathedral name should be a separate place detail,
        not mixed with the city name.
        """
        warnings = []

        # Check for details that should be separate places
        detail_indicators = [
            'Cathedral', 'Church', 'Chapel', 'Abbey', 'Monastery',
            'Hospital', 'School', 'University', 'Cemetery',
            'Castle', 'Palace', 'Fort', 'Manor',
        ]

        for i, piece in enumerate(hierarchy):
            for indicator in detail_indicators:
                if indicator.lower() in piece.lower() and len(hierarchy) > 1:
                    # Check if it's in a mixed format like "Canterbury Cathedral, Kent"
                    # vs proper format "Canterbury Cathedral" -> child of "Canterbury"
                    if i == 0:  # First piece
                        warnings.append(
                            f'Place detail "{piece}" may need separate hierarchy: '
                            f'create "{piece}" as child of parent location'
                        )
                    break

        return hierarchy, warnings

    @classmethod
    def find_duplicate_places(cls, places: List[Tuple[int, str]],
                             normalize_uk_counties: bool = True) -> Dict[str, List[int]]:
        """Find duplicate places after normalization.

        Args:
            places: List of (place_id, place_name) tuples
            normalize_uk_counties: Whether to normalize UK counties when comparing

        Returns:
            Dictionary mapping normalized place names to list of place IDs
        """
        normalized_to_ids = {}

        for place_id, place_name in places:
            cleaned = cls.clean_place_name(
                place_name,
                normalize_uk_counties=normalize_uk_counties,
                remove_postal_codes=True,
                expand_abbreviations=True
            )

            normalized_name = cleaned.cleaned.lower().strip()

            if normalized_name not in normalized_to_ids:
                normalized_to_ids[normalized_name] = []

            normalized_to_ids[normalized_name].append(place_id)

        # Return only duplicates (2+ place IDs)
        duplicates = {name: ids for name, ids in normalized_to_ids.items() if len(ids) > 1}

        return duplicates

    @classmethod
    def suggest_merge_candidates(cls, place_name1: str, place_name2: str) -> Tuple[bool, float, str]:
        """Suggest whether two places should be merged.

        Args:
            place_name1: First place name
            place_name2: Second place name

        Returns:
            Tuple of (should_merge, confidence, reason)
        """
        clean1 = cls.clean_place_name(place_name1)
        clean2 = cls.clean_place_name(place_name2)

        # Exact match after cleaning
        if clean1.cleaned.lower() == clean2.cleaned.lower():
            return True, 1.0, "Exact match after normalization"

        # Check hierarchy similarity
        h1 = set(clean1.normalized_hierarchy)
        h2 = set(clean2.normalized_hierarchy)

        if h1 == h2:
            return True, 1.0, "Same hierarchy after normalization"

        # Check if one is subset of another (e.g., "Cambridge, England" vs "Cambridge, Middlesex, England")
        if h1.issubset(h2) or h2.issubset(h1):
            return True, 0.9, "One place is more specific than the other"

        # Check for UK county variations
        # e.g., "Burton Dassett, Warwick, England" vs "Burton Dassett, Warwickshire, England"
        if len(h1) == len(h2):
            differences = 0
            uk_county_diff = False

            for p1, p2 in zip(clean1.normalized_hierarchy, clean2.normalized_hierarchy):
                if p1.lower() != p2.lower():
                    differences += 1
                    # Check if this is a UK county variation
                    for short, long in cls.UK_COUNTY_VARIATIONS.items():
                        if (p1.lower() == short.lower() and p2.lower() == long.lower()) or \
                           (p2.lower() == short.lower() and p1.lower() == long.lower()):
                            uk_county_diff = True
                            break

            if differences == 1 and uk_county_diff:
                return True, 0.95, "UK county variation (Warwick/Warwickshire)"

        return False, 0.0, "No clear match"
