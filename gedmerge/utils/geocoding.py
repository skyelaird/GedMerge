"""Geocoding utilities for place name resolution and coordinate lookup."""

import time
import logging
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
import requests
from urllib.parse import quote

logger = logging.getLogger(__name__)


@dataclass
class GeocodingResult:
    """Result of a geocoding operation."""
    latitude: float
    longitude: float
    display_name: str
    place_type: Optional[str] = None
    osm_id: Optional[int] = None
    confidence: Optional[float] = None
    address: Optional[Dict[str, str]] = None


class NominatimGeocoder:
    """
    Geocoder using OpenStreetMap's Nominatim service.

    Free to use with rate limiting (1 request per second).
    No API key required.
    """

    BASE_URL = "https://nominatim.openstreetmap.org"

    def __init__(self, user_agent: str = "GedMerge/2.0"):
        """
        Initialize the geocoder.

        Args:
            user_agent: User agent string for API requests (required by Nominatim)
        """
        self.user_agent = user_agent
        self.last_request_time = 0
        self.min_request_interval = 1.0  # 1 second between requests (Nominatim rate limit)

    def _rate_limit(self):
        """Ensure we don't exceed Nominatim's rate limit of 1 request per second."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    def geocode(self, place_name: str, language: str = "en") -> Optional[GeocodingResult]:
        """
        Geocode a place name to coordinates.

        Args:
            place_name: The place name to geocode (e.g., "Paris, France")
            language: Preferred language for results (ISO 639-1 code)

        Returns:
            GeocodingResult if successful, None otherwise
        """
        self._rate_limit()

        url = f"{self.BASE_URL}/search"
        params = {
            "q": place_name,
            "format": "json",
            "addressdetails": 1,
            "limit": 1,
            "accept-language": language,
        }
        headers = {
            "User-Agent": self.user_agent
        }

        try:
            logger.info(f"Geocoding place: {place_name}")
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            results = response.json()

            if not results:
                logger.warning(f"No geocoding results found for: {place_name}")
                return None

            # Take the first result
            result = results[0]

            return GeocodingResult(
                latitude=float(result["lat"]),
                longitude=float(result["lon"]),
                display_name=result.get("display_name", place_name),
                place_type=result.get("type"),
                osm_id=result.get("osm_id"),
                confidence=result.get("importance"),  # Nominatim uses "importance" as a confidence score
                address=result.get("address", {})
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Geocoding request failed for {place_name}: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse geocoding response for {place_name}: {e}")
            return None

    def reverse_geocode(self, latitude: float, longitude: float, language: str = "en") -> Optional[GeocodingResult]:
        """
        Reverse geocode coordinates to a place name.

        Args:
            latitude: Latitude in decimal degrees
            longitude: Longitude in decimal degrees
            language: Preferred language for results (ISO 639-1 code)

        Returns:
            GeocodingResult if successful, None otherwise
        """
        self._rate_limit()

        url = f"{self.BASE_URL}/reverse"
        params = {
            "lat": latitude,
            "lon": longitude,
            "format": "json",
            "addressdetails": 1,
            "accept-language": language,
        }
        headers = {
            "User-Agent": self.user_agent
        }

        try:
            logger.info(f"Reverse geocoding: ({latitude}, {longitude})")
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()

            result = response.json()

            if "error" in result:
                logger.warning(f"Reverse geocoding failed: {result['error']}")
                return None

            return GeocodingResult(
                latitude=float(result["lat"]),
                longitude=float(result["lon"]),
                display_name=result.get("display_name", ""),
                place_type=result.get("type"),
                osm_id=result.get("osm_id"),
                confidence=result.get("importance"),
                address=result.get("address", {})
            )

        except requests.exceptions.RequestException as e:
            logger.error(f"Reverse geocoding request failed: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Failed to parse reverse geocoding response: {e}")
            return None

    def batch_geocode(self, place_names: list[str], language: str = "en") -> Dict[str, Optional[GeocodingResult]]:
        """
        Geocode multiple place names.

        Note: This method respects Nominatim's rate limit of 1 request per second,
        so it will take len(place_names) seconds to complete.

        Args:
            place_names: List of place names to geocode
            language: Preferred language for results

        Returns:
            Dictionary mapping place names to GeocodingResults (or None if failed)
        """
        results = {}
        total = len(place_names)

        for i, place_name in enumerate(place_names, 1):
            logger.info(f"Geocoding {i}/{total}: {place_name}")
            results[place_name] = self.geocode(place_name, language)

        return results


def format_place_hierarchy(address: Dict[str, str]) -> list[str]:
    """
    Format Nominatim address components into a hierarchical place name.

    Args:
        address: Address dictionary from Nominatim response

    Returns:
        List of place components in hierarchical order (specific to general)
    """
    hierarchy = []

    # Order from most specific to most general
    component_order = [
        "building",
        "house_number",
        "road",
        "neighbourhood",
        "suburb",
        "city",
        "town",
        "village",
        "municipality",
        "county",
        "state",
        "region",
        "country",
    ]

    for component in component_order:
        if component in address and address[component]:
            hierarchy.append(address[component])

    return hierarchy
