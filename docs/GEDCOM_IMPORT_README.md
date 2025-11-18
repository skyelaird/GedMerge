# GEDCOM Import Workflow

This guide explains how to safely import GEDCOM data into your RootsMagic database.

## Overview

The workflow has two main phases:

1. **Clean the database** - Remove duplicates and placeholders
2. **Import GEDCOM data** - Add new people while avoiding duplicates

## Prerequisites

- Python 3.11+
- RootsMagic .rmtree database file
- GEDCOM file to import
- **IMPORTANT: Always work on a backup copy of your database!**

## Workflow

### Step 1: Clean the Database (Optional but Recommended)

Before importing, clean up your existing database to remove duplicates and placeholder entries.

#### 1a. Clean Unnamed/Placeholder People

```bash
# Dry run - preview what would be deleted
python cleanup_unnamed_people.py database.rmtree --dry-run

# Actually delete (requires confirmation)
python cleanup_unnamed_people.py database.rmtree --execute
```

This removes:
- Unnamed people without named ancestors
- "MRS" placeholder names
- "EndofLine" surname-only parents

#### 1b. Find and Merge Duplicates

```bash
# Dry run - find potential duplicates
python find_and_merge_duplicates.py database.rmtree --dry-run

# Auto-merge high-confidence duplicates (>= 90%)
python find_and_merge_duplicates.py database.rmtree --auto-merge

# Interactive mode - review each match
python find_and_merge_duplicates.py database.rmtree --interactive
```

### Step 2: Import GEDCOM Data

The import tool has **automatic backup** enabled by default and multiple import modes:

#### Import Modes

**Dry Run (Default - Safe)**
```bash
# Preview import without making changes
python import_gedcom_to_rmtree.py database.rmtree source.ged --dry-run
```

**Skip Duplicates**
```bash
# Only add new people, skip anyone who already exists
python import_gedcom_to_rmtree.py database.rmtree source.ged --skip-duplicates
```

**Interactive Mode (Recommended)**
```bash
# Review each potential duplicate and decide
python import_gedcom_to_rmtree.py database.rmtree source.ged --interactive
```

**Auto-Merge**
```bash
# Automatically merge high-confidence matches (>= 90%)
python import_gedcom_to_rmtree.py database.rmtree source.ged --auto-merge

# Custom thresholds
python import_gedcom_to_rmtree.py database.rmtree source.ged --auto-merge \
  --match-confidence 60 --auto-merge-threshold 85
```

**Force Add (Dangerous)**
```bash
# Add everyone as new (creates duplicates!)
python import_gedcom_to_rmtree.py database.rmtree source.ged --force-add
```

## Safety Features

### Automatic Backups

By default, the import tool creates a timestamped backup before making any changes:

```
database.rmtree.backup_20231116_143022
```

To restore from a backup:
```bash
cp database.rmtree.backup_20231116_143022 database.rmtree
```

To disable automatic backup (not recommended):
```bash
python import_gedcom_to_rmtree.py database.rmtree source.ged --no-backup
```

### Dry Run Mode

**Always start with dry-run** to preview what would happen:

```bash
python import_gedcom_to_rmtree.py database.rmtree source.ged --dry-run
```

This shows:
- How many people would be added
- How many duplicates were found
- What would be merged

### Confirmation Prompts

For any operation that modifies the database, you must type 'yes' to confirm.

## Recommended Workflow

### For First-Time Import

```bash
# 1. Make a manual backup
cp database.rmtree database.rmtree.backup_manual

# 2. Clean the database (optional)
python cleanup_unnamed_people.py database.rmtree --dry-run
python find_and_merge_duplicates.py database.rmtree --dry-run

# 3. Preview GEDCOM import
python import_gedcom_to_rmtree.py database.rmtree source.ged --dry-run

# 4. Import with interactive mode
python import_gedcom_to_rmtree.py database.rmtree source.ged --interactive

# 5. Verify in RootsMagic
# Open database.rmtree in RootsMagic and verify the import
```

### For Subsequent Imports

```bash
# Skip duplicates to only add new people
python import_gedcom_to_rmtree.py database.rmtree new_source.ged --skip-duplicates
```

## Duplicate Detection

The import tool uses the following criteria to detect duplicates:

- **Name matching**: Given name + surname comparison
- **Sex matching**: Gender must match
- **Confidence scoring**: 0-100% confidence score

Confidence threshold (default: 70%):
- Below threshold: Not considered a duplicate
- 70-89%: Medium confidence (ask in interactive mode)
- 90%+: High confidence (auto-merge in auto-merge mode)

## Troubleshooting

### Import Failed

Check the error message and:
1. Verify GEDCOM file is valid
2. Check database isn't locked by RootsMagic
3. Review backup files

### Too Many Duplicates Found

Lower the confidence threshold:
```bash
python import_gedcom_to_rmtree.py database.rmtree source.ged --interactive --match-confidence 80
```

### Want to Start Over

Restore from backup:
```bash
# Find your backup
ls -lt database.rmtree.backup_*

# Restore it
cp database.rmtree.backup_20231116_143022 database.rmtree
```

## Example Session

```bash
$ python import_gedcom_to_rmtree.py family.rmtree newdata.ged --interactive

Creating backup: family.rmtree.backup_20231116_143022
✓ Backup created successfully

Loading GEDCOM file: newdata.ged
✓ Loaded 150 persons and 45 families

Opening database: family.rmtree
✓ Database currently has 500 persons and 180 families

================================================================================
WARNING: This will modify your database!
================================================================================
Database: family.rmtree
GEDCOM:   newdata.ged
Mode:     interactive
Backup:   family.rmtree.backup_20231116_143022

Proceed with import? (type 'yes' to continue): yes

================================================================================
IMPORTING PERSONS
================================================================================
Mode: interactive
Total persons to import: 150

  ✓ Added John /Smith/ as person 501
  ✓ Added Mary /Jones/ as person 502

  Potential duplicate found for William /Brown/
  Existing person: ID 123
    Name: William /Brown/
  Confidence: 85.0%
  Merge with existing? (y/n/q): y
  ✓ Merged with existing person 123

  ...

================================================================================
IMPORT COMPLETE
================================================================================

Import Statistics:
  Persons in GEDCOM:      150
  - Added as new:         120
  - Merged with existing: 25
  - Skipped (duplicates): 5
  - Failed:               0

  Families in GEDCOM:     45
  - Families added:       40

================================================================================
Import complete!

Backup saved to: family.rmtree.backup_20231116_143022
To restore from backup if needed:
  cp "family.rmtree.backup_20231116_143022" "family.rmtree"
================================================================================
```

## Additional Tools

### View Database Stats

```bash
python -c "
from GedMerge.gedmerge.rootsmagic.adapter import RootsMagicDatabase
db = RootsMagicDatabase('database.rmtree')
stats = db.get_stats()
for key, value in stats.items():
    print(f'{key}: {value}')
db.close()
"
```

### Search for Specific Person

```bash
python -c "
from GedMerge.gedmerge.rootsmagic.adapter import RootsMagicDatabase
db = RootsMagicDatabase('database.rmtree')
persons = db.search_persons_by_name(surname='Smith', given='John')
for p in persons:
    name = p.get_primary_name()
    print(f'ID {p.person_id}: {name.given} /{name.surname}/')
db.close()
"
```

## Support

For issues or questions:
- Check existing tools: `python <tool>.py --help`
- Review backup files before restoring
- Test on a copy of your database first
