"""GEDMerge - A tool to find and merge duplicate people in GEDCOM genealogy files."""

__version__ = "0.1.0"

from .core.person import Person
from .core.family import Family
from .core.event import Event
from .core.gedcom_parser import GedcomParser, load_gedcom, save_gedcom

__all__ = [
    'Person',
    'Family',
    'Event',
    'GedcomParser',
    'load_gedcom',
    'save_gedcom',
]
