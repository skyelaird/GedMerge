"""Tests for Place class with multilingual support."""

import pytest
from gedmerge.core.place import Place


class TestPlace:
    """Test suite for the Place class."""

    def test_create_place_with_single_name(self):
        """Test creating a place with a single name."""
        place = Place(names={'en': 'London'})
        assert place.get_name() == 'London'
        assert place.get_name('en') == 'London'

    def test_create_place_with_multiple_names(self):
        """Test creating a place with multiple language names."""
        place = Place(names={
            'en': 'Munich',
            'de': 'München',
            'fr': 'Munich'
        })
        assert place.get_name('en') == 'Munich'
        assert place.get_name('de') == 'München'
        assert place.get_name('fr') == 'Munich'

    def test_add_name_in_language(self):
        """Test adding a name in a specific language."""
        place = Place(names={'en': 'Vienna'})
        place.add_name('de', 'Wien')
        place.add_name('fr', 'Vienne')

        assert place.get_name('en') == 'Vienna'
        assert place.get_name('de') == 'Wien'
        assert place.get_name('fr') == 'Vienne'

    def test_get_name_fallback(self):
        """Test that get_name falls back to primary language."""
        place = Place(names={'en': 'Prague'}, primary_language='en')

        # Non-existent language should fall back to primary
        assert place.get_name('de') == 'Prague'

    def test_get_all_names(self):
        """Test getting all names."""
        names = {
            'en': 'Moscow',
            'ru': 'Москва',
            'de': 'Moskau'
        }
        place = Place(names=names)
        all_names = place.get_all_names()

        assert all_names == names
        # Ensure it's a copy, not the original
        all_names['fr'] = 'Moscou'
        assert 'fr' not in place.names

    def test_from_string(self):
        """Test creating a Place from a string."""
        place = Place.from_string('Paris')
        assert place.get_name() == 'Paris'
        assert place.get_name('en') == 'Paris'

    def test_from_string_with_language(self):
        """Test creating a Place from a string with specific language."""
        place = Place.from_string('Paris', language='fr')
        assert place.get_name('fr') == 'Paris'
        assert place.primary_language == 'fr'

    def test_is_empty(self):
        """Test checking if a place is empty."""
        empty_place = Place()
        assert empty_place.is_empty()

        non_empty_place = Place(names={'en': 'Rome'})
        assert not non_empty_place.is_empty()

    def test_coordinates(self):
        """Test place with coordinates."""
        place = Place(
            names={'en': 'New York'},
            latitude=40.7128,
            longitude=-74.0060
        )
        assert place.has_coordinates()
        assert place.latitude == 40.7128
        assert place.longitude == -74.0060

    def test_no_coordinates(self):
        """Test place without coordinates."""
        place = Place(names={'en': 'Unknown Location'})
        assert not place.has_coordinates()

    def test_partial_coordinates(self):
        """Test place with only one coordinate (should not be considered complete)."""
        place1 = Place(names={'en': 'Place1'}, latitude=40.0)
        assert not place1.has_coordinates()

        place2 = Place(names={'en': 'Place2'}, longitude=-74.0)
        assert not place2.has_coordinates()

    def test_to_dict(self):
        """Test converting place to dictionary."""
        place = Place(
            names={'en': 'Berlin', 'de': 'Berlin'},
            primary_language='de',
            latitude=52.5200,
            longitude=13.4050,
            place_type='city',
            notes='Capital of Germany'
        )
        data = place.to_dict()

        assert data['names'] == {'en': 'Berlin', 'de': 'Berlin'}
        assert data['primary_language'] == 'de'
        assert data['latitude'] == 52.5200
        assert data['longitude'] == 13.4050
        assert data['place_type'] == 'city'
        assert data['notes'] == 'Capital of Germany'

    def test_from_dict(self):
        """Test creating place from dictionary."""
        data = {
            'names': {'en': 'Tokyo', 'ja': '東京'},
            'primary_language': 'ja',
            'latitude': 35.6762,
            'longitude': 139.6503,
            'place_type': 'city',
            'notes': 'Capital of Japan'
        }
        place = Place.from_dict(data)

        assert place.get_name('en') == 'Tokyo'
        assert place.get_name('ja') == '東京'
        assert place.primary_language == 'ja'
        assert place.latitude == 35.6762
        assert place.longitude == 139.6503
        assert place.place_type == 'city'
        assert place.notes == 'Capital of Japan'

    def test_str_representation(self):
        """Test string representation."""
        place = Place(names={'en': 'Amsterdam'})
        assert str(place) == 'Amsterdam'

        empty_place = Place()
        assert str(empty_place) == 'Unknown Place'

    def test_repr_representation(self):
        """Test repr representation."""
        place = Place(names={'en': 'Dublin'}, primary_language='en')
        repr_str = repr(place)
        assert 'Dublin' in repr_str
        assert 'en' in repr_str

    def test_gedcom_format(self):
        """Test GEDCOM format output."""
        place = Place(names={'en': 'Warsaw'})
        assert place.get_gedcom_format() == 'Warsaw'

    def test_gedcom_format_with_hierarchy(self):
        """Test GEDCOM format with hierarchy."""
        place = Place(
            names={'en': 'Chicago'},
            hierarchy=['Chicago', 'Cook County', 'Illinois', 'USA']
        )
        assert place.get_gedcom_format() == 'Chicago, Cook County, Illinois, USA'

    def test_merge_places(self):
        """Test merging two places."""
        place1 = Place(
            names={'en': 'Constantinople'},
            latitude=41.0082,
            longitude=28.9784
        )
        place2 = Place(
            names={'en': 'Istanbul', 'tr': 'İstanbul'},
            notes='Modern name'
        )

        merged = place1.merge_with(place2)

        # Should have all names
        assert 'Constantinople' in merged.names.values()
        assert 'Istanbul' in merged.names.values()
        assert merged.get_name('tr') == 'İstanbul'

        # Should preserve coordinates from first place
        assert merged.latitude == 41.0082
        assert merged.longitude == 28.9784

    def test_place_init_with_string(self):
        """Test Place __post_init__ conversion from string."""
        # This tests the __post_init__ auto-conversion
        place = Place(names='Budapest')  # type: ignore
        assert isinstance(place.names, dict)
        assert place.get_name() == 'Budapest'

    def test_hierarchy(self):
        """Test place hierarchy."""
        place = Place(
            names={'en': 'Brooklyn'},
            hierarchy=['Brooklyn', 'Kings County', 'New York', 'USA']
        )
        assert len(place.hierarchy) == 4
        assert place.hierarchy[0] == 'Brooklyn'
        assert place.hierarchy[-1] == 'USA'


class TestPlaceIntegration:
    """Integration tests for Place with other components."""

    def test_place_roundtrip_dict(self):
        """Test that a place survives dict conversion roundtrip."""
        original = Place(
            names={'en': 'San Francisco', 'es': 'San Francisco'},
            primary_language='en',
            latitude=37.7749,
            longitude=-122.4194,
            place_type='city',
            notes='City in California',
            hierarchy=['San Francisco', 'San Francisco County', 'California', 'USA']
        )

        # Convert to dict and back
        data = original.to_dict()
        restored = Place.from_dict(data)

        # Verify all fields match
        assert restored.names == original.names
        assert restored.primary_language == original.primary_language
        assert restored.latitude == original.latitude
        assert restored.longitude == original.longitude
        assert restored.place_type == original.place_type
        assert restored.notes == original.notes
        assert restored.hierarchy == original.hierarchy


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
