#!/usr/bin/env python3
"""
Comprehensive multilingual analysis of GEDCOM data.
Extracts language patterns, titles, relationships, occupations, and event types.
"""

import re
from collections import defaultdict
from pathlib import Path
import unicodedata


class MultilingualAnalyzer:
    """Analyzes GEDCOM files for multilingual patterns."""

    def __init__(self):
        self.titles = defaultdict(set)
        self.occupations = defaultdict(set)
        self.event_types = defaultdict(set)
        self.relationships = defaultdict(set)
        self.places = defaultdict(set)
        self.general_terms = defaultdict(set)
        self.name_titles = defaultdict(set)  # Titles found in NAME fields
        self.title_examples = defaultdict(list)  # Store examples of each title

        # Track all text for language detection
        self.all_text = []

        # Comprehensive nobility and honorific titles by language
        self.nobility_titles = {
            'English': [
                r'\b(King|Queen|Prince|Princess|Duke|Duchess|Marquess|Marchioness)\b',
                r'\b(Earl|Countess|Viscount|Viscountess|Baron|Baroness|Baronet)\b',
                r'\b(Lord|Lady|Sir|Dame|Knight)\b',
                r'\b(Heiress|Heir)\s+of\s+\w+',
                r'\b(\d+(?:st|nd|rd|th)\s+(?:Earl|Baron|Lord|Duke))\b',
                r'\b(High\s+King|King\s+of\s+\w+|Queen\s+of\s+\w+)\b',
            ],
            'French': [
                r'\b(Roi|Reine|Prince|Princesse|Duc|Duchesse|Marquis|Marquise)\b',
                r'\b(Comte|Comtesse|Vicomte|Vicomtesse|Baron|Baronne)\b',
                r'\b(Seigneur|Dame|Chevalier|Ecuyer|Écuyer)\b',
                r'\b(Châtelain|Châtelaine)\b',
                r'\b(comte\s+d[\'e]\s*\w+|duc\s+d[\'e]\s*\w+)\b',
                r'\b(seigneur\s+d[\'e]\s*\w+)\b',
            ],
            'German': [
                r'\b(König|Königin|Prinz|Prinzessin|Herzog|Herzogin)\b',
                r'\b(Graf|Gräfin|Freiherr|Freifrau|Ritter)\b',
                r'\b(Markgraf|Pfalzgraf|Landgraf|Burggraf)\b',
                r'\b(Hallgraf)\b',
                r'\b(Graf\s+(?:von|im|zu)\s+\w+)\b',
                r'\b(Herzog\s+(?:von|zu)\s+\w+)\b',
            ],
            'Italian': [
                r'\b(Re|Regina|Principe|Principessa|Duca|Duchessa)\b',
                r'\b(Marchese|Marchesa|Conte|Contessa|Barone|Baronessa)\b',
                r'\b(Signore|Signora|Cavaliere)\b',
            ],
            'Spanish': [
                r'\b(Rey|Reina|Príncipe|Princesa|Duque|Duquesa)\b',
                r'\b(Marqués|Marquesa|Conde|Condesa|Barón|Baronesa)\b',
                r'\b(Señor|Señora|Caballero|Hidalgo)\b',
            ],
            'Portuguese': [
                r'\b(Rei|Rainha|Príncipe|Princesa|Duque|Duquesa)\b',
                r'\b(Marquês|Marquesa|Conde|Condessa|Barão|Baronesa)\b',
                r'\b(Senhor|Senhora|Cavaleiro|Fidalgo)\b',
            ],
            'Latin': [
                r'\b(Rex|Regina|Princeps|Dux|Comes|Baro)\b',
            ],
            'Norse': [
                r'\b(Jarl|Thane)\b',
            ]
        }

    def is_likely_french(self, text: str) -> bool:
        """Detect if text is likely French."""
        french_indicators = [
            r'\b(de|du|des|le|la|les|et|pour|sur|dans|avec|père|mère)\b',
            r'[àâäéèêëïîôùûü]',  # French accents
            r'\b(commerce|maitre|capitaine|lieutenant|voyageur)\b'
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in french_indicators)

    def is_likely_german(self, text: str) -> bool:
        """Detect if text is likely German."""
        german_indicators = [
            r'\b(der|die|das|und|von|zu|in|auf|für|mit|vater|mutter)\b',
            r'[äöüß]',  # German characters
            r'\b(hauptmann|leutnant|kaufmann)\b'
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in german_indicators)

    def is_likely_spanish(self, text: str) -> bool:
        """Detect if text is likely Spanish."""
        spanish_indicators = [
            r'\b(el|la|los|las|de|del|y|para|con|padre|madre)\b',
            r'[áéíóúñ]',  # Spanish accents
            r'\b(capitán|teniente|comerciante)\b'
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in spanish_indicators)

    def is_likely_italian(self, text: str) -> bool:
        """Detect if text is likely Italian."""
        italian_indicators = [
            r'\b(il|la|i|le|di|del|della|e|per|con|padre|madre)\b',
            r'\b(capitano|tenente|commerciante)\b'
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in italian_indicators)

    def is_likely_portuguese(self, text: str) -> bool:
        """Detect if text is likely Portuguese."""
        portuguese_indicators = [
            r'\b(o|a|os|as|de|do|da|e|para|com|pai|mãe)\b',
            r'[ãõâêôáéíóú]',  # Portuguese accents
            r'\b(capitão|tenente|comerciante)\b'
        ]
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in portuguese_indicators)

    def detect_language(self, text: str) -> str:
        """Detect the most likely language of text."""
        if self.is_likely_french(text):
            return "French"
        elif self.is_likely_german(text):
            return "German"
        elif self.is_likely_spanish(text):
            return "Spanish"
        elif self.is_likely_italian(text):
            return "Italian"
        elif self.is_likely_portuguese(text):
            return "Portuguese"
        else:
            return "English"

    def extract_titles_from_name(self, name_value: str) -> list:
        """Extract nobility titles from a name string."""
        found_titles = []

        for language, patterns in self.nobility_titles.items():
            for pattern in patterns:
                matches = re.finditer(pattern, name_value, re.IGNORECASE)
                for match in matches:
                    title = match.group(1) if match.groups() else match.group(0)
                    found_titles.append({
                        'title': title,
                        'language': language,
                        'full_name': name_value,
                        'match': match.group(0)
                    })

        return found_titles

    def parse_gedcom_file(self, filepath: str):
        """Parse GEDCOM file and extract multilingual patterns."""
        # Try multiple encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    lines = f.readlines()
                break
            except UnicodeDecodeError:
                continue
        else:
            print(f"Warning: Could not decode {filepath}, skipping...")
            return

        current_record = None
        current_tag = None
        current_name = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Parse GEDCOM line structure
            parts = line.split(' ', 2)
            if len(parts) < 2:
                continue

            level = parts[0]
            tag = parts[1]
            value = parts[2] if len(parts) > 2 else ""

            # Extract nobility titles from NAME fields
            if tag == 'NAME':
                current_name = value.strip()
                titles = self.extract_titles_from_name(current_name)
                for title_info in titles:
                    lang = title_info['language']
                    title = title_info['title']
                    self.name_titles[lang].add(title)
                    # Store example with full name context (limit to 10 examples per title)
                    if len([ex for ex in self.title_examples[title] if ex == current_name]) < 10:
                        self.title_examples[title].append(current_name)

            # Also check GIVN and SURN fields
            elif tag in ['GIVN', 'SURN'] and value:
                titles = self.extract_titles_from_name(value)
                for title_info in titles:
                    lang = title_info['language']
                    title = title_info['title']
                    self.name_titles[lang].add(title)
                    if len([ex for ex in self.title_examples[title] if ex == value]) < 10:
                        self.title_examples[title].append(value)

            # Extract occupations
            if tag == 'OCCU':
                if value:
                    lang = self.detect_language(value)
                    self.occupations[lang].add(value.strip())
                    self.all_text.append((value, lang))

            # Extract event types
            elif tag == 'TYPE' and current_tag == 'EVEN':
                lang = self.detect_language(value)
                self.event_types[lang].add(value.strip())
                self.all_text.append((value, lang))

            # Extract places
            elif tag == 'PLAC':
                lang = self.detect_language(value)
                self.places[lang].add(value.strip())

            # Track current context
            if tag == 'EVEN':
                current_tag = 'EVEN'
            elif level == '0':
                current_tag = None
                current_name = None

    def find_equivalencies(self):
        """Find potential equivalencies across languages."""
        equivalencies = []

        # Military rank equivalencies
        military_ranks = {
            "English": ["Lieutenant", "Captain", "Major", "Colonel", "General", "Private", "Sergeant"],
            "French": ["Lieutenant", "Capitaine", "Major", "Colonel", "Général", "Soldat", "Sergent"],
            "German": ["Leutnant", "Hauptmann", "Major", "Oberst", "General", "Soldat", "Feldwebel"],
            "Spanish": ["Teniente", "Capitán", "Mayor", "Coronel", "General", "Soldado", "Sargento"],
            "Italian": ["Tenente", "Capitano", "Maggiore", "Colonnello", "Generale", "Soldato", "Sergente"],
            "Portuguese": ["Tenente", "Capitão", "Major", "Coronel", "General", "Soldado", "Sargento"]
        }

        # Family relationships
        relationships = {
            "English": ["Father", "Mother", "Son", "Daughter", "Brother", "Sister", "Husband", "Wife"],
            "French": ["Père", "Mère", "Fils", "Fille", "Frère", "Sœur", "Mari", "Femme"],
            "German": ["Vater", "Mutter", "Sohn", "Tochter", "Bruder", "Schwester", "Ehemann", "Ehefrau"],
            "Spanish": ["Padre", "Madre", "Hijo", "Hija", "Hermano", "Hermana", "Esposo", "Esposa"],
            "Italian": ["Padre", "Madre", "Figlio", "Figlia", "Fratello", "Sorella", "Marito", "Moglie"],
            "Portuguese": ["Pai", "Mãe", "Filho", "Filha", "Irmão", "Irmã", "Marido", "Esposa"]
        }

        # Event types
        event_types = {
            "English": ["Birth", "Death", "Marriage", "Baptism", "Burial", "Residence", "Occupation",
                       "Military Service", "Education", "Immigration", "Emigration"],
            "French": ["Naissance", "Décès", "Mariage", "Baptême", "Inhumation", "Résidence", "Profession",
                      "Service Militaire", "Éducation", "Immigration", "Émigration"],
            "German": ["Geburt", "Tod", "Hochzeit", "Taufe", "Beerdigung", "Wohnsitz", "Beruf",
                      "Militärdienst", "Bildung", "Einwanderung", "Auswanderung"],
            "Spanish": ["Nacimiento", "Defunción", "Matrimonio", "Bautismo", "Entierro", "Residencia", "Ocupación",
                       "Servicio Militar", "Educación", "Inmigración", "Emigración"],
            "Italian": ["Nascita", "Morte", "Matrimonio", "Battesimo", "Sepoltura", "Residenza", "Occupazione",
                       "Servizio Militare", "Istruzione", "Immigrazione", "Emigrazione"],
            "Portuguese": ["Nascimento", "Óbito", "Casamento", "Batismo", "Sepultamento", "Residência", "Ocupação",
                          "Serviço Militar", "Educação", "Imigração", "Emigração"]
        }

        # Titles/honorifics
        titles = {
            "English": ["Mr.", "Mrs.", "Miss", "Dr.", "Rev.", "Sir", "Lady", "Lord"],
            "French": ["M.", "Mme", "Mlle", "Dr", "Rév.", "Sieur", "Dame", "Seigneur"],
            "German": ["Herr", "Frau", "Fräulein", "Dr.", "Pfarrer", "Herr", "Frau", "Herr"],
            "Spanish": ["Sr.", "Sra.", "Srta.", "Dr.", "Rev.", "Señor", "Señora", "Señor"],
            "Italian": ["Sig.", "Sig.ra", "Sig.na", "Dott.", "Rev.", "Signore", "Signora", "Signore"],
            "Portuguese": ["Sr.", "Sra.", "Srta.", "Dr.", "Rev.", "Senhor", "Senhora", "Senhor"]
        }

        # Occupations
        occupations = {
            "English": ["Farmer", "Merchant", "Teacher", "Doctor", "Lawyer", "Carpenter", "Blacksmith", "Postmaster"],
            "French": ["Cultivateur", "Commerçant", "Enseignant", "Médecin", "Avocat", "Charpentier", "Forgeron", "Maître de poste"],
            "German": ["Bauer", "Kaufmann", "Lehrer", "Arzt", "Anwalt", "Zimmermann", "Schmied", "Postmeister"],
            "Spanish": ["Agricultor", "Comerciante", "Maestro", "Médico", "Abogado", "Carpintero", "Herrero", "Jefe de correos"],
            "Italian": ["Agricoltore", "Commerciante", "Insegnante", "Medico", "Avvocato", "Falegname", "Fabbro", "Direttore postale"],
            "Portuguese": ["Agricultor", "Comerciante", "Professor", "Médico", "Advogado", "Carpinteiro", "Ferreiro", "Chefe dos correios"]
        }

        return {
            "Military Ranks": military_ranks,
            "Relationships": relationships,
            "Event Types": event_types,
            "Titles": titles,
            "Occupations": occupations
        }

    def print_analysis(self):
        """Print comprehensive analysis."""
        print("\n" + "="*80)
        print("MULTILINGUAL ANALYSIS OF GEDCOM DATA")
        print("="*80)

        print("\n### NOBILITY TITLES FOUND IN NAMES ###")
        print("\nThese are titles extracted from NAME, GIVN, and SURN fields:")
        for lang, items in sorted(self.name_titles.items()):
            if items:
                print(f"\n{lang}:")
                for item in sorted(items):
                    # Show examples for each title (limit to 3)
                    examples = self.title_examples.get(item, [])[:3]
                    print(f"  - {item}")
                    for example in examples:
                        print(f"      Example: {example}")

        print("\n### OCCUPATIONS FOUND IN DATA ###")
        for lang, items in sorted(self.occupations.items()):
            if items:
                print(f"\n{lang}:")
                for item in sorted(items)[:20]:  # Limit output
                    print(f"  - {item}")

        print("\n### EVENT TYPES FOUND IN DATA ###")
        for lang, items in sorted(self.event_types.items()):
            if items:
                print(f"\n{lang}:")
                for item in sorted(items):
                    print(f"  - {item}")

        print("\n### SAMPLE PLACES BY LANGUAGE ###")
        for lang, items in sorted(self.places.items()):
            if items:
                print(f"\n{lang}:")
                for item in sorted(list(items)[:10]):  # Show first 10
                    print(f"  - {item}")

        print("\n" + "="*80)
        print("COMPREHENSIVE EQUIVALENCY TABLE")
        print("="*80)

        equivalencies = self.find_equivalencies()

        for category, langs in equivalencies.items():
            print(f"\n### {category.upper()} ###")
            print()

            # Determine max length for each language
            max_len = max(len(max(langs[lang], key=len)) if langs[lang] else 0
                         for lang in langs.keys())

            # Print header
            header = "| " + " | ".join(f"{lang:^{max_len}}" for lang in sorted(langs.keys())) + " |"
            separator = "|" + "|".join("-" * (max_len + 2) for _ in langs.keys()) + "|"
            print(separator)
            print(header)
            print(separator)

            # Print rows
            max_rows = max(len(langs[lang]) for lang in langs.keys())
            lang_lists = {lang: list(langs[lang]) for lang in sorted(langs.keys())}

            for i in range(max_rows):
                row = []
                for lang in sorted(langs.keys()):
                    if i < len(lang_lists[lang]):
                        row.append(f"{lang_lists[lang][i]:^{max_len}}")
                    else:
                        row.append(" " * max_len)
                print("| " + " | ".join(row) + " |")
            print(separator)


def main():
    """Main execution function."""
    analyzer = MultilingualAnalyzer()

    # Analyze all GEDCOM files
    gedcom_dir = Path("/home/user/Python-Scripts/GedMerge/GEDCOM")
    gedcom_files = list(gedcom_dir.glob("*.ged")) + list(gedcom_dir.glob("*.GED"))

    print(f"Analyzing {len(gedcom_files)} GEDCOM files...")
    for gedcom_file in gedcom_files:
        print(f"  - {gedcom_file.name}")
        analyzer.parse_gedcom_file(str(gedcom_file))

    analyzer.print_analysis()

    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)
    print(f"\nTotal text samples analyzed: {len(analyzer.all_text)}")
    print("\nLanguages detected:")
    lang_counts = defaultdict(int)
    for text, lang in analyzer.all_text:
        lang_counts[lang] += 1

    for lang, count in sorted(lang_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {lang}: {count} occurrences")


if __name__ == "__main__":
    main()
