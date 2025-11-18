"""Tests for the Family class."""

import pytest
from gedmerge.core.family import Family
from gedmerge.core.event import Event


def test_family_creation():
    """Test basic family creation."""
    family = Family(
        id='@F1@',
        husband_id='@I1@',
        wife_id='@I2@',
        children_ids=['@I3@', '@I4@']
    )

    assert family.id == '@F1@'
    assert family.husband_id == '@I1@'
    assert family.wife_id == '@I2@'
    assert family.children_ids == ['@I3@', '@I4@']
    assert family.events == []


def test_family_with_events():
    """Test family with events."""
    marriage_event = Event(type='MARR', date='15 JUN 1975', place='London, England')
    family = Family(
        id='@F1@',
        husband_id='@I1@',
        wife_id='@I2@',
        events=[marriage_event]
    )

    assert len(family.events) == 1
    assert family.get_marriage_event() == marriage_event


def test_get_parents():
    """Test getting parent IDs."""
    family = Family(
        id='@F1@',
        husband_id='@I1@',
        wife_id='@I2@'
    )

    parents = family.get_parents()
    assert '@I1@' in parents
    assert '@I2@' in parents
    assert len(parents) == 2


def test_get_parents_single_parent():
    """Test getting parent IDs with single parent."""
    family = Family(
        id='@F1@',
        husband_id='@I1@'
    )

    parents = family.get_parents()
    assert '@I1@' in parents
    assert len(parents) == 1


def test_has_children():
    """Test checking if family has children."""
    family_with_children = Family(
        id='@F1@',
        husband_id='@I1@',
        wife_id='@I2@',
        children_ids=['@I3@', '@I4@']
    )
    assert family_with_children.has_children()

    family_without_children = Family(
        id='@F2@',
        husband_id='@I5@',
        wife_id='@I6@'
    )
    assert not family_without_children.has_children()


def test_get_marriage_year():
    """Test getting marriage year."""
    marriage_event = Event(type='MARR', date='15 JUN 1975')
    family = Family(
        id='@F1@',
        husband_id='@I1@',
        wife_id='@I2@',
        events=[marriage_event]
    )

    assert family.get_marriage_year() == 1975


def test_get_marriage_place():
    """Test getting marriage place."""
    marriage_event = Event(type='MARR', place='Paris, France')
    family = Family(
        id='@F1@',
        husband_id='@I1@',
        wife_id='@I2@',
        events=[marriage_event]
    )

    assert family.get_marriage_place() == 'Paris, France'


def test_is_divorced():
    """Test checking if family is divorced."""
    divorce_event = Event(type='DIV', date='1 JAN 2000')
    divorced_family = Family(
        id='@F1@',
        husband_id='@I1@',
        wife_id='@I2@',
        events=[divorce_event]
    )
    assert divorced_family.is_divorced()

    married_family = Family(
        id='@F2@',
        husband_id='@I3@',
        wife_id='@I4@',
        events=[Event(type='MARR', date='15 JUN 1975')]
    )
    assert not married_family.is_divorced()


def test_family_str_representation():
    """Test string representation of family."""
    family = Family(
        id='@F1@',
        husband_id='@I1@',
        wife_id='@I2@',
        children_ids=['@I3@', '@I4@', '@I5@']
    )

    result = str(family)
    assert '@F1@' in result
    assert '@I1@' in result
    assert '@I2@' in result
    assert '3' in result  # Number of children


def test_family_to_dict():
    """Test converting family to dictionary."""
    marriage_event = Event(type='MARR', date='15 JUN 1975')
    family = Family(
        id='@F1@',
        husband_id='@I1@',
        wife_id='@I2@',
        children_ids=['@I3@'],
        events=[marriage_event]
    )

    result = family.to_dict()
    assert result['id'] == '@F1@'
    assert result['husband_id'] == '@I1@'
    assert result['wife_id'] == '@I2@'
    assert result['children_ids'] == ['@I3@']
    assert len(result['events']) == 1


def test_family_from_dict():
    """Test creating family from dictionary."""
    data = {
        'id': '@F1@',
        'husband_id': '@I1@',
        'wife_id': '@I2@',
        'children_ids': ['@I3@', '@I4@'],
        'events': [
            {
                'type': 'MARR',
                'date': '15 JUN 1975',
                'place': 'London, England',
                'notes': None,
                'sources': [],
                'attributes': {}
            }
        ],
        'sources': [],
        'notes': None,
        'attributes': {}
    }

    family = Family.from_dict(data)
    assert family.id == '@F1@'
    assert family.husband_id == '@I1@'
    assert family.wife_id == '@I2@'
    assert family.children_ids == ['@I3@', '@I4@']
    assert len(family.events) == 1


def test_get_event_by_type():
    """Test getting event by type."""
    marriage_event = Event(type='MARR', date='15 JUN 1975')
    divorce_event = Event(type='DIV', date='1 JAN 2000')

    family = Family(
        id='@F1@',
        events=[marriage_event, divorce_event]
    )

    assert family.get_event_by_type('MARR') == marriage_event
    assert family.get_event_by_type('DIV') == divorce_event
    assert family.get_event_by_type('NONEXISTENT') is None
