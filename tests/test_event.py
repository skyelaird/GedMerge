"""Tests for the Event class."""

import pytest
from gedmerge.core.event import Event


def test_event_creation():
    """Test basic event creation."""
    event = Event(type='BIRT', date='1 JAN 1950', place='New York, NY, USA')

    assert event.type == 'BIRT'
    assert event.date == '1 JAN 1950'
    assert event.place == 'New York, NY, USA'
    assert event.notes is None
    assert event.sources == []
    assert event.attributes == {}


def test_event_str_representation():
    """Test string representation of event."""
    event = Event(type='BIRT', date='1 JAN 1950', place='New York, NY, USA')

    result = str(event)
    assert 'BIRT' in result
    assert '1 JAN 1950' in result
    assert 'New York, NY, USA' in result


def test_event_to_dict():
    """Test converting event to dictionary."""
    event = Event(
        type='MARR',
        date='15 JUN 1975',
        place='London, England',
        notes='Beautiful ceremony'
    )

    result = event.to_dict()
    assert result['type'] == 'MARR'
    assert result['date'] == '15 JUN 1975'
    assert result['place'] == 'London, England'
    assert result['notes'] == 'Beautiful ceremony'


def test_event_from_dict():
    """Test creating event from dictionary."""
    data = {
        'type': 'DEAT',
        'date': '31 DEC 2000',
        'place': 'Paris, France',
        'notes': None,
        'sources': ['@S1@'],
        'attributes': {'CAUS': 'Natural'}
    }

    event = Event.from_dict(data)
    assert event.type == 'DEAT'
    assert event.date == '31 DEC 2000'
    assert event.place == 'Paris, France'
    assert event.sources == ['@S1@']
    assert event.attributes['CAUS'] == 'Natural'


def test_event_is_valid():
    """Test event validation."""
    event1 = Event(type='BIRT')
    assert event1.is_valid()

    event2 = Event(type='')
    assert not event2.is_valid()


def test_event_get_year():
    """Test extracting year from date."""
    event1 = Event(type='BIRT', date='15 APR 1955')
    assert event1.get_year() == 1955

    event2 = Event(type='BIRT', date='BET 1950 AND 1960')
    assert event2.get_year() == 1950  # Should get first year

    event3 = Event(type='BIRT', date='Unknown')
    assert event3.get_year() is None

    event4 = Event(type='BIRT', date=None)
    assert event4.get_year() is None


def test_event_with_attributes():
    """Test event with custom attributes."""
    event = Event(
        type='EVEN',
        date='10 MAY 2000',
        attributes={'TYPE': 'Graduation', 'AGE': '22'}
    )

    assert event.attributes['TYPE'] == 'Graduation'
    assert event.attributes['AGE'] == '22'
