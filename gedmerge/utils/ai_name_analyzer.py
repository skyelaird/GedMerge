"""AI-powered name analysis using Claude for intelligent, context-aware name parsing.

This module provides smart name analysis capabilities that go beyond hardcoded rules,
handling complex cases like:
- Distinguishing between name variants and nicknames/epithets
- Context-aware title detection (e.g., French nobility titles)
- Intelligent capitalization correction
- Cultural and linguistic context understanding
"""

import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import anthropic


class ParenthesesType(Enum):
    """Type of content found in parentheses."""
    NAME_VARIANT = "name_variant"  # e.g., "Vazul (Basil)"
    NICKNAME = "nickname"  # e.g., "Albert (the Elder)"
    EPITHET = "epithet"  # e.g., "Charles (the Great)"
    TITLE = "title"  # e.g., "John (Earl of Essex)"
    UNKNOWN = "unknown"


@dataclass
class AINameAnalysis:
    """Results from AI-powered name analysis."""
    # Corrected components
    given_name: Optional[str] = None
    surname: Optional[str] = None
    prefix: Optional[str] = None  # Honorific like Mr, Mrs, Dr
    title: Optional[str] = None  # Nobility title like Seigneur, Duke
    suffix: Optional[str] = None
    nickname: Optional[str] = None

    # Extracted variants
    name_variants: List[str] = None

    # Corrections made
    capitalization_fixed: bool = False
    original_capitalization: Optional[str] = None

    # Parentheses analysis
    parentheses_type: Optional[ParenthesesType] = None
    parentheses_content: Optional[str] = None

    # Confidence and explanation
    confidence: float = 0.0
    explanation: str = ""

    def __post_init__(self):
        if self.name_variants is None:
            self.name_variants = []


class AINameAnalyzer:
    """AI-powered name analyzer using Claude for intelligent parsing."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the AI name analyzer.

        Args:
            api_key: Anthropic API key. If not provided, will try to read from ANTHROPIC_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError(
                "Anthropic API key is required. Either pass it to __init__ or set ANTHROPIC_API_KEY env var."
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def analyze_name(
        self,
        given_name: Optional[str] = None,
        surname: Optional[str] = None,
        sex: Optional[str] = None,
        prefix: Optional[str] = None,
        language_hint: Optional[str] = None
    ) -> AINameAnalysis:
        """Analyze a name using AI to detect issues and suggest corrections.

        Args:
            given_name: Given name field
            surname: Surname field
            sex: Person's sex ('M', 'F', 'U')
            prefix: Existing prefix field
            language_hint: Optional language hint (e.g., 'French', 'English')

        Returns:
            AINameAnalysis with detected issues and suggested corrections
        """
        prompt = self._build_analysis_prompt(given_name, surname, sex, prefix, language_hint)

        try:
            message = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1024,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = message.content[0].text
            return self._parse_ai_response(response_text, given_name, surname, prefix)

        except Exception as e:
            # If AI fails, return basic analysis
            return AINameAnalysis(
                given_name=given_name,
                surname=surname,
                prefix=prefix,
                confidence=0.0,
                explanation=f"AI analysis failed: {str(e)}"
            )

    def _build_analysis_prompt(
        self,
        given_name: Optional[str],
        surname: Optional[str],
        sex: Optional[str],
        prefix: Optional[str],
        language_hint: Optional[str]
    ) -> str:
        """Build the prompt for Claude to analyze the name."""

        prompt = """You are a genealogy name analysis expert. Analyze the following name data and identify any issues or corrections needed.

Name Data:
"""
        if given_name:
            prompt += f"- Given Name: '{given_name}'\n"
        if surname:
            prompt += f"- Surname: '{surname}'\n"
        if sex:
            prompt += f"- Sex: {sex}\n"
        if prefix:
            prompt += f"- Existing Prefix: '{prefix}'\n"
        if language_hint:
            prompt += f"- Language Hint: {language_hint}\n"

        prompt += """
Your task is to analyze this name and identify:

1. **Capitalization Issues**: Check if any components have incorrect capitalization (e.g., "mISS" should be "Miss", "jOHN" should be "John")

