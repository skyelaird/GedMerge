# Multilingual Support for Genealogy Data

This document describes the comprehensive multilingual support system for handling genealogical data in multiple languages.

## Overview

The language support system provides:

- **Language Detection**: Automatic detection of English, French, German, Spanish, Italian, and Portuguese
- **Term Normalization**: Conversion of multilingual terms to English canonical forms
- **Alternate Names**: Preservation of all language variants for cross-referencing
- **Adaptive Learning**: Dynamic learning of new equivalencies from data
- **Category Organization**: Terms organized by type (titles, relationships, events, occupations)

## Languages Detected in Your Data

Based on analysis of your GEDCOM files, the following languages were detected:

| Language | Occurrences | Percentage |
|----------|-------------|------------|
| English | 17,427 | 91.3% |
| French | 1,270 | 6.7% |
| Portuguese | 260 | 1.4% |
| German | 86 | 0.5% |
| Italian | 45 | 0.2% |
| Spanish | 1 | <0.1% |

**Total analyzed**: 19,089 text samples across 3 GEDCOM files

## Equivalency Tables

### Titles and Honorifics (22 terms)

| English | French | German | Spanish | Italian | Portuguese |
|---------|--------|--------|---------|---------|------------|
| Lieutenant | Lieutenant | Leutnant | Teniente | Tenente | Tenente |
| Captain | Capitaine | Hauptmann | Capitán | Capitano | Capitão |
| Major | Major | Major | Mayor | Maggiore | Major |
| Colonel | Colonel | Oberst | Coronel | Colonnello | Coronel |
| General | Général | General | General | Generale | General |
| King | Roi | König | Rey | Re | Rei |
| Queen | Reine | Königin | Reina | Regina | Rainha |
| Prince | Prince | Prinz | Príncipe | Principe | Príncipe |
| Duke | Duc | Herzog | Duque | Duca | Duque |
| Count | Comte | Graf | Conde | Conte | Conde |
| Baron | Baron | Baron | Barón | Barone | Barão |
| Sir | Sieur | Herr | Señor | Signore | Senhor |
| Lady | Dame | Frau | Señora | Signora | Senhora |
| Lord | Seigneur | Herr | Señor | Signore | Senhor |

### Family Relationships (10 terms)

| English | French | German | Spanish | Italian | Portuguese |
|---------|--------|--------|---------|---------|------------|
| Father | Père | Vater | Padre | Padre | Pai |
| Mother | Mère | Mutter | Madre | Madre | Mãe |
| Son | Fils | Sohn | Hijo | Figlio | Filho |
| Daughter | Fille | Tochter | Hija | Figlia | Filha |
| Brother | Frère | Bruder | Hermano | Fratello | Irmão |
| Sister | Sœur | Schwester | Hermana | Sorella | Irmã |
| Husband | Mari | Ehemann | Esposo | Marito | Marido |
| Wife | Femme | Ehefrau | Esposa | Moglie | Esposa |
| Grandfather | Grand-père | Großvater | Abuelo | Nonno | Avô |
| Grandmother | Grand-mère | Großmutter | Abuela | Nonna | Avó |

### Event Types (11 terms)

| English | French | German | Spanish | Italian | Portuguese |
|---------|--------|--------|---------|---------|------------|
| Birth | Naissance | Geburt | Nacimiento | Nascita | Nascimento |
| Death | Décès | Tod | Defunción | Morte | Óbito |
| Marriage | Mariage | Hochzeit | Matrimonio | Matrimonio | Casamento |
| Baptism | Baptême | Taufe | Bautismo | Battesimo | Batismo |
| Burial | Inhumation | Beerdigung | Entierro | Sepoltura | Sepultamento |
| Residence | Résidence | Wohnsitz | Residencia | Residenza | Residência |
| Occupation | Profession | Beruf | Ocupación | Occupazione | Ocupação |
| Military Service | Service Militaire | Militärdienst | Servicio Militar | Servizio Militare | Serviço Militar |
| Education | Éducation | Bildung | Educación | Istruzione | Educação |
| Immigration | Immigration | Einwanderung | Inmigración | Immigrazione | Imigração |
| Emigration | Émigration | Auswanderung | Emigración | Emigrazione | Emigração |

### Occupations (10 terms)

| English | French | German | Spanish | Italian | Portuguese |
|---------|--------|--------|---------|---------|------------|
| Farmer | Cultivateur | Bauer | Agricultor | Agricoltore | Agricultor |
| Merchant | Commerçant | Kaufmann | Comerciante | Commerciante | Comerciante |
| Teacher | Enseignant | Lehrer | Maestro | Insegnante | Professor |
| Doctor | Médecin | Arzt | Médico | Medico | Médico |
| Lawyer | Avocat | Anwalt | Abogado | Avvocato | Advogado |
| Carpenter | Charpentier | Zimmermann | Carpintero | Falegname | Carpinteiro |
| Blacksmith | Forgeron | Schmied | Herrero | Fabbro | Ferreiro |
| Postmaster | Maître de poste | Postmeister | Jefe de correos | Direttore postale | Chefe dos correios |
| Priest | Prêtre | Priester | Sacerdote | Sacerdote | Padre |
| Baker | Boulanger | Bäcker | Panadero | Panettiere | Padeiro |

