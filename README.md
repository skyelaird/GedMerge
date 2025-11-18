# GEDMerge

A powerful tool to find and merge duplicate people in GEDCOM genealogy files.

## Overview

GEDMerge is designed to help genealogists clean up their family tree data by automatically detecting and merging duplicate individual records in GEDCOM files. The tool uses advanced matching algorithms including fuzzy string matching and phonetic comparison to identify potential duplicates with high accuracy.

## Features

- **GEDCOM Parsing**: Full support for GEDCOM 5.5 and 5.5.1 formats
- **Duplicate Detection**: Advanced algorithms to find potential duplicate individuals
- **Smart Merging**: Intelligent merging that preserves all relevant data
- **Data Integrity**: Maintains relationships between individuals and families
- **CLI Interface**: Easy-to-use command-line interface

## Project Structure

```
GedMerge/
├── gedmerge/
│   ├── core/           # Core data models and GEDCOM parsing
│   ├── matching/       # Duplicate detection algorithms
│   ├── merge/          # Merge logic and strategies
│   ├── ui/             # User interface (CLI)
│   ├── utils/          # Utility functions
│   └── data/           # Data storage and caching
├── tests/              # Test suite
├── GEDCOM/             # Sample GEDCOM files
├── pyproject.toml      # Project configuration and dependencies
└── README.md           # This file
```

## Installation

### From Source

```bash
cd GedMerge
pip install -e .
```

### With Development Dependencies

```bash
pip install -e ".[dev]"
```

## Dependencies

- **python-gedcom**: GEDCOM file parsing
- **rapidfuzz**: Fast fuzzy string matching
- **phonetics**: Phonetic matching algorithms (Soundex, Metaphone, etc.)
- **pytest**: Testing framework (dev dependency)

## Quick Start

### Load and Analyze a GEDCOM File

```bash
gedmerge analyze path/to/your/file.ged
```

This will display basic statistics about your GEDCOM file including:
- Number of individuals
- Number of families
- Date range
- Geographic coverage

### Find Duplicates

```bash
gedmerge find-duplicates path/to/your/file.ged
```

### Merge Duplicates

```bash
gedmerge merge path/to/your/file.ged --output merged.ged
```

## Name Preprocessing for Duplicate Detection

**IMPORTANT**: Before running duplicate detection, names must be preprocessed to ensure consistent "apples to apples" comparisons.

See [NAMING_CONVENTIONS.md](../NAMING_CONVENTIONS.md) for complete details.

### Quick Overview

1. **NN Convention**: Use `NN` for missing given names (genealogy standard)
2. **Language Codes**: Set ISO 639-1 codes (`en`, `fr`, `de`) for all names
3. **Clean Variants**: Separate embedded variants like `Margaret [Marguerite]` into separate name records
4. **Remove Placeholders**: Remove generic placeholders like `EndofLine`, `Unknown`
5. **Preserve Meaningful Data**: Keep mother's maiden names even if different from children

### Preprocessing Workflow

```bash
# Step 1: Structural cleanup (NN convention, placeholders)
python ../preprocess_names_for_matching.py database.rmtree --report
python ../preprocess_names_for_matching.py database.rmtree --execute

# Step 2: Language analysis and variant separation
python ../analyze_name_structure.py database.rmtree --check-language
python ../analyze_name_structure.py database.rmtree --fix-variants --execute

# Step 3: NOW ready for duplicate detection
gedmerge find-duplicates database.rmtree
```

### RootsMagic Compatibility

✅ **Language codes are safe** - The `NameTable.Language` field is a standard RootsMagic field and will NOT break your database.

## Development

### Running Tests

```bash
pytest
```

### Running Tests with Coverage

```bash
pytest --cov=gedmerge --cov-report=html
```

## Roadmap

### Phase 1: Foundation (Current)
- [x] Project setup and structure
- [x] GEDCOM parser
- [x] Core data models
- [x] Basic CLI
- [ ] Unit tests

### Phase 2: Duplicate Detection
- [ ] Name matching algorithms
- [ ] Date/place comparison
- [ ] Relationship analysis
- [ ] Scoring system

### Phase 3: Merging Logic
- [ ] Merge strategies
- [ ] Conflict resolution
- [ ] Data preservation
- [ ] Undo capability

### Phase 4: User Interface
- [ ] Interactive CLI
- [ ] Review and approve duplicates
- [ ] Batch operations
- [ ] Progress tracking

### Phase 5: Advanced Features
- [ ] Machine learning for matching
- [ ] Custom matching rules
- [ ] Performance optimization
- [ ] Export reports

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - See LICENSE file for details

## Acknowledgments

- GEDCOM format specification by The Church of Jesus Christ of Latter-day Saints
- python-gedcom library contributors
- Genealogy community for feature suggestions and testing

## Support

For issues, questions, or suggestions, please open an issue on the project repository.
