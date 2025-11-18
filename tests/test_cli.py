"""Tests for the CLI interface."""

import pytest
import tempfile
import os
from pathlib import Path

from gedmerge.ui.cli import main, create_parser


SAMPLE_GEDCOM = """0 HEAD
1 SOUR TestSource
1 GEDC
2 VERS 5.5.1
0 @I1@ INDI
1 NAME Test /Person/
1 SEX M
1 BIRT
2 DATE 1 JAN 1950
0 TRLR
"""


@pytest.fixture
def sample_gedcom_file():
    """Create a temporary GEDCOM file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ged', delete=False) as f:
        f.write(SAMPLE_GEDCOM)
        temp_path = f.name

    yield temp_path

    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_create_parser():
    """Test that the argument parser is created correctly."""
    parser = create_parser()

    assert parser is not None
    assert parser.prog == 'gedmerge'


def test_cli_no_arguments():
    """Test CLI with no arguments shows help."""
    exit_code = main([])
    assert exit_code == 0


def test_cli_analyze_command(sample_gedcom_file, capsys):
    """Test the analyze command."""
    exit_code = main(['analyze', sample_gedcom_file])

    assert exit_code == 0

    captured = capsys.readouterr()
    assert 'GEDCOM FILE STATISTICS' in captured.out
    assert 'Total Individuals' in captured.out


def test_cli_analyze_with_samples(sample_gedcom_file, capsys):
    """Test the analyze command with sample display."""
    exit_code = main(['analyze', sample_gedcom_file, '--show-samples'])

    assert exit_code == 0

    captured = capsys.readouterr()
    assert 'SAMPLE INDIVIDUALS' in captured.out


def test_cli_analyze_nonexistent_file(capsys):
    """Test analyze with non-existent file."""
    exit_code = main(['analyze', '/nonexistent/file.ged'])

    assert exit_code == 1

    captured = capsys.readouterr()
    assert 'Error' in captured.err or 'not found' in captured.err.lower()


def test_cli_find_duplicates_placeholder(sample_gedcom_file, capsys):
    """Test find-duplicates placeholder command."""
    exit_code = main(['find-duplicates', sample_gedcom_file])

    assert exit_code == 0

    captured = capsys.readouterr()
    assert 'Phase 2' in captured.out


def test_cli_merge_placeholder(sample_gedcom_file, capsys):
    """Test merge placeholder command."""
    exit_code = main(['merge', sample_gedcom_file, '-o', 'output.ged'])

    assert exit_code == 0

    captured = capsys.readouterr()
    assert 'Phase 3' in captured.out


def test_cli_version():
    """Test version flag."""
    parser = create_parser()
    # Note: We can't easily test --version with main() as it exits,
    # but we can verify the parser has version configured
    assert parser._optionals._actions[1].version is not None


def test_cli_with_real_gedcom():
    """Test CLI with real GEDCOM file if available."""
    sample_file = Path('/home/user/Python-Scripts/GedMerge/GEDCOM/JOEL.GED')

    if sample_file.exists():
        exit_code = main(['analyze', str(sample_file)])
        assert exit_code == 0
    else:
        pytest.skip("Real GEDCOM file not found")