2. **Prefix vs Title**:
   - Prefixes are honorifics like Mr, Mrs, Miss, Dr, Monsieur, Madame
   - Titles are nobility/status titles like Seigneur, Duke, Earl, Baron
   - In French, "Seigneur" is a TITLE, not a prefix
   - Special case: French "M." for females should be expanded to "Marie" as part of the given name, NOT treated as a prefix

3. **Parentheses Content**: If there are parentheses in the given name:
   - NAME_VARIANT: Another form of the same name (e.g., "Vazul (Basil)", "John (Jean)")
   - NICKNAME: A descriptive nickname (e.g., "Albert (the Elder)", "William (Longsword)")
   - EPITHET: A title or descriptor (e.g., "Charles (the Great)", "Edward (the Confessor)")
   - TITLE: A nobility title (e.g., "John (Earl of Essex)")

4. **Name Variants**: If parentheses contain a NAME_VARIANT, extract it

Return your analysis in this EXACT format (use --- as separators):

GIVEN_NAME: <corrected given name or UNCHANGED>
SURNAME: <corrected surname or UNCHANGED>
PREFIX: <honorific prefix or NONE>
TITLE: <nobility title or NONE>
NICKNAME: <nickname or NONE>
---
CAPITALIZATION_FIXED: <yes or no>
ORIGINAL_CAPITALIZATION: <original text if fixed, or NONE>
---
PARENTHESES_TYPE: <NAME_VARIANT, NICKNAME, EPITHET, TITLE, or NONE>
PARENTHESES_CONTENT: <extracted content or NONE>
---
NAME_VARIANTS: <comma-separated list of name variants or NONE>
---
CONFIDENCE: <0.0 to 1.0>
EXPLANATION: <brief explanation of your analysis>

Examples:

Input: Given Name: "M. Rose", Sex: F
Output:
GIVEN_NAME: Marie Rose
SURNAME: UNCHANGED
PREFIX: NONE
TITLE: NONE
NICKNAME: NONE
---
CAPITALIZATION_FIXED: no
ORIGINAL_CAPITALIZATION: NONE
---
PARENTHESES_TYPE: NONE
PARENTHESES_CONTENT: NONE
---
NAME_VARIANTS: NONE
---
CONFIDENCE: 0.95
EXPLANATION: French "M." for a female should be expanded to "Marie" as part of the given name, not treated as the prefix "Monsieur".

Input: Given Name: "Vazul (Basil)"
Output:
GIVEN_NAME: Vazul
SURNAME: UNCHANGED
PREFIX: NONE
TITLE: NONE
NICKNAME: NONE
---
CAPITALIZATION_FIXED: no
ORIGINAL_CAPITALIZATION: NONE
---
PARENTHESES_TYPE: NAME_VARIANT
PARENTHESES_CONTENT: Basil
---
NAME_VARIANTS: Basil
---
CONFIDENCE: 0.9
EXPLANATION: "Basil" is an English/Latin variant of the Hungarian name "Vazul". This should be recorded as a name variant.

Input: Given Name: "Albert (the Elder)"
Output:
GIVEN_NAME: Albert
SURNAME: UNCHANGED
PREFIX: NONE
TITLE: NONE
NICKNAME: the Elder
---
CAPITALIZATION_FIXED: no
ORIGINAL_CAPITALIZATION: NONE
---
PARENTHESES_TYPE: NICKNAME
PARENTHESES_CONTENT: the Elder
---
NAME_VARIANTS: NONE
---
CONFIDENCE: 0.95
EXPLANATION: "the Elder" is a descriptive epithet/nickname, not a name variant. Should be stored in the nickname field.

