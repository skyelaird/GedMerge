# Cleanup Unnamed People Script

This script cleans up unnamed and placeholder people from RootsMagic genealogy databases.

## Features

The script identifies and removes the following types of problematic records:

### 1. Unnamed People Without Named Ancestors
- People with no given name (only surname or completely unnamed)
- Only deleted if they don't have at least one named ancestor

### 2. EndofLine Parents
- Parents with only a surname that matches their child's surname
- Example: "Smith" as father of "John Smith"
- Example: "Mrs Smith" as mother of "John Smith"
- These are placeholder entries that provide no genealogical value

### 3. MRS Placeholders
- Generic "MRS" or "Mrs." entries without a real given name
- "MRS [Surname]" entries
- "Mrs. [Husband's Full Name]" clones
- Only deleted if not connected to named ancestors

### 4. Merge Candidates
- MRS persons who may be named elsewhere in the database
- Flagged for manual review but NOT automatically deleted
- Potential duplicates that should be merged

## Usage

### Prerequisites

```bash
# Ensure you have the GedMerge module in the same directory
cd /home/user/Python-Scripts
```

### Dry Run (Preview Changes)

**Always run this first!** This shows what would be deleted without making changes:

```bash
python cleanup_unnamed_people.py your_database.rmtree --dry-run
```

### Show More Details

```bash
python cleanup_unnamed_people.py your_database.rmtree --dry-run --report-limit 100
```

### Execute Deletions

**WARNING: This permanently modifies your database. Make a backup first!**

```bash
# Make a backup first!
cp your_database.rmtree your_database_backup.rmtree

# Then execute
python cleanup_unnamed_people.py your_database.rmtree --execute
```

## How It Works

### Detection Logic

1. **Unnamed Check**: Person has no given name or only whitespace
2. **MRS Check**: Given name is "MRS", "Mrs.", "MS", "Miss" or starts with "Mrs."
3. **EndofLine Check**: Person has only a surname (no given name) that matches a child's surname
4. **Named Ancestor Check**: Recursively searches up the family tree for any ancestor with a real given name

### Deletion Rules

A person is deleted if ANY of the following are true:

1. **EndofLine parent** - Always deleted (provides no value)
2. **MRS placeholder** AND no named ancestors - Deleted (unless named elsewhere)
3. **Unnamed** AND no named ancestors - Deleted

### Safety Features

- **Dry run by default**: Won't delete anything unless you use `--execute`
- **Confirmation prompt**: Asks for "yes" before executing deletions
- **Transaction safety**: All deletions happen in a single transaction (rollback on error)
- **Merge candidate detection**: MRS persons with potential matches are flagged, not deleted
- **Detailed reporting**: Shows exactly what will be deleted and why

## Example Output

```
Loading database...
Loaded 5234 persons and 1876 families

Analyzing persons...
  Merge candidate: Mrs. Jane Smith (ID: 1234) - Generic MRS/MS/MISS with surname 'Smith'

Found 127 persons to delete:
  - 45 unnamed without named ancestors
  - 38 MRS placeholders without named ancestors
  - 44 EndofLine surname-only parents

Found 12 potential merge candidates

================================================================================
DELETION REPORT
================================================================================

Showing first 50 of 127 persons to delete:

1. ID 2345: Smith (M)
   Reason: EndofLine parent 'Smith' of child 'John Smith', parent of: John Smith

2. ID 2346: Mrs Smith (F)
   Reason: Generic MRS/MS/MISS with surname 'Smith' - no named ancestors, parent of: John Smith

3. ID 3456: Unknown (U)
   Reason: Unnamed person 'Unknown' - no named ancestors

...
```

## What Gets Deleted

For each deleted person, the script removes:

- Name records (NameTable)
- Event records (EventTable)
- Family connections (sets FatherID/MotherID to NULL)
- Child relationships (ChildTable)
- Person record (PersonTable)

## Best Practices

1. **Always backup your database first**
2. **Run dry-run before execute**
3. **Review the deletion report carefully**
4. **Check merge candidates manually** - these may be duplicates
5. **Verify in RootsMagic after deletion**
6. **Consider running iteratively** - some unnamed people may become deletable after others are removed

## Command-Line Options

```
positional arguments:
  database              Path to RootsMagic .rmtree database file

optional arguments:
  -h, --help            show this help message and exit
  --dry-run             Preview changes without making them (default)
  --execute             Actually delete the persons (use with caution!)
  --report-limit N      Maximum number of entries to show in report (default: 50)
```

## Troubleshooting

### "Database file not found"
- Ensure the path to your .rmtree file is correct
- Use absolute path or ensure you're in the right directory

### "Module not found: gedmerge"
- Ensure the GedMerge folder is in the same directory as the script
- The script automatically adds it to the Python path

### Changes don't appear in RootsMagic
- Close and reopen the database in RootsMagic
- The database file is directly modified by SQLite

## Technical Details

### Database Tables Modified

- `PersonTable` - Person records deleted
- `NameTable` - Name records deleted
- `EventTable` - Event records deleted
- `FamilyTable` - Father/Mother IDs set to NULL
- `ChildTable` - Child relationships deleted

### Ancestor Search Algorithm

The script uses recursive depth-first search to find named ancestors:
1. Start with person to check
2. Get all parents
3. For each parent:
   - If parent has a real given name (not MRS/EndofLine), return True
   - Otherwise, recursively check parent's ancestors
4. Return False if no named ancestors found

This ensures we preserve any unnamed person who has genealogical value through their connection to named ancestors.
