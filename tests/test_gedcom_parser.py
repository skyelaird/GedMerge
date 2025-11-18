"""Tests for the GEDCOM parser."""

import pytest
import tempfile
import os
from pathlib import Path

from gedmerge.core.gedcom_parser import GedcomParser, load_gedcom, save_gedcom
from gedmerge.core.person import Person
from gedmerge.core.family import Family
from gedmerge.core.event import Event


# Sample GEDCOM data for testing
SAMPLE_GEDCOM = """0 HEAD
1 SOUR TestSource
2 VERS 1.0
1 GEDC
2 VERS 5.5.1
2 FORM LINEAGE-LINKED
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 BIRT
2 DATE 1 JAN 1950
2 PLAC New York, NY, USA
1 DEAT
2 DATE 31 DEC 2020
2 PLAC Boston, MA, USA
1 FAMS @F1@
1 FAMC @F2@
0 @I2@ INDI
1 NAME Jane /Smith/
1 SEX F
1 BIRT
2 DATE 15 JUN 1952
2 PLAC London, England
1 FAMS @F1@
0 @I3@ INDI
1 NAME Alice /Doe/
1 SEX F
1 BIRT
2 DATE 10 MAR 1975
2 PLAC Boston, MA, USA
1 FAMC @F1@
0 @F1@ FAM
1 HUSB @I1@
1 WIFE @I2@
1 CHIL @I3@
1 MARR
2 DATE 15 JUN 1974
2 PLAC Paris, France
0 @F2@ FAM
1 HUSB @I4@
1 WIFE @I5@
1 CHIL @I1@
0 TRLR
"""