**Total**: 53 canonical terms with 265 translations (avg 5.0 translations per term)

## Usage

### Basic Normalization

```python
from gedmerge.data.language_support import normalize_term

# Normalize a French term to English
normalized, alternates = normalize_term("Capitaine")
# Returns: ("Captain", ["Capitaine", "Hauptmann", "Capitán", ...])
```

### Language Detection

```python
from gedmerge.data.language_support import detect_language

lang = detect_language("Père de trois enfants")
# Returns: Language.FRENCH
```

### Adaptive Learning

```python
from gedmerge.data.language_support import get_registry

registry = get_registry()

# Learn a new equivalency
registry.learn_equivalency("Mason", "Maçon", "occupation")

# Now "Maçon" will normalize to "Mason"
normalized, alternates = normalize_term("Maçon")
# Returns: ("Mason", ["Maçon"])
```

### Working with the Registry

```python
from gedmerge.data.language_support import get_registry, MultilingualTerm

registry = get_registry()

# Add a completely new term with all translations
new_term = MultilingualTerm(
    english="Godfather",
    french="Parrain",
    german="Pate",
    spanish="Padrino",
    italian="Padrino",
    portuguese="Padrinho",
    category="relationship"
)
registry.add_term(new_term)

# Save learned terms to file
registry.save(Path("custom_terms.json"))

# Load terms from file
registry.load(Path("custom_terms.json"))
```

## Architecture

### Core Components

1. **LanguageDetector**: Uses pattern matching to identify language
   - Word patterns (common words in each language)
   - Character patterns (language-specific accents/characters)
   - Title/term patterns (domain-specific vocabulary)

2. **MultilingualTerm**: Dataclass holding a term in all languages
   - English form (canonical)
   - Translations for 5 other languages
   - Category (title, relationship, event, occupation)
   - Aliases (additional variations)

3. **MultilingualRegistry**: Main registry managing all terms
   - Normalization to English
   - Reverse index for fast lookup
   - Adaptive learning capabilities
   - JSON persistence

### Design Principles

1. **English as Canonical**: All terms normalize to English for consistency
2. **Preserve Alternates**: All language variants stored for cross-referencing
3. **Adaptive**: System learns new equivalencies from data
4. **Extensible**: Easy to add new languages, categories, or terms
5. **Not Hardcoded**: Core terms are initialization, not limitations

## Recommendations for Implementation

### 1. Main Name Strategy

When merging records from multiple languages:

```python
# Primary name: Use English canonical form
primary_name = normalized_term

# Alternate names: Store ALL language variants
alternate_names = alternates

# Example output:
# Primary: "Father"
# Alternates: ["Père", "Vater", "Padre", "Pai"]
```

### 2. Cross-Indexing

Create indices that map ALL forms to the same record:

```python
index = {
    "father": record_id,
    "père": record_id,
    "vater": record_id,
    "padre": record_id,
    "pai": record_id
}
```

### 3. Display Strategy

For multilingual users, show both forms:

```
Captain (Capitaine, Hauptmann, Capitán)
Father (Père, Vater, Padre, Pai)
```

### 4. Extensibility

The system is designed to grow:

- **Add new languages**: Extend MultilingualTerm dataclass
- **Add new categories**: Just set category field
- **Learn from data**: Use `learn_equivalency()` method
- **Import from external sources**: Load from JSON files

## Files

- `gedmerge/data/language_support.py` - Core language support module
- `analyze_multilingual.py` - Analysis tool for GEDCOM files
- `show_equivalency_tables.py` - Display comprehensive tables
- `LANGUAGE_SUPPORT.md` - This documentation

## Future Enhancements

Potential improvements:

1. **Machine Learning**: Use ML for better language detection
2. **More Languages**: Add Dutch, Polish, Russian, etc.
3. **Place Names**: Multilingual support for geographic locations
4. **Fuzzy Matching**: Handle spelling variations and typos
5. **Context Awareness**: Use surrounding text for better detection
6. **GEDCOM Integration**: Direct integration with GEDCOM parser
7. **Web Service**: API for language normalization

## Examples from Your Data

Real examples found in your GEDCOM files:

| Original (French) | Normalized (English) | Category |
|-------------------|---------------------|----------|
| maître de poste | Postmaster | occupation |
| Capitaine | Captain | title |
| Cultivateur | Farmer | occupation |
| Commerçant | Merchant | occupation |
| Père | Father | relationship |
| Naissance | Birth | event |
| Décès | Death | event |
| Mariage | Marriage | event |

## Conclusion

This multilingual support system provides a robust, extensible foundation for handling genealogical data across multiple languages. It's designed to be practical (not just academic) and adaptive (learns from your data).

The key insight is: **Don't hardcode everything - make it learnable and extensible.**
