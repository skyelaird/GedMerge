"""Comprehensive name cleaning utilities for genealogy data.

This module provides robust cleaning for person names, handling:
- Names in uppercase
- Improper spacing
- Improper punctuation
- Misplaced prefixes/suffixes/nicknames
- Alternate names within a name
- Invalid characters
- Abbreviations
- Descriptions rather than names
- Wife shares husband's surname (detecting and flagging)
- Capitalization
- French 'feu' (deceased) removal

Follows RootsMagic NameClean function standards.
"""

import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass
from ..utils.name_parser import NameParser, ParsedName


@dataclass
class CleanedName:
    """Result of name cleaning operation."""
    original_given: Optional[str]
    original_surname: Optional[str]
    original_prefix: Optional[str]
    original_suffix: Optional[str]
    original_nickname: Optional[str]

    cleaned_given: Optional[str]
    cleaned_surname: Optional[str]
    cleaned_prefix: Optional[str]
    cleaned_suffix: Optional[str]
    cleaned_nickname: Optional[str]

    changes_made: List[str]
    warnings: List[str]


class NameCleaner:
    """Comprehensive name cleaning utility."""

    # Invalid characters in names
    INVALID_CHARS = r'[<>@#$%^&*+=\[\]{}\\|;:`~]'

    # Description patterns that indicate a description rather than a name
    DESCRIPTION_PATTERNS = [
        r'\bunknown\b',
        r'\bunnamed\b',
        r'\bno name\b',
        r'\bname unknown\b',
        r'\bnot known\b',
        r'\bunidentified\b',
        r'\bmissing\b',
        r'\bdeceased\b',
        r'\bfeu\b',  # French for deceased
        r'\bfeue\b',  # French for deceased (feminine)
        r'\blate\b',  # "the late John Smith"
        r'\bdied\b',
        r'\bborn\b',
        r'\bmarried\b',
        r'\bdivorced\b',
        r'\bwidow\b',
        r'\bwidower\b',
    ]

    # French 'feu' patterns (deceased)
    FEU_PATTERNS = [
        r'\bfeu\s+',
        r'\bfeue\s+',
        r'\bFeu\s+',
        r'\bFeue\s+',
        r'\bFEU\s+',
        r'\bFEUE\s+',
    ]

    # Problematic patterns in names (alternate names within a name)
    ALTERNATE_NAME_PATTERNS = [
        r'\(.*?\)',  # Names in parentheses
        r'\balias\s+',
        r'\ba\.k\.a\.\s+',
        r'\balso\s+known\s+as\s+',
        r'\bor\s+\b',  # "John or Jean"
    ]

    @classmethod
    def clean_name_components(cls, given: Optional[str] = None,
                             surname: Optional[str] = None,
                             prefix: Optional[str] = None,
                             suffix: Optional[str] = None,
                             nickname: Optional[str] = None,
                             sex: Optional[str] = None) -> CleanedName:
        """Clean all name components comprehensively.

        Args:
            given: Given name
            surname: Surname
            prefix: Prefix (Mr., Mrs., etc.)
            suffix: Suffix (Jr., Sr., III, etc.)
            nickname: Nickname
            sex: Sex indicator ('M', 'F', 'U')

        Returns:
            CleanedName object with original, cleaned, and list of changes
        """
        changes = []
        warnings = []

        # Store originals
        original_given = given
        original_surname = surname
        original_prefix = prefix
        original_suffix = suffix
        original_nickname = nickname

        # Clean each component
        given, given_changes, given_warnings = cls._clean_given_name(given, sex)
        surname, surname_changes, surname_warnings = cls._clean_surname(surname)
        prefix, prefix_changes, prefix_warnings = cls._clean_prefix(prefix)
        suffix, suffix_changes, suffix_warnings = cls._clean_suffix(suffix)
        nickname, nick_changes, nick_warnings = cls._clean_nickname(nickname)

        changes.extend(given_changes)
        changes.extend(surname_changes)
        changes.extend(prefix_changes)
        changes.extend(suffix_changes)
        changes.extend(nick_changes)

        warnings.extend(given_warnings)
        warnings.extend(surname_warnings)
        warnings.extend(prefix_warnings)
        warnings.extend(suffix_warnings)
        warnings.extend(nick_warnings)

        # Check for cross-field issues
        cross_changes, cross_warnings = cls._check_cross_field_issues(
            given, surname, prefix, suffix, nickname
        )
        changes.extend(cross_changes)
        warnings.extend(cross_warnings)

        if not changes:
            changes = ['No changes needed']

        return CleanedName(
            original_given=original_given,
            original_surname=original_surname,
            original_prefix=original_prefix,
            original_suffix=original_suffix,
            original_nickname=original_nickname,
            cleaned_given=given,
            cleaned_surname=surname,
            cleaned_prefix=prefix,
            cleaned_suffix=suffix,
            cleaned_nickname=nickname,
            changes_made=changes,
            warnings=warnings
        )

    @classmethod
    def _clean_given_name(cls, given: Optional[str], sex: Optional[str] = None) -> Tuple[Optional[str], List[str], List[str]]:
        """Clean given name field."""
        if not given or not given.strip():
            return None, [], []

        original = given
        changes = []
        warnings = []

        # Step 1: Remove 'feu' (French for deceased)
        given, feu_removed = cls._remove_feu(given)
        if feu_removed:
            changes.append("Removed 'feu' (French for deceased)")

        # Step 2: Check for descriptions
        is_desc, desc_type = cls._is_description(given)
        if is_desc:
            warnings.append(f"Given name appears to be a description: {desc_type}")

        # Step 3: Fix all uppercase
        if given.isupper() and len(given) > 2:
            given = NameParser.smart_title_case(given)
            changes.append('Converted from all uppercase')

        # Step 4: Fix spacing
        given, spacing_changes = cls._fix_spacing(given)
        changes.extend(spacing_changes)

        # Step 5: Fix punctuation
        given, punct_changes = cls._fix_punctuation(given)
        changes.extend(punct_changes)

        # Step 6: Remove invalid characters
        given, invalid_changes = cls._remove_invalid_characters(given)
        changes.extend(invalid_changes)

        # Step 7: Check for alternate names
        has_alt, alt_pattern = cls._has_alternate_name_pattern(given)
        if has_alt:
            warnings.append(f"Given name contains alternate name pattern: {alt_pattern}")

        # Final cleanup
        given = given.strip() if given else None

        return given, changes, warnings

    @classmethod
    def _clean_surname(cls, surname: Optional[str]) -> Tuple[Optional[str], List[str], List[str]]:
        """Clean surname field."""
        if not surname or not surname.strip():
            return None, [], []

        original = surname
        changes = []
        warnings = []

        # Step 1: Check for descriptions
        is_desc, desc_type = cls._is_description(surname)
        if is_desc:
            warnings.append(f"Surname appears to be a description: {desc_type}")

        # Step 2: Fix all uppercase (but preserve surname particles)
        if surname.isupper() and len(surname) > 2:
            surname = NameParser.smart_title_case(surname)
            changes.append('Converted from all uppercase')

        # Step 3: Fix spacing
        surname, spacing_changes = cls._fix_spacing(surname)
        changes.extend(spacing_changes)

        # Step 4: Fix punctuation
        surname, punct_changes = cls._fix_punctuation(surname)
        changes.extend(punct_changes)

        # Step 5: Remove invalid characters
        surname, invalid_changes = cls._remove_invalid_characters(surname)
        changes.extend(invalid_changes)

        # Step 6: Check for alternate names
        has_alt, alt_pattern = cls._has_alternate_name_pattern(surname)
        if has_alt:
            warnings.append(f"Surname contains alternate name pattern: {alt_pattern}")

        # Final cleanup
        surname = surname.strip() if surname else None

        return surname, changes, warnings

    @classmethod
    def _clean_prefix(cls, prefix: Optional[str]) -> Tuple[Optional[str], List[str], List[str]]:
        """Clean prefix field."""
        if not prefix or not prefix.strip():
            return None, [], []

        changes = []
        warnings = []

        # Fix spacing
        prefix, spacing_changes = cls._fix_spacing(prefix)
        changes.extend(spacing_changes)

        # Standardize common prefixes
        prefix = prefix.strip()
        prefix_map = {
            'mr': 'Mr.',
            'mrs': 'Mrs.',
            'ms': 'Ms.',
            'miss': 'Miss',
            'dr': 'Dr.',
            'rev': 'Rev.',
            'sir': 'Sir',
            'lady': 'Lady',
            'lord': 'Lord',
        }

        lower = prefix.lower().rstrip('.')
        if lower in prefix_map and prefix != prefix_map[lower]:
            old_prefix = prefix
            prefix = prefix_map[lower]
            changes.append(f'Standardized prefix: {old_prefix} -> {prefix}')

        return prefix, changes, warnings

    @classmethod
    def _clean_suffix(cls, suffix: Optional[str]) -> Tuple[Optional[str], List[str], List[str]]:
        """Clean suffix field."""
        if not suffix or not suffix.strip():
            return None, [], []

        changes = []
        warnings = []

        # Fix spacing
        suffix, spacing_changes = cls._fix_spacing(suffix)
        changes.extend(spacing_changes)

        # Standardize common suffixes
        suffix = suffix.strip()
        suffix_map = {
            'jr': 'Jr.',
            'sr': 'Sr.',
            'ii': 'II',
            'iii': 'III',
            'iv': 'IV',
            'esq': 'Esq.',
            'phd': 'Ph.D.',
            'md': 'M.D.',
        }

        lower = suffix.lower().rstrip('.')
        if lower in suffix_map and suffix != suffix_map[lower]:
            old_suffix = suffix
            suffix = suffix_map[lower]
            changes.append(f'Standardized suffix: {old_suffix} -> {suffix}')

        return suffix, changes, warnings

    @classmethod
    def _clean_nickname(cls, nickname: Optional[str]) -> Tuple[Optional[str], List[str], List[str]]:
        """Clean nickname field."""
        if not nickname or not nickname.strip():
            return None, [], []

        original = nickname
        changes = []
        warnings = []

        # Check if nickname contains surname particles (misclassified surname)
        if NameParser.has_surname_particle(nickname):
            warnings.append("Nickname contains surname particle - may be misclassified surname")

        # Step 1: Fix all uppercase
        if nickname.isupper() and len(nickname) > 2:
            nickname = NameParser.smart_title_case(nickname)
            changes.append('Converted from all uppercase')

        # Step 2: Fix spacing
        nickname, spacing_changes = cls._fix_spacing(nickname)
        changes.extend(spacing_changes)

        # Step 3: Fix punctuation
        nickname, punct_changes = cls._fix_punctuation(nickname)
        changes.extend(punct_changes)

        # Step 4: Remove invalid characters
        nickname, invalid_changes = cls._remove_invalid_characters(nickname)
        changes.extend(invalid_changes)

        # Final cleanup
        nickname = nickname.strip() if nickname else None

        return nickname, changes, warnings

    @classmethod
    def _remove_feu(cls, text: str) -> Tuple[str, bool]:
        """Remove French 'feu' (deceased) from text."""
        if not text:
            return text, False

        original = text
        for pattern in cls.FEU_PATTERNS:
            text = re.sub(pattern, '', text)

        # Clean up spacing
        text = re.sub(r'\s+', ' ', text).strip()

        return text, text != original

    @classmethod
    def _is_description(cls, text: str) -> Tuple[bool, str]:
        """Check if text is a description rather than a name."""
        if not text:
            return False, ''

        text_lower = text.lower()
        for pattern in cls.DESCRIPTION_PATTERNS:
            if re.search(pattern, text_lower):
                return True, pattern

        return False, ''

    @classmethod
    def _has_alternate_name_pattern(cls, text: str) -> Tuple[bool, str]:
        """Check if text contains alternate name pattern."""
        if not text:
            return False, ''

        for pattern in cls.ALTERNATE_NAME_PATTERNS:
            if re.search(pattern, text):
                return True, pattern

        return False, ''

    @classmethod
    def _fix_spacing(cls, text: str) -> Tuple[str, List[str]]:
        """Fix spacing issues in text."""
        if not text:
            return text, []

        changes = []
        original = text

        # Fix multiple spaces
        text = re.sub(r'\s{2,}', ' ', text)
        if text != original:
            changes.append('Fixed multiple spaces')

        # Trim whitespace
        text = text.strip()

        return text, changes

    @classmethod
    def _fix_punctuation(cls, text: str) -> Tuple[str, List[str]]:
        """Fix punctuation issues in text."""
        if not text:
            return text, []

        changes = []
        original = text

        # Fix multiple periods
        text = re.sub(r'\.{2,}', '.', text)
        if text != original:
            changes.append('Fixed multiple periods')
            original = text

        # Fix space before period
        text = re.sub(r'\s+\.', '.', text)
        if text != original:
            changes.append('Removed space before period')

        return text, changes

    @classmethod
    def _remove_invalid_characters(cls, text: str) -> Tuple[str, List[str]]:
        """Remove invalid characters from text."""
        if not text:
            return text, []

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
    def _check_cross_field_issues(cls, given: Optional[str], surname: Optional[str],
                                  prefix: Optional[str], suffix: Optional[str],
                                  nickname: Optional[str]) -> Tuple[List[str], List[str]]:
        """Check for issues across multiple name fields."""
        changes = []
        warnings = []

        # Check if wife might share husband's surname (both given and surname same)
        # This is a common data entry error
        if given and surname and given.lower() == surname.lower():
            warnings.append("Given name and surname are identical - possible data entry error")

        # Check if prefix/suffix are misplaced
        if prefix and NameParser.is_title_suffix(prefix):
            warnings.append(f"Prefix '{prefix}' appears to be a title suffix - should be in suffix field")

        if suffix and NameParser.is_prefix(suffix):
            warnings.append(f"Suffix '{suffix}' appears to be a prefix - should be in prefix field")

        # Check if nickname contains surname particles
        if nickname and NameParser.has_surname_particle(nickname) and not surname:
            warnings.append("Nickname contains surname particle but no surname - possible misclassification")

        return changes, warnings

    @classmethod
    def detect_wife_shares_husband_surname(cls, wife_given: Optional[str],
                                          wife_surname: Optional[str],
                                          husband_given: Optional[str],
                                          husband_surname: Optional[str]) -> Tuple[bool, str]:
        """Detect if wife shares husband's surname (common error in old records).

        Args:
            wife_given: Wife's given name
            wife_surname: Wife's surname
            husband_given: Husband's given name
            husband_surname: Husband's surname

        Returns:
            Tuple of (is_error, explanation)
        """
        if not wife_given or not husband_given or not husband_surname:
            return False, ''

        # Case 1: Wife's "given name" is actually husband's full name
        # e.g., Given: "John Smith", Surname: "Smith"
        if wife_given and husband_surname:
            if husband_surname.lower() in wife_given.lower():
                return True, f"Wife's given name '{wife_given}' contains husband's surname '{husband_surname}'"

        # Case 2: Wife's surname matches husband's but shouldn't (maiden name expected)
        if wife_surname and husband_surname:
            if wife_surname.lower() == husband_surname.lower():
                # This is actually normal in most databases - wife takes husband's surname
                # Only flag if wife's given name looks suspicious
                if wife_given.lower() == husband_given.lower():
                    return True, "Wife has same given and surname as husband - likely data entry error"

        return False, ''
