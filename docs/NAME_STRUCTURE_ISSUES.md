# Name Structure and Language Issues in RootsMagic Database

## Executive Summary

Analysis of the genealogy database reveals **13,147 structural and language issues** across 61,024 name records (~21.5% of all names have problems).

## Issue Categories

### 1. Structural Issues (6,299 total)

#### Missing Given Names (1,061 records)
People with only surnames, no given names:
- `von Preussen` (should be `[Given] von Preussen`)
- `of Kent` (should be `[Given] of Kent`)
- `Dutil` (should be `[Given] Dutil`)
- `av Zutphen`
- `Vifilsdatter`

**Root cause**: Data entry stored surnames in surname field but left given name blank. These are often nobility or "end of line" placeholder records.

#### Missing Surnames (4,739 records)
People with only given names, no surnames.

**Root cause**: Incomplete data entry or ancient/historical figures who may not have had surnames.

#### Possible Reversed Names (335 records)
Names containing commas, suggesting they may be stored in wrong fields:
- Given: `Richard`, Surname: `Devereux,`
- Given: `Hawise de`, Surname: `Vitré,`
- Given: `Aénor`, Surname: `de Châtellerault,`

**Root cause**: Data imported from "Surname, Given" format and not properly split.

#### Titles in Given Name Field (122 records)
Titles incorrectly stored as part of the given name:
- `Sir Dugald` (should be Given: `Dugald`, Prefix: `Sir`)
- `Lady Elizabeth` (should be Given: `Elizabeth`, Prefix: `Lady`)
- `Lord William Andrew` (should be Given: `William Andrew`, Prefix: `Lord`)
- `Dame Katherine`

**Root cause**: Titles should be in the "Prefix" field, not the given name field.

#### Embedded Language Variants (42 records)

##### Bracket Variants (3 records)
Multiple language variants embedded in single field with brackets:
- Given: `Margaret [Marguerite]` - English/French
- Given: `John[The Younger]` - nickname variant
- Surname: `Bäysen [Bayh]` - German/anglicized

##### Parenthetical Variants (39 records)
Multiple language variants in parentheses:
- `Bernhard (Bernard)` - German/English
- `Konrad (Conrad)` - German/English
- `Geoffroi (Geoffroy)` - variant spellings
- `Finn (Svåse)` - Norwegian variants
- `Dame Katherine (Catharina, Catherine)` - multiple variants
- `Alfred er (dit Le Grand)` - French "called"

**Root cause**: Attempting to show language variants/alternate spellings inline rather than using proper alternate name records with language codes.

### 2. Language Issues (6,848 total)

#### Missing French Language Code (4,144 records)
Names that are clearly French but don't have `language='fr'` set:
- `Jean`, `Marie`, `Pierre`, `Jacques`, `François`
- `Marguerite`, `Françoise`, `Catherine`, `Jeanne`

#### Missing German Language Code (648 records)
Names that are clearly German but don't have `language='de'` set:
- `Wilhelm`, `Friedrich`, `Heinrich`, `Johann`
- `Margarethe`, `Katharina`, `Elisabeth`

#### Alternate Names Without Language Codes (2,056 records)
Alternate name records exist but don't specify which language they represent.

**Root cause**: RootsMagic's language field is not being used properly. When creating alternate name records for different languages, the language field should be set.

## Proper Data Structure

### RootsMagic Name Fields
```
NameTable fields:
- Given: The given name(s)
- Surname: The surname/family name
- Prefix: Titles, honorifics (Sir, Lady, Dr.)
- Suffix: Jr., Sr., III, etc.
- Nickname: Informal names
- Language: ISO 639-1 language code (en, fr, de, etc.)
- NameType: 0=primary name, other values for alternate names
- IsPrimary: Boolean flag
```

### Correct Approach for Multilingual Names

Instead of:
```
PersonID: 12345
  Name 1 (Primary):
    Given: "Margaret [Marguerite]"
    Surname: "Smith"
    Language: NULL
```

Should be:
```
PersonID: 12345
  Name 1 (Primary):
    Given: "Margaret"
    Surname: "Smith"
    Language: "en"

  Name 2 (Alternate):
    Given: "Marguerite"
    Surname: "Smith"
    Language: "fr"
```

### Correct Approach for Titles

