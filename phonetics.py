"""
Simple phonetics module for Metaphone algorithm.
Created as a workaround for installation issues with older phonetics packages.
"""

def metaphone(text, max_length=4):
    """
    Basic Metaphone algorithm implementation.

    Args:
        text: Input string to encode
        max_length: Maximum length of output code

    Returns:
        Phonetic code string
    """
    if not text:
        return ""

    # Convert to uppercase and remove non-letters
    text = ''.join(c for c in text.upper() if c.isalpha())

    if not text:
        return ""

    # Simplified Metaphone rules
    result = []
    i = 0

    # Drop initial letters in certain cases
    if text.startswith('KN') or text.startswith('GN') or text.startswith('PN') or text.startswith('AE') or text.startswith('WR'):
        i = 1
    elif text.startswith('X'):
        result.append('S')
        i = 1
    elif text.startswith('WH'):
        result.append('W')
        i = 2

    while i < len(text) and len(result) < max_length:
        c = text[i]
        prev = text[i-1] if i > 0 else ''
        next_c = text[i+1] if i < len(text)-1 else ''
        next2 = text[i+2] if i < len(text)-2 else ''

        # Skip duplicate letters (except C)
        if c == prev and c != 'C':
            i += 1
            continue

        # Vowels
        if c in 'AEIOU':
            if i == 0:
                result.append(c)

        # B
        elif c == 'B':
            if not (i == len(text)-1 and prev == 'M'):
                result.append('B')

        # C
        elif c == 'C':
            if next_c == 'H':
                result.append('X')
                i += 1
            elif next_c in 'IEY':
                result.append('S')
            else:
                result.append('K')

        # D
        elif c == 'D':
            if next_c == 'G' and next2 in 'EIY':
                result.append('J')
                i += 1
            else:
                result.append('T')

        # F
        elif c == 'F':
            result.append('F')

        # G
        elif c == 'G':
            if next_c == 'H' and i < len(text)-2:
                i += 1
                continue
            elif next_c == 'N' and i == len(text)-2:
                continue
            elif next_c in 'EIY':
                result.append('J')
            else:
                result.append('K')

        # H
        elif c == 'H':
            if prev not in 'AEIOU' or next_c not in 'AEIOU':
                if i > 0:
                    continue
            result.append('H')

        # J
        elif c == 'J':
            result.append('J')

        # K
        elif c == 'K':
            if prev != 'C':
                result.append('K')

        # L
        elif c == 'L':
            result.append('L')

        # M
        elif c == 'M':
            result.append('M')

        # N
        elif c == 'N':
            result.append('N')

        # P
        elif c == 'P':
            if next_c == 'H':
                result.append('F')
                i += 1
            else:
                result.append('P')

        # Q
        elif c == 'Q':
            result.append('K')

        # R
        elif c == 'R':
            result.append('R')

        # S
        elif c == 'S':
            if next_c == 'H':
                result.append('X')
                i += 1
            elif next_c == 'I' and next2 in 'OA':
                result.append('X')
                i += 2
            else:
                result.append('S')

        # T
        elif c == 'T':
            if next_c == 'H':
                result.append('0')  # TH sound
                i += 1
            elif next_c == 'I' and next2 in 'OA':
                result.append('X')
                i += 2
            elif next_c == 'C' and next2 == 'H':
                continue
            else:
                result.append('T')

        # V
        elif c == 'V':
            result.append('F')

        # W
        elif c == 'W':
            if next_c in 'AEIOU':
                result.append('W')

        # X
        elif c == 'X':
            result.append('KS')

        # Y
        elif c == 'Y':
            if next_c in 'AEIOU':
                result.append('Y')

        # Z
        elif c == 'Z':
            result.append('S')

        i += 1

    code = ''.join(result)[:max_length]
    return code if code else text[0] if text else ""


# Compatibility aliases
def dmetaphone(text):
    """Double Metaphone compatibility (returns tuple)."""
    return (metaphone(text), '')


def soundex(text):
    """
    Simple Soundex implementation.
    Returns a 4-character code.
    """
    if not text:
        return "0000"

    text = ''.join(c for c in text.upper() if c.isalpha())
    if not text:
        return "0000"

    # Soundex character mappings
    soundex_map = {
        'BFPV': '1',
        'CGJKQSXZ': '2',
        'DT': '3',
        'L': '4',
        'MN': '5',
        'R': '6'
    }

    # First letter
    result = [text[0]]

    # Map remaining letters
    for c in text[1:]:
        for letters, code in soundex_map.items():
            if c in letters:
                if len(result) == 1 or result[-1] != code:
                    result.append(code)
                break

        if len(result) >= 4:
            break

    # Pad with zeros
    while len(result) < 4:
        result.append('0')

    return ''.join(result[:4])
