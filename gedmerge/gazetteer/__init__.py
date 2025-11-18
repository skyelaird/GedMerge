"""
Gazetteer module for place name lookup and disambiguation.

This module provides:
- Geographic name lookup from GeoNames database
- Multi-lingual place name support
- Historical place name variants
- Context-aware place disambiguation
"""

from .models import GazetteerPlace, PlaceType
from .lookup import GazetteerLookup

__all__ = [
    'GazetteerPlace',
    'PlaceType',
    'GazetteerLookup',
]