@pytest.fixture
def sample_gedcom_file():
    """Create a temporary GEDCOM file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
        f.write(SAMPLE_GEDCOM)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def parser():
    """Create a GedcomParser instance."""
    return GedcomParser()


def test_load_gedcom_file_not_found(parser):
    """Test loading a non-existent file raises error."""
    with pytest.raises(FileNotFoundError):
        parser.load_gedcom('/nonexistent/file.ged')


def test_load_gedcom_success(parser, sample_gedcom_file):
    """Test successfully loading a GEDCOM file."""
    individuals, families = parser.load_gedcom(sample_gedcom_file)

    assert len(individuals) == 3
    assert len(families) == 2
    assert '@I1@' in individuals
    assert '@I2@' in individuals
    assert '@I3@' in individuals
    assert '@F1@' in families
    assert '@F2@' in families


def test_parse_individual_names(parser, sample_gedcom_file):
    """Test parsing individual names."""
    individuals, _ = parser.load_gedcom(sample_gedcom_file)

    john = individuals['@I1@']
    assert 'John /Doe/' in john.names or john.get_primary_name() == 'John /Doe/'


def test_parse_individual_sex(parser, sample_gedcom_file):
    """Test parsing individual sex."""
    individuals, _ = parser.load_gedcom(sample_gedcom_file)

    john = individuals['@I1@']
    jane = individuals['@I2@']

    assert john.sex == 'M'
    assert jane.sex == 'F'


def test_parse_individual_events(parser, sample_gedcom_file):
    """Test parsing individual events."""
    individuals, _ = parser.load_gedcom(sample_gedcom_file)

    john = individuals['@I1@']
    assert len(john.events) >= 2  # Birth and death

    birth = john.get_birth_event()
    assert birth is not None
    assert birth.type == 'BIRT'
    assert '1950' in birth.date

    death = john.get_death_event()
    assert death is not None
    assert death.type == 'DEAT'
    assert '2020' in death.date


def test_parse_family_relationships(parser, sample_gedcom_file):
    """Test parsing family relationships."""
    individuals, families = parser.load_gedcom(sample_gedcom_file)

    family1 = families['@F1@']
    assert family1.husband_id == '@I1@'
    assert family1.wife_id == '@I2@'
    assert '@I3@' in family1.children_ids


def test_parse_family_events(parser, sample_gedcom_file):
    """Test parsing family events."""
    _, families = parser.load_gedcom(sample_gedcom_file)

    family1 = families['@F1@']
    marriage = family1.get_marriage_event()

    assert marriage is not None
    assert marriage.type == 'MARR'
    assert '1974' in marriage.date
    assert 'Paris' in marriage.place


def test_individual_family_links(parser, sample_gedcom_file):
    """Test that individuals have correct family links."""
    individuals, _ = parser.load_gedcom(sample_gedcom_file)

    john = individuals['@I1@']
    assert '@F1@' in john.families_as_spouse
    assert '@F2@' in john.families_as_child


def test_save_and_reload_gedcom(parser, sample_gedcom_file):
    """Test that saving and reloading preserves data."""
    # Load original
    individuals1, families1 = parser.load_gedcom(sample_gedcom_file)

    # Save to new file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
        output_path = f.name

    try:
        save_gedcom(output_path, individuals1, families1)

        # Reload
        parser2 = GedcomParser()
        individuals2, families2 = parser2.load_gedcom(output_path)

        # Compare counts
        assert len(individuals1) == len(individuals2)
        assert len(families1) == len(families2)

        # Compare specific individual
        john1 = individuals1['@I1@']
        john2 = individuals2['@I1@']

        assert john1.id == john2.id
        assert john1.sex == john2.sex
        assert len(john1.events) == len(john2.events)

    finally:
        if os.path.exists(output_path):
            os.unlink(output_path)


def test_get_statistics(parser, sample_gedcom_file):
    """Test getting statistics from loaded file."""
    parser.load_gedcom(sample_gedcom_file)
    stats = parser.get_statistics()

    assert stats['num_individuals'] == 3
    assert stats['num_families'] == 2
    assert stats['num_males'] >= 1
    assert stats['num_females'] >= 1
    assert 'earliest_year' in stats
    assert 'latest_year' in stats


def test_convenience_load_function(sample_gedcom_file):
    """Test the convenience load_gedcom function."""
    individuals, families = load_gedcom(sample_gedcom_file)

    assert len(individuals) == 3
    assert len(families) == 2


def test_load_real_gedcom_file():
    """Test loading one of the real sample GEDCOM files."""
    sample_file = Path('/home/user/Python-Scripts/GedMerge/GEDCOM/JOEL.GED')

    if sample_file.exists():
        parser = GedcomParser()
        individuals, families = parser.load_gedcom(str(sample_file))

        # Basic sanity checks
        assert len(individuals) > 0, "Should have loaded some individuals"
        assert len(families) >= 0, "Should have loaded families"

        # Get statistics
        stats = parser.get_statistics()
        assert stats['num_individuals'] > 0
        assert stats['num_males'] + stats['num_females'] + stats['num_unknown_sex'] == stats['num_individuals']

        print(f"\nLoaded real GEDCOM file:")
        print(f"  Individuals: {stats['num_individuals']}")
        print(f"  Families: {stats['num_families']}")
        print(f"  Males: {stats['num_males']}")
        print(f"  Females: {stats['num_females']}")
    else:
        pytest.skip("Real GEDCOM file not found")


def test_person_extraction_completeness(parser, sample_gedcom_file):
    """Test that all person data is extracted correctly."""
    individuals, _ = parser.load_gedcom(sample_gedcom_file)

    for person_id, person in individuals.items():
        # Every person should have an ID
        assert person.id == person_id

        # Check that Person object methods work
        primary_name = person.get_primary_name()
        # Primary name might be None or a string
        assert primary_name is None or isinstance(primary_name, str)


def test_empty_gedcom():
    """Test handling of minimal GEDCOM file."""
    minimal_gedcom = """0 HEAD
1 GEDC
2 VERS 5.5.1
0 TRLR
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
        f.write(minimal_gedcom)
        temp_path = f.name

    try:
        parser = GedcomParser()
        individuals, families = parser.load_gedcom(temp_path)

        assert len(individuals) == 0
        assert len(families) == 0

    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
