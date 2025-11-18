# Name Parser Utilities

Comprehensive name parsing for genealogy data that handles complex naming conventions.

## Features

### 1. Surname Particle Recognition

Correctly identifies noble surname particles in multiple languages:

- **German**: `von`, `vom`, `zu`, `zur`, `zum`, `im`, `am`
- **French**: `de`, `du`, `des`, `de la`, `de l'`, `d'`
- **Dutch**: `van`, `van de`, `van den`, `van der`, `ter`, `te`
- **Italian**: `di`, `da`, `del`, `della`, `degli`
- **Spanish/Portuguese**: `del`, `de los`, `dos`, `das`

**Example**: "Frau Gerberga von Franconia" correctly parses to:
- Prefix: "Frau"
- Given: "Gerberga"
- Surname: "von Franconia" (NOT a nickname!)

### 2. Complex GIVN Field Parsing

Extracts multiple components from GIVN fields:
- Given names with ordinals (Thomas II, Edward III)
- Quoted epithets/nicknames ('The Wise', 'The Great')
- Nobility titles as suffixes (1st Baron, Duke of York)

**Example**: "Thomas II 'The Wise' 1st Baron" parses to:
- Given: "Thomas II"
- Ordinal: "II"
- Nickname: "The Wise"
- Suffix: "1st Baron"

### 3. Honorific Prefix Detection

Recognizes honorific prefixes in multiple languages:
- **English**: Sir, Lady, Lord, Dame, Mr, Mrs, Miss, Dr, Rev
- **German**: Herr, Frau, Fräulein, Freiherr
- **French**: M, Mme, Mlle, Sieur, Dame, Seigneur
- **Spanish**: Sr, Sra, Don, Doña, Señor, Señora

### 4. Nobility Title Suffixes

Extracts nobility titles that should be in suffix field:
- Ordinal titles: "1st Baron", "10th Earl of Essex"
- Non-ordinal titles: "Duke of York", "Heiress of Powys"
- Multilingual: English, French, German patterns

## Usage

### Basic Parsing

```python
from gedmerge.utils.name_parser import NameParser

# Parse a GIVN field with complex content
result = NameParser.parse_givn_field("Thomas II 'The Wise' 1st Baron")
print(f"Given: {result.given}")        # Thomas II
print(f"Nickname: {result.nickname}")  # The Wise
print(f"Suffix: {result.suffix}")      # 1st Baron
```

### Detecting Misclassified Surnames

```python
# Check if a "nickname" field actually contains a surname
if NameParser.has_surname_particle("von Franconia"):
    # This is actually a surname, not a nickname
    result = NameParser.parse_field_with_surname_particle(
        "Frau Gerberga von Franconia",
        field_type='NICK'
    )
    print(f"Prefix: {result.prefix}")    # Frau
    print(f"Given: {result.given}")      # Gerberga
    print(f"Surname: {result.surname}")  # von Franconia
```

### Normalizing Name Components

```python
# Fix misclassified fields automatically
result = NameParser.normalize_name_components(
    given="Thomas II 'The Wise' 1st Baron",
    surname="Smith",
    nickname="von Franconia"  # Incorrectly classified
)

# Results in:
#   given: "Thomas II"
#   ordinal: "II"
#   surname: "von Franconia"  # Moved from nickname
#   nickname: "The Wise"       # Extracted from given
#   suffix: "1st Baron"        # Extracted from given
```

### Parsing Full NAME Fields

```python
# Parse GEDCOM NAME format: "Given /Surname/ Suffix"
result = NameParser.parse_name_field(
    "Sir Thomas II 'The Wise' /Smith/ 1st Baron"
)

print(f"Prefix: {result.prefix}")    # Sir
print(f"Given: {result.given}")      # Thomas II
print(f"Surname: {result.surname}")  # Smith
print(f"Nickname: {result.nickname}")# The Wise
print(f"Suffix: {result.suffix}")    # 1st Baron
```

## Common Issues Fixed

### Issue 1: Surnames Misclassified as Nicknames

**Problem**: "von Franconia" tagged as {NICK} instead of being recognized as a surname.

**Solution**:
```python
# Before: nickname="von Franconia"
result = NameParser.normalize_name_components(nickname="von Franconia")
# After: surname="von Franconia", nickname=None
```

### Issue 2: Complex GIVN Fields Not Parsed

**Problem**: "Thomas II 'The Wise' 1st Baron" stored as-is in GIVN without extracting components.

**Solution**:
```python
result = NameParser.parse_givn_field("Thomas II 'The Wise' 1st Baron")
# Extracts: given="Thomas II", nickname="The Wise", suffix="1st Baron"
```

### Issue 3: Prefixes in Wrong Fields

**Problem**: "Frau" stored with given name instead of in prefix field.

**Solution**:
```python
result = NameParser.parse_field_with_surname_particle("Frau Gerberga von Franconia")
# Extracts: prefix="Frau", given="Gerberga", surname="von Franconia"
```

## API Reference

### `NameParser` Class Methods

#### `parse_givn_field(givn_value: str) -> ParsedName`
Parse GIVN field with ordinals, epithets, and titles.

#### `parse_name_field(name_value: str) -> ParsedName`
Parse full NAME field in GEDCOM format.

#### `parse_field_with_surname_particle(field_value: str, field_type: str) -> ParsedName`
Parse field that may contain misclassified surname particles.

#### `normalize_name_components(...) -> ParsedName`
Normalize and fix misclassified name components.

#### `is_surname_particle(word: str) -> bool`
Check if word is a noble surname particle (von, de, van, etc.).

#### `is_prefix(word: str) -> bool`
Check if word is an honorific prefix (Frau, Sir, Lady, etc.).

#### `has_surname_particle(text: str) -> bool`
Check if text contains any surname particle.

### `ParsedName` Data Class

Fields:
- `given`: Given name (may include ordinal)
- `surname`: Surname (may include particles)
- `prefix`: Honorific prefix
- `suffix`: Nobility title or other suffix
- `nickname`: Nickname or epithet
- `ordinal`: Roman numeral ordinal (II, III, etc.)
- `epithets`: List of all quoted epithets

## Examples from Real Data

### Medieval European Names

```python
# German nobility
NameParser.parse_name_field("Herzog Heinrich /von Bayern/")
# Prefix: None, Given: Herzog Heinrich, Surname: von Bayern

# French nobility
NameParser.parse_name_field("Dame Marie /de France/")
# Prefix: Dame, Given: Marie, Surname: de France

# English nobility
NameParser.parse_name_field("Sir Thomas /Beaufort/ 1st Earl of Dorset")
# Prefix: Sir, Given: Thomas, Surname: Beaufort, Suffix: 1st Earl of Dorset
```

### Complex Titles and Epithets

```python
# King with epithet
NameParser.parse_givn_field("Edward I 'Longshanks'")
# Given: Edward I, Ordinal: I, Nickname: Longshanks

# Multiple titles
NameParser.parse_givn_field("William 'The Conqueror' King of England")
# Given: William, Nickname: The Conqueror, Suffix: King of England
```

## Testing

Run the test suite:
```bash
python test_name_parsing_examples.py
```

Or use pytest:
```bash
pytest tests/test_name_parser.py -v
```

## Notes

- **Language Support**: Patterns cover English, French, German, Italian, Spanish, Portuguese, Dutch
- **Case Insensitive**: All particle and prefix matching is case-insensitive
- **GEDCOM Compliant**: Handles standard GEDCOM NAME format with /Surname/ notation
- **Preserves Information**: All parsing is non-destructive; original components are preserved