Instead of:
```
Given: "Sir Dugald"
Surname: "Campbell"
Prefix: NULL
```

Should be:
```
Given: "Dugald"
Surname: "Campbell"
Prefix: "Sir"
```

### Correct Approach for Missing Names

Instead of:
```
Given: NULL
Surname: "von Preussen"
```

Either:
1. Find the actual given name through research
2. Mark as placeholder/unknown
3. Delete if it's a truly empty record with no connections

## Severity Levels

- **HIGH (1,064)**: Embedded variants, missing given names in primary records
- **MEDIUM (5,235)**: Titles in wrong fields, possibly reversed names, missing surnames
- **LOW (6,848)**: Missing language codes (doesn't affect data integrity, just metadata)

## Solution: analyze_name_structure.py

The script `analyze_name_structure.py` can:

1. **Analyze** all name records and categorize issues
2. **Report** on specific issue types with examples
3. **Fix** embedded variants by:
   - Extracting bracketed/parenthetical variants
   - Cleaning the main name record
   - Creating proper alternate name records
   - Setting appropriate language codes

### Usage

```bash
# Analyze all names (read-only)
python3 analyze_name_structure.py database.rmtree

# Show detailed report for specific issue type
python3 analyze_name_structure.py database.rmtree --detail embedded_variant_bracket

# Preview fixes for embedded variants (dry run)
python3 analyze_name_structure.py database.rmtree --fix-variants --dry-run

# Actually fix embedded variants (makes changes!)
python3 analyze_name_structure.py database.rmtree --fix-variants --execute
```

## Recommendations

### Priority 1: Fix Embedded Variants
- Run the fix-variants command to properly split language variants into separate records
- This affects 42 records and is HIGH/MEDIUM severity

### Priority 2: Fix Titles
- Move titles from given name field to prefix field
- Affects 122 records (MEDIUM severity)

### Priority 3: Review Missing Given Names
- 1,061 records need manual review
- Many are likely "end of line" placeholder records that should be deleted
- Use `cleanup_unnamed_people.py` script to identify candidates

### Priority 4: Add Language Codes
- Set language codes for alternate name records
- Lower priority as it doesn't affect data integrity, just improves metadata

### Priority 5: Review Reversed Names
- 335 records need manual inspection
- Remove trailing commas from surnames

## Technical Details

The analysis script uses pattern matching to detect:
- Bracket patterns: `\[([^\]]+)\]`
- Parenthetical patterns: `\(([^\)]+)\)` (excluding birth names like "née")
- French name patterns: Jean, Marie, Pierre, Marguerite, etc.
- German name patterns: Wilhelm, Friedrich, Heinrich, etc.
- Title patterns: `^(MRS?\.?|MS\.?|MISS|DR\.?|REV\.?|SIR|LADY|LORD|DAME)\s+`

## Files

- `analyze_name_structure.py` - Main analysis and fix script
- `cleanup_unnamed_people.py` - Remove unnamed placeholder records
- `NAME_STRUCTURE_ISSUES.md` - This documentation

## Database Schema Reference

```sql
CREATE TABLE NameTable (
    NameID INTEGER PRIMARY KEY,
    OwnerID INTEGER NOT NULL,  -- PersonID
    Surname TEXT,
    Given TEXT,
    Prefix TEXT,              -- For titles: Sir, Lady, Dr.
    Suffix TEXT,              -- For suffixes: Jr., III
    Nickname TEXT,
    NameType INTEGER DEFAULT 0,
    Date TEXT,
    SortDate INTEGER,
    IsPrimary BOOLEAN DEFAULT 0,
    IsPrivate BOOLEAN DEFAULT 0,
    Proof INTEGER DEFAULT 0,
    Sentence TEXT,
    Note TEXT,
    BirthYear INTEGER,
    DeathYear INTEGER,
    Display INTEGER DEFAULT 0,
    Language TEXT,            -- ISO 639-1 code: 'en', 'fr', 'de', etc.
    UTCModDate REAL,
    SurnameMP TEXT,
    GivenMP TEXT,
    NicknameMP TEXT
);
```

## Next Steps

1. Review this analysis with stakeholders
2. Prioritize which issues to fix first
3. Run fixes in test/development database first
4. Validate results
5. Apply to production database
6. Document lessons learned for future data entry
