import uuid
import requests
import os
import json
from datetime import datetime
from typing import List, Tuple, Optional, Dict
from shapely.geometry import Point, Polygon
from .database import DatabaseManager
from .hospital import Hospital


class Incident:
    """Incident management class"""

    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()
        self.hospital_manager = Hospital(self.db)
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
        divisions: List[Dict] = None
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
            self.address
        )

        result = self.db.execute_query(query, params, fetch=True)

        # Update with search area if provided
        if search_area_coordinates and len(search_area_coordinates) >= 3:
            # Convert lng,lat to lat,lng and create WKT
            coords_str = ", ".join([f"{coord[0]} {coord[1]}" for coord in search_area_coordinates])
            search_area_wkt = f"POLYGON(({coords_str}))"
            
            update_query = """
            UPDATE incidents 
            SET search_area = ST_GeomFromText(%s, 4326)
            WHERE incident_id = %s
            """
            
            self.db.execute_query(update_query, (
                search_area_wkt, 
                self.incident_id
            ))

        # Save hospital data if provided
        if self.hospital_data:
            self.hospital_manager.save_incident_hospitals(
                self.incident_id, 
                self.hospital_data
            )

        # Save divisions if provided
        if divisions:
            self.save_divisions(divisions)

        return self.incident_id

    def generate_divisions_preview(self, search_area_coordinates: List, area_size_m2: int = 40000) -> List[Dict]:
        """Generate divisions for preview without saving to database"""
        try:
            if not search_area_coordinates or len(search_area_coordinates) < 3:
                raise ValueError("At least 3 coordinates required for search area")

            # Convert coordinates to shapely polygon
            # search_area_coordinates are in lng,lat format
            polygon_coords = [(coord[0], coord[1]) for coord in search_area_coordinates]
            polygon = Polygon(polygon_coords)
            
            # Calculate area and number of divisions
            area_m2 = self._calculate_area_m2(polygon)
            num_divisions = max(1, int(area_m2 / area_size_m2))

            # Generate divisions
            divisions = self._create_grid_divisions_preview(polygon, num_divisions)
            
            return divisions

        except Exception as e:
            print(f"Failed to generate divisions preview: {e}")
            raise e

    def save_divisions(self, divisions: List[Dict]) -> bool:
        """Save divisions to database"""
        try:
            for division in divisions:
                # Extract coordinates from division data
                coordinates = None
                if 'coordinates' in division:
                    coordinates = division['coordinates']
                elif 'geom' in division and division['geom']:
                    # Parse geometry if it's in different format
                    geom_data = json.loads(division['geom']) if isinstance(division['geom'], str) else division['geom']
                    if 'coordinates' in geom_data:
                        coordinates = geom_data['coordinates'][0]  # Get outer ring
                
                if coordinates:
                    # Convert coordinates to WKT
                    coords_str = ", ".join([f"{coord[0]} {coord[1]}" for coord in coordinates])
                    polygon_wkt = f"POLYGON(({coords_str}))"

                    query = """
                    INSERT INTO search_divisions 
                    (incident_id, division_name, division_id, area_geometry, 
                     area_coordinates, estimated_area_m2, status, priority, 
                     search_type, estimated_duration, assigned_team)
                    VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s, %s, %s, %s)
                    """

                    params = (
                        self.incident_id,
                        division.get("division_name", division.get("name")),
                        division.get("division_id"),
                        polygon_wkt,
                        json.dumps(coordinates),
                        division.get("estimated_area_m2", 0),
                        division.get("status", "unassigned"),
                        division.get("priority", 1),
                        division.get("search_type", "primary"),
                        division.get("estimated_duration", "2 hours"),
                        division.get("assigned_team")
                    )

                    self.db.execute_query(query, params)
            
            return True

        except Exception as e:
            print(f"Failed to save divisions: {e}")
            return False

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

            # Convert to WKT for PostGIS
            coords_str = ", ".join([f"{lng} {lat}" for lat, lng in coordinates])
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
                self.incident_id, 
                hospital_data
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
            hospital_data = self.hospital_manager.get_incident_hospitals(self.incident_id)
            if hospital_data:
                incident['hospitals'] = hospital_data
            
            # Get divisions
            divisions = self.get_divisions()
            if divisions:
                incident['divisions'] = divisions
            
            return incident
            
        except Exception as e:
            print(f"Failed to get incident data: {e}")
            return {}

    def get_divisions(self) -> List[Dict]:
        """Get search divisions for this incident"""
        try:
            query = """
            SELECT 
                id, division_name, division_id, estimated_area_m2,
                assigned_team, team_leader, priority, search_type,
                estimated_duration, status,
                ST_AsGeoJSON(area_geometry) as geometry_geojson,
                area_coordinates
            FROM search_divisions
            WHERE incident_id = %s
            ORDER BY division_name
            """
            
            result = self.db.execute_query(query, (self.incident_id,), fetch=True)
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            print(f"Failed to get divisions: {e}")
            return []

    def generate_divisions(self) -> List[Dict]:
        """Generate search divisions based on search area and team capacity"""
        if not self.search_area:
            raise ValueError("Search area must be set before generating divisions")

        try:
            # Clear existing divisions
            self._clear_existing_divisions()
            
            # Calculate approximate number of divisions needed
            area_m2 = self._calculate_area_m2(self.search_area)
            num_divisions = max(1, int(area_m2 / self.search_area_size_m2))

            # For now, create simple grid divisions
            # TODO: Integrate with OSM road data for better alignment
            divisions = self._create_grid_divisions(num_divisions)

            # Save divisions to database
            self._save_divisions(divisions)

            return divisions

        except Exception as e:
            print(f"Failed to generate divisions: {e}")
            return []

    def _clear_existing_divisions(self):
        """Clear existing divisions for this incident"""
        query = "DELETE FROM search_divisions WHERE incident_id = %s"
        self.db.execute_query(query, (self.incident_id,))

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

    def _calculate_area_m2(self, polygon: Polygon) -> float:
        """Calculate polygon area in square meters (approximate)"""
        # Simple approximation - for production use proper geodetic calculations
        bounds = polygon.bounds
        lat_center = (bounds[1] + bounds[3]) / 2

        # Rough conversion from degrees to meters at given latitude
        lat_m_per_deg = 111132.92 - 559.82 * (lat_center * 0.0174533) ** 2
        lng_m_per_deg = 111412.84 * (1 - (lat_center * 0.0174533) ** 2) ** 0.5

        area_deg2 = polygon.area
        area_m2 = area_deg2 * lat_m_per_deg * lng_m_per_deg

        return abs(area_m2)

    def _create_grid_divisions_preview(self, polygon: Polygon, num_divisions: int) -> List[Dict]:
        """Create grid-based divisions for preview"""
        divisions = []
        bounds = polygon.bounds

        # Calculate grid dimensions
        cols = int((num_divisions**0.5)) if num_divisions > 1 else 1
        rows = int(num_divisions / cols) + (1 if num_divisions % cols else 0)

        width = (bounds[2] - bounds[0]) / cols
        height = (bounds[3] - bounds[1]) / rows

        division_counter = 0
        for row in range(rows):
            for col in range(cols):
                if division_counter >= num_divisions:
                    break

                # Create grid cell
                x1 = bounds[0] + col * width
                y1 = bounds[1] + row * height
                x2 = x1 + width
                y2 = y1 + height

                cell = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])

                # Clip to search area
                clipped = polygon.intersection(cell)

                if hasattr(clipped, "area") and clipped.area > 0:
                    division_letter = chr(65 + division_counter)  # A, B, C, etc.
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    # Convert geometry to coordinates for frontend
                    if hasattr(clipped, "exterior"):
                        coords = list(clipped.exterior.coords)
                    else:
                        coords = [(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)]

                    divisions.append({
                        "division_name": division_name,
                        "division_id": division_id,
                        "coordinates": coords,
                        "estimated_area_m2": self._calculate_area_m2(clipped),
                        "status": "unassigned",
                        "priority": 1,
                        "search_type": "primary",
                        "estimated_duration": "2 hours"
                    })

                    division_counter += 1

        return divisions

    def _create_grid_divisions(self, num_divisions: int) -> List[Dict]:
        """Create grid-based divisions"""
        divisions = []
        bounds = self.search_area.bounds

        # Calculate grid dimensions
        cols = int((num_divisions**0.5))
        rows = int(num_divisions / cols) + (1 if num_divisions % cols else 0)

        width = (bounds[2] - bounds[0]) / cols
        height = (bounds[3] - bounds[1]) / rows

        division_counter = 0
        for row in range(rows):
            for col in range(cols):
                if division_counter >= num_divisions:
                    break

                # Create grid cell
                x1 = bounds[0] + col * width
                y1 = bounds[1] + row * height
                x2 = x1 + width
                y2 = y1 + height

                cell = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])

                # Clip to search area
                clipped = self.search_area.intersection(cell)

                if hasattr(clipped, "area") and clipped.area > 0:
                    division_letter = chr(65 + division_counter)  # A, B, C, etc.
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    divisions.append(
                        {
                            "name": division_name,
                            "division_id": division_id,
                            "geometry": clipped,
                            "area_m2": self._calculate_area_m2(clipped),
                            "status": "unassigned",
                            "priority": 1,
                            "search_type": "primary",
                            "estimated_duration": "2 hours"
                        }
                    )

                    division_counter += 1

        return divisions

    def _save_divisions(self, divisions: List[Dict]):
        """Save divisions to database"""
        for division in divisions:
            # Convert geometry to WKT
            if hasattr(division["geometry"], "exterior"):
                coords = list(division["geometry"].exterior.coords)
                coords_str = ", ".join([f"{x} {y}" for x, y in coords])
                polygon_wkt = f"POLYGON(({coords_str}))"

                query = """
                INSERT INTO search_divisions 
                (incident_id, division_name, division_id, area_geometry, 
                 estimated_area_m2, status, priority, search_type, estimated_duration)
                VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s, %s)
                """

                params = (
                    self.incident_id,
                    division["name"],
                    division["division_id"],
                    polygon_wkt,
                    division["area_m2"],
                    division["status"],
                    division["priority"],
                    division["search_type"],
                    division["estimated_duration"]
                )

                self.db.execute_query(query, params)

    @classmethod
    def get_incident_by_id(cls, incident_id: str, db_manager: DatabaseManager = None) -> Optional['Incident']:
        """Load an existing incident by ID"""
        try:
            incident = cls(db_manager)
            incident.incident_id = incident_id
            
            # Get incident data
            data = incident.get_incident_data()
            if not data:
                return None
            
            # Populate incident object
            incident.name = data.get('name')
            incident.incident_type = data.get('incident_type')
            incident.description = data.get('description')
            incident.address = data.get('address')
            
            if data.get('longitude') and data.get('latitude'):
                incident.incident_location = Point(data['longitude'], data['latitude'])
            
            incident.hospital_data = data.get('hospitals')
            
            return incident
            
        except Exception as e:
            print(f"Failed to load incident: {e}")
            return None
