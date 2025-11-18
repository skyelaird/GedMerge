"""
Comprehensive multilingual support for genealogy data.

This module provides adaptive language detection and normalization for:
- Titles and honorifics
- Family relationships
- Event types
- Occupations
- Places

The system is designed to be extensible and can learn new equivalencies.
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


class Language(Enum):
    """Supported languages."""
    ENGLISH = "en"
    FRENCH = "fr"
    GERMAN = "de"
    SPANISH = "es"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class MultilingualTerm:
    """A term with translations across multiple languages."""
    english: str  # Canonical/normalized form
    french: Optional[str] = None
    german: Optional[str] = None
    spanish: Optional[str] = None
    italian: Optional[str] = None
    portuguese: Optional[str] = None
    category: str = "general"  # e.g., "title", "relationship", "event", "occupation"
    aliases: Set[str] = field(default_factory=set)  # Additional variations

    def get_translation(self, language: Language) -> Optional[str]:
        """Get the translation for a specific language."""
        lang_map = {
            Language.ENGLISH: self.english,
            Language.FRENCH: self.french,
            Language.GERMAN: self.german,
            Language.SPANISH: self.spanish,
            Language.ITALIAN: self.italian,
            Language.PORTUGUESE: self.portuguese
        }
        return lang_map.get(language)

    def all_forms(self) -> Set[str]:
        """Get all forms of this term across all languages."""
        forms = {self.english}
        for lang in Language:
            if lang != Language.UNKNOWN:
                trans = self.get_translation(lang)
                if trans:
                    forms.add(trans)
        forms.update(self.aliases)
        return {f for f in forms if f}


class LanguageDetector:
    """Detects the language of text using pattern matching."""

    # Language-specific patterns and common words
    PATTERNS = {
        Language.FRENCH: {
            'words': r'\b(de|du|des|le|la|les|et|pour|sur|dans|avec|père|mère|fils|fille|'
                    r'naissance|décès|mariage|baptême|résidence|profession)\b',
            'chars': r'[àâäéèêëïîôùûü]',
            'titles': r'\b(m\.|mme|mlle|capitaine|lieutenant|major|colonel|général|'
                     r'cultivateur|commerçant|médecin|avocat|roi|duc|comte|seigneur)\b'
        },
        Language.GERMAN: {
            'words': r'\b(der|die|das|und|von|zu|in|auf|für|mit|vater|mutter|sohn|tochter|'
                    r'geburt|tod|hochzeit|taufe|wohnsitz|beruf)\b',
            'chars': r'[äöüß]',
            'titles': r'\b(herr|frau|fräulein|hauptmann|leutnant|major|oberst|general|'
                     r'bauer|kaufmann|arzt|anwalt|könig|herzog|graf)\b'
        },
        Language.SPANISH: {
            'words': r'\b(el|la|los|las|de|del|y|para|con|padre|madre|hijo|hija|'
                    r'nacimiento|defunción|matrimonio|bautismo|residencia|ocupación)\b',
            'chars': r'[áéíóúñ]',
            'titles': r'\b(sr\.|sra\.|srta\.|capitán|teniente|mayor|coronel|general|'
                     r'agricultor|comerciante|médico|abogado|rey|duque|conde)\b'
        },
        Language.ITALIAN: {
            'words': r'\b(il|la|i|le|di|del|della|e|per|con|padre|madre|figlio|figlia|'
                    r'nascita|morte|matrimonio|battesimo|residenza|occupazione)\b',
            'chars': r'[àèéìòù]',
            'titles': r'\b(sig\.|sig\.ra|sig\.na|capitano|tenente|maggiore|colonnello|generale|'
                     r'agricoltore|commerciante|medico|avvocato|re|duca|conte)\b'
        },
        Language.PORTUGUESE: {
            'words': r'\b(o|a|os|as|de|do|da|e|para|com|pai|mãe|filho|filha|'
                    r'nascimento|óbito|casamento|batismo|residência|ocupação)\b',
            'chars': r'[ãõâêôáéíóú]',
            'titles': r'\b(sr\.|sra\.|srta\.|capitão|tenente|major|coronel|general|'
                     r'agricultor|comerciante|médico|advogado|rei|duque|conde)\b'
        }
    }

    def detect(self, text: str) -> Language:
        """Detect the most likely language of text."""
        if not text or not text.strip():
            return Language.UNKNOWN

        text = text.lower()
        scores = {lang: 0 for lang in Language if lang != Language.UNKNOWN}

        for lang, patterns in self.PATTERNS.items():
            # Score based on word matches
            word_matches = len(re.findall(patterns['words'], text, re.IGNORECASE))
            scores[lang] += word_matches * 3

            # Score based on character matches
            char_matches = len(re.findall(patterns['chars'], text))
            scores[lang] += char_matches * 2

            # Score based on title/term matches
            if 'titles' in patterns:
                title_matches = len(re.findall(patterns['titles'], text, re.IGNORECASE))
                scores[lang] += title_matches * 5

        # Return language with highest score, or English if no clear winner
        max_score = max(scores.values())
        if max_score == 0:
            return Language.ENGLISH

        return max(scores.items(), key=lambda x: x[1])[0]


class MultilingualRegistry:
    """Registry of multilingual terms with normalization capabilities."""

    def __init__(self, data_file: Optional[Path] = None):
        self.terms: Dict[str, MultilingualTerm] = {}
        self.reverse_index: Dict[str, str] = {}  # Maps any form -> english canonical
        self.detector = LanguageDetector()
        self.data_file = data_file

        # Initialize with core terms
        self._initialize_core_terms()

        # Load from file if provided
        if data_file and data_file.exists():
            self.load(data_file)

    def _initialize_core_terms(self):
        """Initialize with core multilingual equivalencies."""

        # Military Ranks
        ranks = [
            MultilingualTerm("Lieutenant", "Lieutenant", "Leutnant", "Teniente", "Tenente", "Tenente", "title"),
            MultilingualTerm("Captain", "Capitaine", "Hauptmann", "Capitán", "Capitano", "Capitão", "title"),
            MultilingualTerm("Major", "Major", "Major", "Mayor", "Maggiore", "Major", "title"),
            MultilingualTerm("Colonel", "Colonel", "Oberst", "Coronel", "Colonnello", "Coronel", "title"),
            MultilingualTerm("General", "Général", "General", "General", "Generale", "General", "title"),
            MultilingualTerm("Private", "Soldat", "Soldat", "Soldado", "Soldato", "Soldado", "title"),
            MultilingualTerm("Sergeant", "Sergent", "Feldwebel", "Sargento", "Sergente", "Sargento", "title"),
        ]

        # Family Relationships
        relationships = [
            MultilingualTerm("Father", "Père", "Vater", "Padre", "Padre", "Pai", "relationship"),
            MultilingualTerm("Mother", "Mère", "Mutter", "Madre", "Madre", "Mãe", "relationship"),
            MultilingualTerm("Son", "Fils", "Sohn", "Hijo", "Figlio", "Filho", "relationship"),
            MultilingualTerm("Daughter", "Fille", "Tochter", "Hija", "Figlia", "Filha", "relationship"),
            MultilingualTerm("Brother", "Frère", "Bruder", "Hermano", "Fratello", "Irmão", "relationship"),
            MultilingualTerm("Sister", "Sœur", "Schwester", "Hermana", "Sorella", "Irmã", "relationship"),
            MultilingualTerm("Husband", "Mari", "Ehemann", "Esposo", "Marito", "Marido", "relationship"),
            MultilingualTerm("Wife", "Femme", "Ehefrau", "Esposa", "Moglie", "Esposa", "relationship"),
            MultilingualTerm("Grandfather", "Grand-père", "Großvater", "Abuelo", "Nonno", "Avô", "relationship"),
            MultilingualTerm("Grandmother", "Grand-mère", "Großmutter", "Abuela", "Nonna", "Avó", "relationship"),
        ]

        # Event Types
        events = [
            MultilingualTerm("Birth", "Naissance", "Geburt", "Nacimiento", "Nascita", "Nascimento", "event"),
            MultilingualTerm("Death", "Décès", "Tod", "Defunción", "Morte", "Óbito", "event"),
            MultilingualTerm("Marriage", "Mariage", "Hochzeit", "Matrimonio", "Matrimonio", "Casamento", "event"),
            MultilingualTerm("Baptism", "Baptême", "Taufe", "Bautismo", "Battesimo", "Batismo", "event"),
            MultilingualTerm("Burial", "Inhumation", "Beerdigung", "Entierro", "Sepoltura", "Sepultamento", "event"),
            MultilingualTerm("Residence", "Résidence", "Wohnsitz", "Residencia", "Residenza", "Residência", "event"),
            MultilingualTerm("Occupation", "Profession", "Beruf", "Ocupación", "Occupazione", "Ocupação", "event"),
            MultilingualTerm("Military Service", "Service Militaire", "Militärdienst",
                           "Servicio Militar", "Servizio Militare", "Serviço Militar", "event"),
            MultilingualTerm("Education", "Éducation", "Bildung", "Educación", "Istruzione", "Educação", "event"),
            MultilingualTerm("Immigration", "Immigration", "Einwanderung", "Inmigración", "Immigrazione", "Imigração", "event"),
            MultilingualTerm("Emigration", "Émigration", "Auswanderung", "Emigración", "Emigrazione", "Emigração", "event"),
        ]

        # Titles/Honorifics
        titles = [
            MultilingualTerm("Mr.", "M.", "Herr", "Sr.", "Sig.", "Sr.", "title"),
            MultilingualTerm("Mrs.", "Mme", "Frau", "Sra.", "Sig.ra", "Sra.", "title"),
            MultilingualTerm("Miss", "Mlle", "Fräulein", "Srta.", "Sig.na", "Srta.", "title"),
            MultilingualTerm("Dr.", "Dr", "Dr.", "Dr.", "Dott.", "Dr.", "title"),
            MultilingualTerm("Rev.", "Rév.", "Pfarrer", "Rev.", "Rev.", "Rev.", "title"),
            MultilingualTerm("Sir", "Sieur", "Herr", "Señor", "Signore", "Senhor", "title"),
            MultilingualTerm("Lady", "Dame", "Frau", "Señora", "Signora", "Senhora", "title"),
            MultilingualTerm("Lord", "Seigneur", "Herr", "Señor", "Signore", "Senhor", "title"),
            MultilingualTerm("King", "Roi", "König", "Rey", "Re", "Rei", "title"),
            MultilingualTerm("Queen", "Reine", "Königin", "Reina", "Regina", "Rainha", "title"),
            MultilingualTerm("Prince", "Prince", "Prinz", "Príncipe", "Principe", "Príncipe", "title"),
            MultilingualTerm("Princess", "Princesse", "Prinzessin", "Princesa", "Principessa", "Princesa", "title"),
            MultilingualTerm("Duke", "Duc", "Herzog", "Duque", "Duca", "Duque", "title"),
            MultilingualTerm("Count", "Comte", "Graf", "Conde", "Conte", "Conde", "title"),
            MultilingualTerm("Baron", "Baron", "Baron", "Barón", "Barone", "Barão", "title"),
        ]

        # Occupations
        occupations = [
            MultilingualTerm("Farmer", "Cultivateur", "Bauer", "Agricultor", "Agricoltore", "Agricultor", "occupation"),
            MultilingualTerm("Merchant", "Commerçant", "Kaufmann", "Comerciante", "Commerciante", "Comerciante", "occupation"),
            MultilingualTerm("Teacher", "Enseignant", "Lehrer", "Maestro", "Insegnante", "Professor", "occupation"),
            MultilingualTerm("Doctor", "Médecin", "Arzt", "Médico", "Medico", "Médico", "occupation"),
            MultilingualTerm("Lawyer", "Avocat", "Anwalt", "Abogado", "Avvocato", "Advogado", "occupation"),
            MultilingualTerm("Carpenter", "Charpentier", "Zimmermann", "Carpintero", "Falegname", "Carpinteiro", "occupation"),
            MultilingualTerm("Blacksmith", "Forgeron", "Schmied", "Herrero", "Fabbro", "Ferreiro", "occupation"),
            MultilingualTerm("Postmaster", "Maître de poste", "Postmeister", "Jefe de correos",
                           "Direttore postale", "Chefe dos correios", "occupation"),
            MultilingualTerm("Priest", "Prêtre", "Priester", "Sacerdote", "Sacerdote", "Padre", "occupation"),
            MultilingualTerm("Baker", "Boulanger", "Bäcker", "Panadero", "Panettiere", "Padeiro", "occupation"),
        ]

        # Add all terms to registry
        for term in ranks + relationships + events + titles + occupations:
            self.add_term(term)

    def add_term(self, term: MultilingualTerm):
        """Add a term to the registry and update reverse index."""
        canonical = term.english.lower()
        self.terms[canonical] = term

        # Update reverse index for all forms
        for form in term.all_forms():
            self.reverse_index[form.lower()] = canonical

    def normalize(self, text: str, detect_language: bool = True) -> Tuple[str, Optional[Language], List[str]]:
        """
        Normalize text to English canonical form.

        Returns:
            - Normalized English term
            - Detected language (if detect_language=True)
            - List of alternate forms found
        """
        if not text:
            return text, Language.UNKNOWN, []

        text_lower = text.lower().strip()

        # Check if we have a direct match
        if text_lower in self.reverse_index:
            canonical = self.reverse_index[text_lower]
            term = self.terms[canonical]
            detected_lang = self.detector.detect(text) if detect_language else None
            alternates = list(term.all_forms() - {term.english})
            return term.english, detected_lang, alternates

        # No match found - return original with language detection
        detected_lang = self.detector.detect(text) if detect_language else None
        return text, detected_lang, []

    def learn_equivalency(self, term1: str, term2: str, category: str = "general") -> bool:
        """
        Learn a new equivalency between two terms.

        Attempts to add a new translation or create a new term.
        Returns True if learning was successful.
        """
        term1_lower = term1.lower().strip()
        term2_lower = term2.lower().strip()

        # Detect languages
        lang1 = self.detector.detect(term1)
        lang2 = self.detector.detect(term2)

        # If either is in registry, add the other as an alias/translation
        if term1_lower in self.reverse_index:
            canonical = self.reverse_index[term1_lower]
            term_obj = self.terms[canonical]
            term_obj.aliases.add(term2)
            self.reverse_index[term2_lower] = canonical
            return True
        elif term2_lower in self.reverse_index:
            canonical = self.reverse_index[term2_lower]
            term_obj = self.terms[canonical]
            term_obj.aliases.add(term1)
            self.reverse_index[term1_lower] = canonical
            return True
        else:
            # Create new term - assume term1 is English if it detects as English
            if lang1 == Language.ENGLISH:
                english_form = term1
                other_form = term2
                other_lang = lang2
            elif lang2 == Language.ENGLISH:
                english_form = term2
                other_form = term1
                other_lang = lang1
            else:
                # Neither is English, use term1 as canonical
                english_form = term1
                other_form = term2
                other_lang = lang2

            # Create new multilingual term
            new_term = MultilingualTerm(english=english_form, category=category)

            # Set translation for detected language
            if other_lang == Language.FRENCH:
                new_term.french = other_form
            elif other_lang == Language.GERMAN:
                new_term.german = other_form
            elif other_lang == Language.SPANISH:
                new_term.spanish = other_form
            elif other_lang == Language.ITALIAN:
                new_term.italian = other_form
            elif other_lang == Language.PORTUGUESE:
                new_term.portuguese = other_form
            else:
                new_term.aliases.add(other_form)

            self.add_term(new_term)
            return True

    def get_alternates(self, text: str) -> List[str]:
        """Get all alternate forms of a term."""
        text_lower = text.lower().strip()
        if text_lower in self.reverse_index:
            canonical = self.reverse_index[text_lower]
            term = self.terms[canonical]
            return list(term.all_forms() - {text})
        return []

    def save(self, filepath: Path):
        """Save registry to JSON file."""
        data = {
            'terms': {k: asdict(v) for k, v in self.terms.items()}
        }
        # Convert sets to lists for JSON serialization
        for term_data in data['terms'].values():
            term_data['aliases'] = list(term_data['aliases'])

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def load(self, filepath: Path):
        """Load registry from JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for canonical, term_data in data.get('terms', {}).items():
            # Convert aliases list back to set
            term_data['aliases'] = set(term_data['aliases'])
            term = MultilingualTerm(**term_data)
            self.add_term(term)

    def export_table(self, category: Optional[str] = None) -> str:
        """Export terms as a markdown table."""
        # Filter by category if specified
        terms = [t for t in self.terms.values()
                if category is None or t.category == category]

        if not terms:
            return "No terms found"

        # Build table
        header = "| English | French | German | Spanish | Italian | Portuguese |"
        separator = "|---------|--------|--------|---------|---------|------------|"

        rows = [header, separator]
        for term in sorted(terms, key=lambda t: t.english):
            row = f"| {term.english} | {term.french or ''} | {term.german or ''} | " \
                  f"{term.spanish or ''} | {term.italian or ''} | {term.portuguese or ''} |"
            rows.append(row)

        return "\n".join(rows)


# Global registry instance
_global_registry: Optional[MultilingualRegistry] = None


def get_registry() -> MultilingualRegistry:
    """Get or create the global registry instance."""
    global _global_registry
    if _global_registry is None:
        # Try to load from default location
        data_dir = Path(__file__).parent
        data_file = data_dir / "multilingual_terms.json"
        _global_registry = MultilingualRegistry(data_file if data_file.exists() else None)
    return _global_registry


def normalize_term(text: str) -> Tuple[str, List[str]]:
    """
    Convenience function to normalize a term to English.

    Returns: (normalized_term, alternate_forms)
    """
    registry = get_registry()
    normalized, _, alternates = registry.normalize(text)
    return normalized, alternates


def detect_language(text: str) -> Language:
    """Convenience function to detect language."""
    detector = LanguageDetector()
    return detector.detect(text)
