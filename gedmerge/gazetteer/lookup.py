"""Gazetteer lookup functionality."""

import sqlite3
from pathlib import Path
from typing import List, Optional, Tuple
from rapidfuzz import fuzz

from .models import GazetteerPlace, PlaceMatch, PlaceType


class GazetteerLookup:
    """Provides lookup functionality for geographic places."""

    def __init__(self, database_path: str | Path = None):
        """Initialize gazetteer lookup.

        Args:
            database_path: Path to gazetteer SQLite database.
                          If None, uses default location.
        """
        if database_path is None:
            # Default location in models directory
            database_path = Path(__file__).parent.parent.parent / "models" / "gazetteer.db"

        self.db_path = Path(database_path)
        self.conn = None

        # Create database if it doesn't exist
        if not self.db_path.exists():
            self._create_database()

    def _create_database(self):
        """Create the gazetteer database schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Main places table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS places (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                geonames_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                ascii_name TEXT,
                country_code TEXT,
                admin1_code TEXT,
                admin2_code TEXT,
                admin3_code TEXT,
                admin4_code TEXT,
                latitude REAL,
                longitude REAL,
                feature_class TEXT,
                feature_code TEXT,
                population INTEGER,
                valid_from INTEGER,
                valid_to INTEGER,
                parent_id INTEGER,
                FOREIGN KEY (parent_id) REFERENCES places(id)
            )
        """)

        # Alternate names table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alternate_names (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                place_id INTEGER NOT NULL,
                alternate_name TEXT NOT NULL,
                language_code TEXT,
                is_preferred INTEGER DEFAULT 0,
                is_historic INTEGER DEFAULT 0,
                FOREIGN KEY (place_id) REFERENCES places(id)
            )
        """)

        # Create indexes for fast lookup
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_places_name
            ON places(name)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_places_country
            ON places(country_code)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_places_geonames
            ON places(geonames_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alternate_names_name
            ON alternate_names(alternate_name)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alternate_names_place
            ON alternate_names(place_id)
        """)

        conn.commit()
        conn.close()

    def connect(self):
        """Open database connection."""
        if self.conn is None:
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def lookup_exact(self, place_name: str, country_code: str = None) -> List[GazetteerPlace]:
        """Look up places by exact name match.

        Args:
            place_name: The place name to search for
            country_code: Optional country code to filter results

        Returns:
            List of matching places
        """
        self.connect()
        cursor = self.conn.cursor()

        if country_code:
            cursor.execute("""
                SELECT * FROM places
                WHERE (name = ? OR ascii_name = ?)
                AND country_code = ?
                ORDER BY population DESC NULLS LAST
            """, (place_name, place_name, country_code))
        else:
            cursor.execute("""
                SELECT * FROM places
                WHERE name = ? OR ascii_name = ?
                ORDER BY population DESC NULLS LAST
            """, (place_name, place_name))

        return [self._row_to_place(row) for row in cursor.fetchall()]

    def lookup_fuzzy(
        self,
        place_name: str,
        country_code: str = None,
        min_score: int = 80,
        limit: int = 10
    ) -> List[PlaceMatch]:
        """Look up places using fuzzy string matching.

        Args:
            place_name: The place name to search for
            country_code: Optional country code to filter results
            min_score: Minimum similarity score (0-100)
            limit: Maximum number of results

        Returns:
            List of place matches ordered by confidence
        """
        self.connect()
        cursor = self.conn.cursor()

        # Get candidate places (starts with same letter for performance)
        first_letter = place_name[0].upper() if place_name else ''

        if country_code:
            cursor.execute("""
                SELECT * FROM places
                WHERE (name LIKE ? OR ascii_name LIKE ?)
                AND country_code = ?
                LIMIT 100
            """, (f"{first_letter}%", f"{first_letter}%", country_code))
        else:
            cursor.execute("""
                SELECT * FROM places
                WHERE name LIKE ? OR ascii_name LIKE ?
                LIMIT 100
            """, (f"{first_letter}%", f"{first_letter}%"))

        matches = []
        for row in cursor.fetchall():
            place = self._row_to_place(row)

            # Calculate similarity score
            name_score = fuzz.ratio(place_name.lower(), place.name.lower())
            ascii_score = fuzz.ratio(place_name.lower(), place.ascii_name.lower())
            score = max(name_score, ascii_score)

            if score >= min_score:
                match_type = 'exact' if score == 100 else 'fuzzy'
                matches.append(PlaceMatch(
                    input_place=place_name,
                    gazetteer_place=place,
                    confidence=score / 100.0,
                    match_type=match_type
                ))

        # Sort by confidence
        matches.sort(key=lambda m: m.confidence, reverse=True)

        return matches[:limit]

    def lookup_with_context(
        self,
        place_name: str,
        year: int = None,
        parent_places: List[str] = None,
        nearby_coords: Tuple[float, float] = None,
        max_distance_km: float = 100.0
    ) -> List[PlaceMatch]:
        """Look up places with contextual information.

        Args:
            place_name: The place name to search for
            year: Year for temporal validation
            parent_places: List of parent place names (e.g., ["Ohio", "USA"])
            nearby_coords: (latitude, longitude) tuple
            max_distance_km: Maximum distance from nearby_coords

        Returns:
            List of place matches with context scores
        """
        # Start with fuzzy lookup
        matches = self.lookup_fuzzy(place_name, limit=20)

        # Apply contextual scoring
        for match in matches:
            context_score = 0.0

            # Temporal context
            if year and match.gazetteer_place.is_valid_in_year(year):
                context_score += 0.2

            # Parent place context
            if parent_places:
                hierarchy = match.gazetteer_place.full_hierarchy.lower()
                matching_parents = sum(
                    1 for parent in parent_places
                    if parent.lower() in hierarchy
                )
                context_score += (matching_parents / len(parent_places)) * 0.3

            # Geographic proximity context
            if nearby_coords and match.gazetteer_place.latitude:
                distance = self._calculate_distance(
                    nearby_coords,
                    (match.gazetteer_place.latitude, match.gazetteer_place.longitude)
                )
                if distance <= max_distance_km:
                    # Closer is better
                    proximity_score = 1.0 - (distance / max_distance_km)
                    context_score += proximity_score * 0.3

            match.context_score = context_score

        # Re-sort by total score (confidence + context)
        matches.sort(key=lambda m: m.confidence + m.context_score, reverse=True)

        return matches[:10]

    def add_place(self, place: GazetteerPlace) -> int:
        """Add a place to the gazetteer.

        Args:
            place: The place to add

        Returns:
            The ID of the inserted place
        """
        self.connect()
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO places (
                geonames_id, name, ascii_name, country_code,
                admin1_code, admin2_code, admin3_code, admin4_code,
                latitude, longitude, feature_class, feature_code,
                population, valid_from, valid_to, parent_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            place.geonames_id, place.name, place.ascii_name, place.country_code,
            place.admin1_code, place.admin2_code, place.admin3_code, place.admin4_code,
            place.latitude, place.longitude, place.feature_class, place.feature_code,
            place.population, place.valid_from, place.valid_to, place.parent_id
        ))

        place_id = cursor.lastrowid

        # Add alternate names
        if place.alternate_names:
            for alt_name in place.alternate_names:
                cursor.execute("""
                    INSERT INTO alternate_names (place_id, alternate_name)
                    VALUES (?, ?)
                """, (place_id, alt_name))

        self.conn.commit()
        return place_id

    def _row_to_place(self, row: sqlite3.Row) -> GazetteerPlace:
        """Convert database row to GazetteerPlace."""
        # Get alternate names
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT alternate_name
            FROM alternate_names
            WHERE place_id = ?
        """, (row['id'],))

        alternates = [r['alternate_name'] for r in cursor.fetchall()]

        return GazetteerPlace(
            geonames_id=row['geonames_id'],
            name=row['name'],
            ascii_name=row['ascii_name'],
            country_code=row['country_code'],
            admin1_code=row['admin1_code'],
            admin2_code=row['admin2_code'],
            admin3_code=row['admin3_code'],
            admin4_code=row['admin4_code'],
            latitude=row['latitude'],
            longitude=row['longitude'],
            feature_class=row['feature_class'],
            feature_code=row['feature_code'],
            population=row['population'],
            valid_from=row['valid_from'],
            valid_to=row['valid_to'],
            alternate_names=alternates,
            parent_id=row['parent_id']
        )

    @staticmethod
    def _calculate_distance(
        coord1: Tuple[float, float],
        coord2: Tuple[float, float]
    ) -> float:
        """Calculate distance between two coordinates in kilometers (Haversine formula)."""
        import math

        lat1, lon1 = coord1
        lat2, lon2 = coord2

        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        # Radius of Earth in kilometers
        r = 6371

        return c * r

    def get_stats(self) -> dict:
        """Get gazetteer statistics."""
        self.connect()
        cursor = self.conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM places")
        total_places = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM alternate_names")
        total_alternates = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT country_code) FROM places")
        total_countries = cursor.fetchone()[0]

        return {
            'total_places': total_places,
            'total_alternates': total_alternates,
            'total_countries': total_countries
        }
