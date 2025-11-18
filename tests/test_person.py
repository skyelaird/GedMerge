"""Tests for the Person class."""

import pytest
from gedmerge.core.person import Person
from gedmerge.core.event import Event


def test_person_creation():
    """Test basic person creation."""
    person = Person(
        id='@I1@',
        names=['John /Doe/'],
        sex='M'
    )

    assert person.id == '@I1@'
    assert person.names == ['John /Doe/']
    assert person.sex == 'M'
    assert person.events == []
    assert person.families_as_spouse == []
    assert person.families_as_child == []


def test_person_with_events():
    """Test person with events."""
    birth_event = Event(type='BIRT', date='1 JAN 1950', place='New York, NY')
    death_event = Event(type='DEAT', date='31 DEC 2020', place='Boston, MA')

    person = Person(
        id='@I1@',
        names=['Jane /Smith/'],
        sex='F',
        events=[birth_event, death_event]
    )

    assert len(person.events) == 2
    assert person.get_birth_event() == birth_event
    assert person.get_death_event() == death_event


def test_get_primary_name():
    """Test getting primary name."""
    person = Person(
        id='@I1@',
        names=['John /Doe/', 'Johnny /Doe/']
    )

    assert person.get_primary_name() == 'John /Doe/'

    person_no_name = Person(id='@I2@')
    assert person_no_name.get_primary_name() is None


def test_get_surname():
    """Test extracting surname."""
    person = Person(
        id='@I1@',
        names=['John Michael /Doe/']
    )

    assert person.get_surname() == 'Doe'

    person_no_surname = Person(
        id='@I2@',
        names=['John']
    )
    assert person_no_surname.get_surname() is None


def test_get_given_name():
    """Test extracting given name."""
    person = Person(
        id='@I1@',
        names=['John Michael /Doe/']
    )

    assert person.get_given_name() == 'John Michael'


def test_get_birth_year():
    """Test getting birth year."""
    birth_event = Event(type='BIRT', date='15 APR 1955')
    person = Person(
        id='@I1@',
        names=['John /Doe/'],
        events=[birth_event]
    )

    assert person.get_birth_year() == 1955


def test_get_death_year():
    """Test getting death year."""
    death_event = Event(type='DEAT', date='31 DEC 2020')
    person = Person(
        id='@I1@',
        names=['John /Doe/'],
        events=[death_event]
    )

    assert person.get_death_year() == 2020


def test_get_birth_place():
    """Test getting birth place."""
    birth_event = Event(type='BIRT', place='London, England')
    person = Person(
        id='@I1@',
        names=['John /Doe/'],
        events=[birth_event]
    )

    assert person.get_birth_place() == 'London, England'


def test_is_living():
    """Test determining if person is living."""
    living_person = Person(
        id='@I1@',
        names=['John /Doe/'],
        events=[Event(type='BIRT', date='1 JAN 1950')]
    )
    assert living_person.is_living()

    deceased_person = Person(
        id='@I2@',
        names=['Jane /Smith/'],
        events=[
            Event(type='BIRT', date='1 JAN 1920'),
            Event(type='DEAT', date='31 DEC 2000')
        ]
    )
    assert not deceased_person.is_living()


def test_person_str_representation():
    """Test string representation of person."""
    birth_event = Event(type='BIRT', date='15 APR 1955')
    death_event = Event(type='DEAT', date='31 DEC 2020')

    person = Person(
        id='@I1@',
        names=['John /Doe/'],
        events=[birth_event, death_event]
    )

    result = str(person)
    assert 'John /Doe/' in result
    assert '1955' in result
    assert '2020' in result


def test_person_to_dict():
    """Test converting person to dictionary."""
    birth_event = Event(type='BIRT', date='1 JAN 1950')
    person = Person(
        id='@I1@',
        names=['John /Doe/'],
        sex='M',
        events=[birth_event],
        families_as_spouse=['@F1@']
    )

    result = person.to_dict()
    assert result['id'] == '@I1@'
    assert result['names'] == ['John /Doe/']
    assert result['sex'] == 'M'
    assert len(result['events']) == 1
    assert result['families_as_spouse'] == ['@F1@']


def test_person_from_dict():
    """Test creating person from dictionary."""
    data = {
        'id': '@I1@',
        'names': ['Jane /Smith/'],
        'sex': 'F',
        'events': [
            {
                'type': 'BIRT',
                'date': '1 JAN 1960',
                'place': 'Boston, MA',
                'notes': None,
                'sources': [],
                'attributes': {}
            }
        ],
        'families_as_spouse': ['@F1@'],
        'families_as_child': ['@F2@'],
        'sources': [],
        'notes': None,
        'attributes': {}
    }

    person = Person.from_dict(data)
    assert person.id == '@I1@'
    assert person.names == ['Jane /Smith/']
    assert person.sex == 'F'
    assert len(person.events) == 1
    assert person.families_as_spouse == ['@F1@']
    assert person.families_as_child == ['@F2@']


def test_person_with_family_relationships():
    """Test person with family relationships."""
    person = Person(
        id='@I1@',
        names=['John /Doe/'],
        families_as_spouse=['@F1@', '@F2@'],
        families_as_child=['@F3@']
    )

    assert '@F1@' in person.families_as_spouse
    assert '@F2@' in person.families_as_spouse
    assert '@F3@' in person.families_as_child
