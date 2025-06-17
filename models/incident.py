import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from shapely.geometry import Point, Polygon

from .database import DatabaseManager
from .hospital import Hospital
from .division import DivisionManager


class Incident:
    """Incident management class"""

    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()
        self.hospital_manager = Hospital(self.db)
        self.division_manager = DivisionManager(self.db)
        self.incident_id = None
        self.name = None
        self.incident_type = None
        self.description = None
        self.incident_location = None
        self.address = None
        self.search_area = None
        self.search_divisions = []
        self.hospital_data = None
        self.search_area_size_m2 = int(os.getenv("SEARCH_AREA_SIZE_M2", 40000))
        self.team_size = int(os.getenv("TEAM_SIZE", 4))

    def create_incident(
        self,
        name: str,
        incident_type: str,
        description: str = "",
        latitude: float = None,
        longitude: float = None,
        address: str = None,
        hospital_data: Dict = None,
        search_area_coordinates: List = None,
        divisions: List[Dict] = None,
    ) -> str:
        """Create a new incident with full data"""
        self.incident_id = (
            f"INC-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        )
        self.name = name
        self.incident_type = incident_type
        self.description = description
        self.address = address
        self.hospital_data = hospital_data

        # Set location if provided
        if latitude is not None and longitude is not None:
            self.incident_location = Point(longitude, latitude)

        # Insert basic incident data first
        query = """
        INSERT INTO incidents (
            incident_id, name, incident_type, description, 
            incident_location, address
        ) VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """

        params = (
            self.incident_id,
            self.name,
            self.incident_type,
            self.description,
            f"POINT({longitude} {latitude})" if self.incident_location else None,
            self.address,
        )

        result = self.db.execute_query(query, params, fetch=True)

        # Update with search area if provided
        if search_area_coordinates and len(search_area_coordinates) >= 3:
            # Ensure polygon is closed
            coords = search_area_coordinates.copy()
            if coords[0] != coords[-1]:
                coords.append(coords[0])

            # Convert lng,lat to lat,lng and create WKT
            coords_str = ", ".join([f"{coord[0]} {coord[1]}" for coord in coords])
            search_area_wkt = f"POLYGON(({coords_str}))"

            update_query = """
            UPDATE incidents 
            SET search_area = ST_GeomFromText(%s, 4326)
            WHERE incident_id = %s
            """

            self.db.execute_query(update_query, (search_area_wkt, self.incident_id))

        # Save hospital data if provided
        if self.hospital_data:
            self.hospital_manager.save_incident_hospitals(
                self.incident_id, self.hospital_data
            )

        # Save divisions if provided
        if divisions:
            self.division_manager.save_divisions(self.incident_id, divisions)

        return self.incident_id

    def generate_divisions_preview(
        self, search_area_coordinates: List, area_size_m2: int = 40000
    ) -> List[Dict]:
        """Generate divisions for preview without saving to database"""
        return self.division_manager.generate_divisions_preview(
            search_area_coordinates, area_size_m2, self.incident_location
        )

    def generate_divisions(self) -> List[Dict]:
        """Generate search divisions based on search area and team capacity"""
        if not self.search_area:
            raise ValueError("Search area must be set before generating divisions")

        return self.division_manager.generate_divisions(
            self.incident_id, 
            self.search_area, 
            self.search_area_size_m2, 
            self.incident_location
        )

    def save_divisions(self, divisions: List[Dict]) -> bool:
        """Save divisions to database"""
        return self.division_manager.save_divisions(self.incident_id, divisions)

    def get_divisions(self) -> List[Dict]:
        """Get search divisions for this incident"""
        return self.division_manager.get_divisions(self.incident_id)

    def set_location(self, latitude: float, longitude: float) -> bool:
        """Set incident location and reverse geocode to address"""
        try:
            self.incident_location = Point(longitude, latitude)

            # Reverse geocode if no address already set
            if not self.address:
                self.address = self._reverse_geocode(latitude, longitude)

            # Update database
            query = """
            UPDATE incidents 
            SET incident_location = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                address = %s
            WHERE incident_id = %s
            """

            self.db.execute_query(
                query, (longitude, latitude, self.address, self.incident_id)
            )

            return True

        except Exception as e:
            print(f"Failed to set location: {e}")
            return False

    def set_search_area(self, coordinates: List[Tuple[float, float]]) -> bool:
        """Set search area polygon"""
        try:
            # Create polygon from coordinates (lat, lng pairs)
            # Convert to (lng, lat) for PostGIS
            postgis_coords = [(lng, lat) for lat, lng in coordinates]
            self.search_area = Polygon(postgis_coords)

            # Ensure polygon is closed
            coords = coordinates.copy()
            if coords[0] != coords[-1]:
                coords.append(coords[0])

            # Convert to WKT for PostGIS
            coords_str = ", ".join([f"{lng} {lat}" for lat, lng in coords])
            polygon_wkt = f"POLYGON(({coords_str}))"

            # Update database
            query = """
            UPDATE incidents 
            SET search_area = ST_GeomFromText(%s, 4326)
            WHERE incident_id = %s
            """

            self.db.execute_query(query, (polygon_wkt, self.incident_id))

            return True

        except Exception as e:
            print(f"Failed to set search area: {e}")
            return False

    def save_hospital_data(self, hospital_data: Dict) -> bool:
        """Save hospital data for this incident"""
        try:
            self.hospital_data = hospital_data
            return self.hospital_manager.save_incident_hospitals(
                self.incident_id, hospital_data
            )
        except Exception as e:
            print(f"Failed to save hospital data: {e}")
            return False

    def get_incident_data(self) -> Dict:
        """Get complete incident data including hospitals"""
        try:
            # Get basic incident data
            query = """
            SELECT 
                incident_id, name, incident_type, description, address,
                ST_X(incident_location) as longitude,
                ST_Y(incident_location) as latitude,
                ST_AsGeoJSON(search_area) as search_area_geojson,
                created_at, updated_at, status
            FROM incidents
            WHERE incident_id = %s
            """

            result = self.db.execute_query(query, (self.incident_id,), fetch=True)

            if not result:
                return {}

            incident = dict(result[0])

            # Get hospital data
            hospital_data = self.hospital_manager.get_incident_hospitals(
                self.incident_id
            )
            if hospital_data:
                incident["hospitals"] = hospital_data

            # Get divisions
            divisions = self.get_divisions()
            if divisions:
                incident["divisions"] = divisions

            return incident

        except Exception as e:
            print(f"Failed to get incident data: {e}")
            return {}

    def _reverse_geocode(self, latitude: float, longitude: float) -> str:
        """Reverse geocode coordinates to address using Nominatim"""
        try:
            nominatim_url = os.getenv(
                "NOMINATIM_URL", "https://nominatim.openstreetmap.org"
            )
            url = f"{nominatim_url}/reverse"

            params = {
                "lat": latitude,
                "lon": longitude,
                "format": "json",
                "addressdetails": 1,
            }

            headers = {"User-Agent": "EmergencyIncidentApp/1.0"}

            response = requests.get(url, params=params, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get("display_name", f"{latitude}, {longitude}")
            else:
                return f"{latitude}, {longitude}"

        except Exception as e:
            print(f"Reverse geocoding failed: {e}")
            return f"{latitude}, {longitude}"

    @classmethod
    def get_incident_by_id(
        cls, incident_id: str, db_manager: DatabaseManager = None
    ) -> Optional["Incident"]:
        """Load an existing incident by ID"""
        try:
            incident = cls(db_manager)
            incident.incident_id = incident_id

            # Get incident data
            data = incident.get_incident_data()
            if not data:
                return None

            # Populate incident object
            incident.name = data.get("name")
            incident.incident_type = data.get("incident_type")
            incident.description = data.get("description")
            incident.address = data.get("address")

            if data.get("longitude") and data.get("latitude"):
                incident.incident_location = Point(data["longitude"], data["latitude"])

            incident.hospital_data = data.get("hospitals")

            return incident

        except Exception as e:
            print(f"Failed to load incident: {e}")
            return None