Input: Given Name: "Seigneur d'Amboise et Chaumont"
Output:
GIVEN_NAME: NONE
SURNAME: UNCHANGED
PREFIX: NONE
TITLE: Seigneur d'Amboise et Chaumont
NICKNAME: NONE
---
CAPITALIZATION_FIXED: no
ORIGINAL_CAPITALIZATION: NONE
---
PARENTHESES_TYPE: NONE
PARENTHESES_CONTENT: NONE
---
NAME_VARIANTS: NONE
---
CONFIDENCE: 0.98
EXPLANATION: This entire field is a French nobility title. "Seigneur" (Lord) is the title, "d'Amboise et Chaumont" indicates the domains. This should be moved to a title/suffix field, not the given name.

Input: Given Name: "mISS"
Output:
GIVEN_NAME: Miss
SURNAME: UNCHANGED
PREFIX: Miss
TITLE: NONE
NICKNAME: NONE
---
CAPITALIZATION_FIXED: yes
ORIGINAL_CAPITALIZATION: mISS
---
PARENTHESES_TYPE: NONE
PARENTHESES_CONTENT: NONE
---
NAME_VARIANTS: NONE
---
CONFIDENCE: 0.9
EXPLANATION: Capitalization error detected. "mISS" should be "Miss" (an honorific prefix).

Now analyze the name data provided above.
"""

        return prompt

    def _parse_ai_response(
        self,
        response: str,
        original_given: Optional[str],
        original_surname: Optional[str],
        original_prefix: Optional[str]
    ) -> AINameAnalysis:
        """Parse Claude's structured response into AINameAnalysis."""

        result = AINameAnalysis()

        try:
            lines = response.strip().split('\n')

            for line in lines:
                line = line.strip()
                if not line or line == '---':
                    continue

                if ':' not in line:
                    continue

                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                # Parse each field
                if key == 'GIVEN_NAME':
                    result.given_name = None if value == 'UNCHANGED' or value == 'NONE' else value
                    if not result.given_name:
                        result.given_name = original_given

                elif key == 'SURNAME':
                    result.surname = None if value == 'UNCHANGED' or value == 'NONE' else value
                    if not result.surname:
                        result.surname = original_surname

                elif key == 'PREFIX':
                    result.prefix = None if value == 'NONE' else value

                elif key == 'TITLE':
                    result.title = None if value == 'NONE' else value

                elif key == 'NICKNAME':
                    result.nickname = None if value == 'NONE' else value

                elif key == 'CAPITALIZATION_FIXED':
                    result.capitalization_fixed = value.lower() == 'yes'

                elif key == 'ORIGINAL_CAPITALIZATION':
                    result.original_capitalization = None if value == 'NONE' else value

                elif key == 'PARENTHESES_TYPE':
                    if value != 'NONE':
                        try:
                            result.parentheses_type = ParenthesesType(value.lower())
                        except ValueError:
                            result.parentheses_type = ParenthesesType.UNKNOWN

                elif key == 'PARENTHESES_CONTENT':
                    result.parentheses_content = None if value == 'NONE' else value

                elif key == 'NAME_VARIANTS':
                    if value != 'NONE':
                        result.name_variants = [v.strip() for v in value.split(',')]

                elif key == 'CONFIDENCE':
                    try:
                        result.confidence = float(value)
                    except ValueError:
                        result.confidence = 0.5

                elif key == 'EXPLANATION':
                    result.explanation = value

        except Exception as e:
            result.confidence = 0.0
            result.explanation = f"Failed to parse AI response: {str(e)}"
            result.given_name = original_given
            result.surname = original_surname
            result.prefix = original_prefix

        return result


def analyze_name_with_ai(
    given_name: Optional[str] = None,
    surname: Optional[str] = None,
    sex: Optional[str] = None,
    prefix: Optional[str] = None,
    language_hint: Optional[str] = None,
    api_key: Optional[str] = None
) -> AINameAnalysis:
    """Convenience function to analyze a name using AI.

    Args:
        given_name: Given name field
        surname: Surname field
        sex: Person's sex ('M', 'F', 'U')
        prefix: Existing prefix field
        language_hint: Optional language hint
        api_key: Anthropic API key (optional, can use env var)

    Returns:
        AINameAnalysis with detected issues and corrections
    """
    analyzer = AINameAnalyzer(api_key=api_key)
    return analyzer.analyze_name(given_name, surname, sex, prefix, language_hint)
