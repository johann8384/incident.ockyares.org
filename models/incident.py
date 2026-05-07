"""
Incident Model - Unified status tracking system
All unit interactions are status updates, including initial check-in
"""

import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
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
            self.save_divisions(divisions)

        return self.incident_id

    def generate_divisions_preview(
        self, search_area_coordinates: List, max_divisions: int = None, area_size_m2: int = 40000, strategy: str = "grid"
    ) -> List[Dict]:
        """Generate divisions for preview without saving to database

        Args:
            search_area_coordinates: List of coordinates defining the search area
            max_divisions: Maximum number of divisions to create (takes precedence over area_size_m2)
            area_size_m2: Target area size per division (used if max_divisions not specified)
            strategy: Division strategy - "grid" for grid-based, "road" for road-based
        """
        try:
            if not search_area_coordinates or len(search_area_coordinates) < 3:
                raise ValueError("At least 3 coordinates required for search area")

            # Convert coordinates to shapely polygon
            # search_area_coordinates are in lng,lat format
            polygon_coords = [(coord[0], coord[1]) for coord in search_area_coordinates]
            polygon = Polygon(polygon_coords)

            # Calculate number of divisions
            if max_divisions is not None:
                # Use max_divisions if specified
                num_divisions = max(1, min(max_divisions, 100))  # Cap at 100 for safety
            else:
                # Calculate from area if max_divisions not specified
                area_m2 = self._calculate_area_m2(polygon)
                num_divisions = max(1, int(area_m2 / area_size_m2))

            # Generate divisions based on strategy
            if strategy == "road":
                divisions = self._create_road_based_divisions_preview(
                    polygon, num_divisions, self.incident_location
                )
            else:
                divisions = self._create_grid_divisions_preview(
                    polygon, num_divisions, self.incident_location
                )

            return divisions

        except Exception as e:
            print(f"Failed to generate divisions preview: {e}")
            raise e

    def _calculate_division_priority(
        self, division_geom: Polygon, incident_location: Point, existing_divisions: List[Dict]
    ) -> str:
        """
        Calculate division priority based on distance from incident location
        Priority rules:
        - High: Division containing incident location + adjacent divisions
        - Medium: Divisions adjacent to High priority divisions  
        - Low: All other divisions
        """
        if not incident_location:
            return "Low"
        
        # Check if this division contains the incident location
        if division_geom.contains(incident_location):
            return "High"
        
        # Find High priority divisions already created
        high_priority_divisions = [
            div for div in existing_divisions if div.get("priority") == "High"
        ]
        
        # If no High priority division exists yet, check distance to incident
        if not high_priority_divisions:
            # Calculate distance from division centroid to incident location
            division_centroid = division_geom.centroid
            distance = division_centroid.distance(incident_location)
            
            # If very close to incident (roughly adjacent), make it High
            # Using a small threshold based on typical division size
            bounds = division_geom.bounds
            division_size = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
            
            if distance <= division_size * 1.5:  # Within 1.5 division widths
                return "High"
        else:
            # Check if adjacent to any High priority division
            for high_div in high_priority_divisions:
                if "coordinates" in high_div:
                    high_geom = Polygon(high_div["coordinates"])
                    # Check if divisions are adjacent (touching or very close)
                    if division_geom.touches(high_geom) or division_geom.distance(high_geom) < 0.001:
                        return "High"
        
        # Check if adjacent to any High priority division for Medium priority
        for existing_div in existing_divisions:
            if existing_div.get("priority") == "High" and "coordinates" in existing_div:
                existing_geom = Polygon(existing_div["coordinates"])
                if division_geom.touches(existing_geom) or division_geom.distance(existing_geom) < 0.001:
                    return "Medium"
        
        return "Low"

    def save_divisions(self, divisions: List[Dict]) -> bool:
        """Save divisions to database using batch insert for performance"""
        try:
            if not divisions:
                return True

            # Prepare batch data
            values_list = []
            for division in divisions:
                # Extract coordinates from division data
                coordinates = None
                if "coordinates" in division:
                    coordinates = division["coordinates"]
                elif "geom" in division and division["geom"]:
                    # Parse geometry if it's in different format
                    geom_data = (
                        json.loads(division["geom"])
                        if isinstance(division["geom"], str)
                        else division["geom"]
                    )
                    if "coordinates" in geom_data:
                        coordinates = geom_data["coordinates"][0]  # Get outer ring

                if coordinates:
                    # Ensure polygon is closed
                    coords = coordinates.copy()
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])

                    # Convert coordinates to WKT
                    coords_str = ", ".join(
                        [f"{coord[0]} {coord[1]}" for coord in coords]
                    )
                    polygon_wkt = f"POLYGON(({coords_str}))"

                    values_list.append((
                        self.incident_id,
                        division.get("division_name", division.get("name")),
                        division.get("division_id"),
                        polygon_wkt,
                        division.get("estimated_area_m2", 0),
                        division.get("status", "unassigned"),
                        division.get("priority", "Low"),
                        division.get("search_type", "primary"),
                        division.get("estimated_duration", "2 hours"),
                        division.get("assigned_team"),
                    ))

            # Batch insert all divisions in a single query
            if values_list:
                # Use psycopg2.extras.execute_values for efficient batch insert
                import psycopg2.extras

                conn = self.db.get_connection()
                cursor = conn.cursor()

                query = """
                INSERT INTO search_divisions
                (incident_id, division_name, division_id, area_geometry,
                 estimated_area_m2, status, priority,
                 search_type, estimated_duration, assigned_team)
                VALUES %s
                """

                # Convert WKT strings to PostGIS geometries in the template
                template = "(%s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s, %s, %s)"

                psycopg2.extras.execute_values(
                    cursor, query, values_list, template=template, page_size=100
                )
                conn.commit()
                cursor.close()

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

    def get_divisions(self) -> List[Dict]:
        """Get search divisions for this incident with current progress, ordered alphabetically"""
        try:
            query = """
            SELECT 
                sd.id, sd.division_name, sd.division_id, sd.estimated_area_m2,
                sd.assigned_team, sd.team_leader, sd.priority, sd.search_type,
                sd.estimated_duration, sd.status, sd.assigned_unit_id,
                ST_AsGeoJSON(sd.area_geometry) as geometry_geojson,
                u.unit_name, u.unit_type, u.unit_leader,
                COALESCE(ush.percentage_complete, 0) as percentage_complete,
                ush.timestamp as last_update
            FROM search_divisions sd
            LEFT JOIN units u ON sd.assigned_unit_id = u.unit_id
            LEFT JOIN LATERAL (
                SELECT percentage_complete, timestamp
                FROM unit_status_history
                WHERE unit_id = sd.assigned_unit_id 
                  AND incident_id = sd.incident_id
                  AND division_id = sd.division_id
                ORDER BY timestamp DESC
                LIMIT 1
            ) ush ON true
            WHERE sd.incident_id = %s
            ORDER BY sd.division_name
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

    def _convert_area_to_m2(self, area_deg2: float, reference_polygon: Polygon) -> float:
        """Convert area from degrees² to m² using a reference polygon for location

        Args:
            area_deg2: Area value in degrees²
            reference_polygon: A polygon at the same location to use for conversion factors

        Returns:
            Area in square meters (approximate)
        """
        bounds = reference_polygon.bounds
        lat_center = (bounds[1] + bounds[3]) / 2

        # Rough conversion from degrees to meters at given latitude
        lat_m_per_deg = 111132.92 - 559.82 * (lat_center * 0.0174533) ** 2
        lng_m_per_deg = 111412.84 * (1 - (lat_center * 0.0174533) ** 2) ** 0.5

        area_m2 = area_deg2 * lat_m_per_deg * lng_m_per_deg

        return abs(area_m2)

    def _create_grid_divisions_preview(
        self, polygon: Polygon, num_divisions: int, incident_location: Point = None
    ) -> List[Dict]:
        """Create grid-based divisions for preview"""
        divisions = []
        bounds = polygon.bounds

        # Ensure polygon is valid
        if not polygon.is_valid:
            polygon = polygon.buffer(0)  # Fix invalid geometry

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

                # Create grid cell with small buffer to avoid edge cases
                x1 = bounds[0] + col * width
                y1 = bounds[1] + row * height
                x2 = x1 + width
                y2 = y1 + height

                cell = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])

                # Ensure cell is valid
                if not cell.is_valid:
                    cell = cell.buffer(0)

                try:
                    # Clip to search area with safety checks
                    if polygon.intersects(cell):
                        clipped = polygon.intersection(cell)

                        # Handle different geometry types returned by intersection
                        if hasattr(clipped, "area") and clipped.area > 0:
                            # Only process if it's a valid polygon-like geometry
                            if hasattr(clipped, "exterior"):
                                coords = list(clipped.exterior.coords)
                            elif hasattr(clipped, "geoms"):
                                # MultiPolygon case - take the largest polygon
                                largest = max(
                                    clipped.geoms,
                                    key=lambda g: g.area if hasattr(g, "area") else 0,
                                )
                                if hasattr(largest, "exterior"):
                                    coords = list(largest.exterior.coords)
                                    clipped = largest
                                else:
                                    continue
                            else:
                                # Fallback to grid cell
                                coords = [
                                    (x1, y1),
                                    (x2, y1),
                                    (x2, y2),
                                    (x1, y2),
                                    (x1, y1),
                                ]
                                clipped = cell

                            division_letter = chr(
                                65 + division_counter
                            )  # A, B, C, etc.
                            division_name = f"Division {division_letter}"
                            division_id = f"DIV-{division_letter}"

                            # Calculate priority based on distance from incident location
                            priority = self._calculate_division_priority(
                                clipped, incident_location, divisions
                            )

                            divisions.append(
                                {
                                    "division_name": division_name,
                                    "division_id": division_id,
                                    "coordinates": coords,
                                    "estimated_area_m2": self._calculate_area_m2(
                                        clipped
                                    ),
                                    "status": "unassigned",
                                    "priority": priority,
                                    "search_type": "primary",
                                    "estimated_duration": "2 hours",
                                }
                            )

                            division_counter += 1

                except Exception as e:
                    print(f"Error processing grid cell {row},{col}: {e}")
                    # Skip this cell and continue
                    continue

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

                    # Calculate priority based on incident location
                    priority = self._calculate_division_priority(
                        clipped, self.incident_location, divisions
                    )

                    divisions.append(
                        {
                            "name": division_name,
                            "division_id": division_id,
                            "geometry": clipped,
                            "area_m2": self._calculate_area_m2(clipped),
                            "status": "unassigned",
                            "priority": priority,
                            "search_type": "primary",
                            "estimated_duration": "2 hours",
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
                    division.get("division_name", division.get("name")),
                    division.get("division_id"),
                    polygon_wkt,
                    division.get("area_m2", division.get("estimated_area_m2", 0)),
                    division.get("status", "unassigned"),
                    division.get("priority", "Low"),
                    division.get("search_type", "primary"),
                    division.get("estimated_duration", "2 hours"),
                )

                self.db.execute_query(query, params)

    def _fetch_osm_roads(self, polygon: Polygon) -> List:
        """Fetch road data from OpenStreetMap within the search area"""
        try:
            # Get bounding box
            bounds = polygon.bounds  # (minx, miny, maxx, maxy)
            # Overpass format: south,west,north,east
            bbox = f"{bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]}"

            # Build Overpass QL query
            # Use raw HTTP request for full control over query format
            query = f"""
[out:json][timeout:60];
(
  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential|unclassified|service)$"]({bbox});
);
out geom;
""".strip()

            headers = {"User-Agent": "EmergencyIncidentApp/1.0"}

            # Try multiple Overpass API endpoints (mirrors) for reliability
            overpass_endpoints = [
                "https://overpass-api.de/api/interpreter",
                "https://overpass.kumi.systems/api/interpreter",
                "https://overpass.openstreetmap.ru/api/interpreter"
            ]

            for endpoint_idx, overpass_url in enumerate(overpass_endpoints):
                try:
                    if endpoint_idx > 0:
                        print(f"  Retrying with mirror {endpoint_idx + 1}...")

                    response = requests.post(
                        overpass_url,
                        data={"data": query},
                        headers=headers,
                        timeout=60  # Increased from 30 to 60 seconds
                    )

                    if response.status_code == 200:
                        data = response.json()
                        # Convert OSM JSON to GeoJSON-like format
                        features = []
                        for element in data.get('elements', []):
                            if element.get('type') == 'way' and 'geometry' in element:
                                feature = {
                                    'type': 'Feature',
                                    'geometry': {
                                        'type': 'LineString',
                                        'coordinates': [[node['lon'], node['lat']] for node in element['geometry']]
                                    },
                                    'properties': element.get('tags', {})
                                }
                                features.append(feature)

                        if features:
                            return features
                        else:
                            print(f"  No roads returned from {overpass_url}")
                            continue

                    elif response.status_code == 504:
                        print(f"  Overpass API timeout (504) from {overpass_url}")
                        # Try next endpoint
                        continue
                    elif response.status_code == 429:
                        print(f"  Overpass API rate limited (429) from {overpass_url}")
                        # Try next endpoint
                        continue
                    else:
                        print(f"  Overpass API returned status {response.status_code} from {overpass_url}")
                        continue

                except requests.exceptions.Timeout:
                    print(f"  Request timeout from {overpass_url}")
                    continue
                except requests.exceptions.RequestException as e:
                    print(f"  Request error from {overpass_url}: {e}")
                    continue

            # All endpoints failed
            print(f"All Overpass API endpoints failed or timed out")
            return []

        except Exception as e:
            print(f"Failed to fetch OSM road data: {e}")
            return []

    def _create_road_based_divisions_preview(
        self, polygon: Polygon, num_divisions: int, incident_location: Point = None
    ) -> List[Dict]:
        """Create road-based divisions using OpenStreetMap road network

        This creates divisions that:
        1. Use roads as natural boundaries
        2. Are accessible from the road network
        3. Don't require crossing back and forth over roads
        """
        from shapely.ops import unary_union, polygonize
        from shapely.geometry import LineString, MultiLineString

        try:
            # Fetch road data from OSM
            print(f"Fetching road data from OpenStreetMap for search area...")
            road_features = self._fetch_osm_roads(polygon)

            if not road_features:
                print("No road data found, falling back to grid-based divisions")
                return self._create_grid_divisions_preview(polygon, num_divisions, incident_location)

            # Extract road geometries as LineStrings
            road_lines = []
            for feature in road_features:
                geom = feature.get('geometry')
                if geom and geom.get('type') == 'LineString':
                    coords = geom.get('coordinates', [])
                    if len(coords) >= 2:
                        # Convert from [lon, lat] to shapely coords
                        try:
                            line = LineString([(c[0], c[1]) for c in coords])

                            # Fix invalid geometries using buffer(0) trick
                            if not line.is_valid:
                                line = line.buffer(0)
                                if line.geom_type != 'LineString':
                                    continue

                            # Simplify to reduce precision issues
                            line = line.simplify(0.00001, preserve_topology=True)

                            # Only include roads that intersect the search area
                            if line.is_valid and line.intersects(polygon):
                                try:
                                    clipped_line = line.intersection(polygon)

                                    # Repair clipped geometry if needed
                                    if not clipped_line.is_valid:
                                        clipped_line = clipped_line.buffer(0)

                                    # Handle different intersection result types
                                    if clipped_line.geom_type == 'LineString' and clipped_line.is_valid:
                                        road_lines.append(clipped_line)
                                    elif clipped_line.geom_type == 'MultiLineString':
                                        # Add each line segment from the MultiLineString
                                        for segment in clipped_line.geoms:
                                            if segment.is_valid and segment.geom_type == 'LineString':
                                                road_lines.append(segment)
                                    elif clipped_line.geom_type == 'GeometryCollection':
                                        # Extract LineStrings from GeometryCollection
                                        for g in clipped_line.geoms:
                                            if g.geom_type == 'LineString' and g.is_valid:
                                                road_lines.append(g)
                                except Exception as e:
                                    # Skip problematic intersections
                                    continue
                        except Exception as e:
                            # Skip problematic road geometries
                            continue

            if not road_lines:
                print("No roads intersect search area, falling back to grid-based divisions")
                return self._create_grid_divisions_preview(polygon, num_divisions, incident_location)

            print(f"Found {len(road_lines)} road segments in search area")

            # Create divisions using road network
            # Strategy: Use roads to split the search area into natural zones
            divisions = []

            # Combine all road lines into a MultiLineString
            try:
                multi_line = MultiLineString(road_lines)
            except Exception as e:
                print(f"Error creating MultiLineString: {e}")
                return self._create_grid_divisions_preview(polygon, num_divisions, incident_location)

            # Split the polygon using the road network
            # This creates natural divisions bounded by roads
            try:
                # Ensure polygon is valid before splitting
                if not polygon.is_valid:
                    polygon = polygon.buffer(0)

                # Strategy: Use roads as cutting lines to split the polygon
                # We want to split BY the roads, not remove them
                # Use a minimal buffer just to ensure clean topology
                from shapely.ops import split, unary_union

                # Try to use split operation with road lines
                # Create a very small buffer around roads just for clean splitting
                road_buffer = multi_line.buffer(0.000001)  # Extremely small buffer (about 10cm)

                # Ensure buffer is valid
                if not road_buffer.is_valid:
                    road_buffer = road_buffer.buffer(0)

                # Split the polygon by removing the tiny road buffer
                split_result = polygon.difference(road_buffer)

                # Store the road buffer area to add back later
                road_area = polygon.intersection(road_buffer)

                # Handle different result types
                division_polygons = []
                if hasattr(split_result, 'geoms'):
                    # MultiPolygon result
                    division_polygons = [p for p in split_result.geoms if hasattr(p, 'area') and p.area > 0]
                elif hasattr(split_result, 'area') and split_result.area > 0:
                    # Single Polygon result
                    division_polygons = [split_result]

                print(f"Road split produced {len(division_polygons)} initial polygons")

                # Remove tiny edge divisions created by roads running along search area boundary
                # These are not useful for search operations
                division_polygons = self._remove_tiny_edge_divisions(
                    division_polygons, polygon, target_area=polygon.area / num_divisions
                )
                print(f"After removing tiny edge divisions: {len(division_polygons)} divisions")

                # If we got too many divisions, merge them intelligently
                if len(division_polygons) > num_divisions:
                    print(f"Merging {len(division_polygons)} polygons to {num_divisions} divisions")
                    division_polygons = self._merge_adjacent_polygons(
                        division_polygons, num_divisions, incident_location
                    )
                    print(f"After merging: {len(division_polygons)} divisions")

                # If still too many or too few, use hybrid
                if len(division_polygons) > num_divisions * 2 or len(division_polygons) < 2:
                    print(f"Could not achieve target divisions, using hybrid approach")
                    return self._create_hybrid_divisions_preview(
                        polygon, num_divisions, incident_location, road_lines
                    )

                # Take the appropriate number of divisions
                if len(division_polygons) > num_divisions:
                    # Sort by area and take largest
                    division_polygons.sort(key=lambda p: p.area, reverse=True)
                    division_polygons = division_polygons[:num_divisions]

                # Remove any remaining small divisions (less than 20% of average size)
                print("Removing small divisions...")
                division_polygons = self._remove_small_divisions(division_polygons, min_size_ratio=0.2)

                # Fill holes in divisions (remove interior rings and gaps between divisions)
                # This includes road areas that were temporarily removed for splitting
                print("Filling holes in divisions...")
                division_polygons = self._fill_division_holes(division_polygons, search_area=polygon)

                # Balance division areas to make them more equal
                division_polygons = self._balance_division_areas(division_polygons, max_iterations=5)

                print(f"Final divisions after hole filling and area balancing: {len(division_polygons)}")

                # Create division metadata
                for i, div_poly in enumerate(division_polygons):
                    division_letter = chr(65 + i)  # A, B, C, etc.
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    # Get coordinates
                    if hasattr(div_poly, 'exterior'):
                        coords = list(div_poly.exterior.coords)
                    else:
                        continue

                    # Calculate priority
                    priority = self._calculate_division_priority(
                        div_poly, incident_location, divisions
                    )

                    divisions.append({
                        "division_name": division_name,
                        "division_id": division_id,
                        "coordinates": coords,
                        "estimated_area_m2": self._calculate_area_m2(div_poly),
                        "status": "unassigned",
                        "priority": priority,
                        "search_type": "primary",
                        "estimated_duration": "2 hours",
                    })

                print(f"Created {len(divisions)} road-based divisions")
                return divisions

            except Exception as e:
                print(f"Error creating road-based divisions: {e}")
                return self._create_grid_divisions_preview(polygon, num_divisions, incident_location)

        except Exception as e:
            print(f"Failed to create road-based divisions: {e}")
            # Fall back to grid-based divisions
            return self._create_grid_divisions_preview(polygon, num_divisions, incident_location)

    def _remove_tiny_edge_divisions(
        self, polygons: List[Polygon], search_area: Polygon, target_area: float
    ) -> List[Polygon]:
        """Remove tiny divisions along search area edges caused by roads running along boundaries

        These tiny divisions are created when a road runs very close to the search area boundary,
        creating a sliver on the other side of the road. They're not useful for search operations.

        Args:
            polygons: List of division polygons
            search_area: Original search area polygon
            target_area: Target area per division

        Returns:
            Filtered list of polygons with tiny edge divisions removed
        """
        if not polygons:
            return polygons

        # Define thresholds for what's considered "tiny"
        # A division is tiny if it's less than 5% of target area AND less than 2000 m²
        min_area_threshold = min(target_area * 0.05, 0.000018)  # ~2000 m² in degrees squared

        filtered_polygons = []
        removed_count = 0

        for poly in polygons:
            # Check if polygon is tiny
            if poly.area < min_area_threshold:
                # Check if it's along the edge of the search area
                # A polygon is on the edge if its boundary overlaps significantly with search area boundary
                search_boundary = search_area.boundary
                poly_boundary = poly.boundary

                # Check intersection between boundaries
                boundary_intersection = search_boundary.intersection(poly_boundary)

                # If the polygon shares a significant portion of its boundary with the search area edge,
                # it's a tiny edge division we should remove
                if hasattr(boundary_intersection, 'length'):
                    # Calculate what percentage of the polygon's perimeter is on the search area edge
                    shared_boundary_ratio = boundary_intersection.length / poly_boundary.length

                    if shared_boundary_ratio > 0.3:  # More than 30% of boundary is on search area edge
                        print(f"  Removing tiny edge division ({self._calculate_area_m2(poly):.0f} m², {shared_boundary_ratio:.1%} on edge)")
                        removed_count += 1
                        continue  # Skip this polygon

            # Keep this polygon
            filtered_polygons.append(poly)

        if removed_count > 0:
            print(f"  Removed {removed_count} tiny edge division(s)")

        return filtered_polygons

    def _remove_small_divisions(
        self, polygons: List[Polygon], min_size_ratio: float = 0.2
    ) -> List[Polygon]:
        """Remove divisions that are very small compared to their neighbors

        Args:
            polygons: List of division polygons
            min_size_ratio: Minimum size as ratio of average division size (default 0.2 = 20%)

        Returns:
            List of polygons with small divisions merged into neighbors
        """
        from shapely.ops import unary_union

        if len(polygons) <= 2:
            return polygons

        # Calculate average division size
        total_area = sum(p.area for p in polygons)
        avg_area = total_area / len(polygons)
        min_area_threshold = avg_area * min_size_ratio

        print(f"  Removing divisions smaller than {min_size_ratio:.0%} of average ({self._convert_area_to_m2(min_area_threshold, polygons[0]):.0f} m²)")

        working_polygons = polygons.copy()
        removed_count = 0

        # Keep iterating until no more small divisions to remove
        while True:
            found_small = False

            for i, poly in enumerate(working_polygons):
                if poly.area < min_area_threshold:
                    # This division is too small, find best neighbor to merge with
                    best_neighbor_idx = None
                    longest_shared_boundary = 0

                    for j, neighbor in enumerate(working_polygons):
                        if i != j:
                            # Check if they share a boundary
                            if poly.touches(neighbor) or poly.intersects(neighbor):
                                # Calculate shared boundary length
                                shared_boundary = poly.boundary.intersection(neighbor.boundary)
                                if hasattr(shared_boundary, 'length'):
                                    boundary_length = shared_boundary.length

                                    # Prefer neighbors that are at least 10x larger
                                    # This prevents merging into another small division
                                    if neighbor.area >= poly.area * 10 and boundary_length > longest_shared_boundary:
                                        longest_shared_boundary = boundary_length
                                        best_neighbor_idx = j

                    # If no large neighbor found, try any neighbor
                    if best_neighbor_idx is None:
                        for j, neighbor in enumerate(working_polygons):
                            if i != j:
                                if poly.touches(neighbor) or poly.intersects(neighbor):
                                    shared_boundary = poly.boundary.intersection(neighbor.boundary)
                                    if hasattr(shared_boundary, 'length'):
                                        boundary_length = shared_boundary.length
                                        if boundary_length > longest_shared_boundary:
                                            longest_shared_boundary = boundary_length
                                            best_neighbor_idx = j

                    if best_neighbor_idx is not None:
                        # Merge small division into neighbor
                        try:
                            neighbor = working_polygons[best_neighbor_idx]
                            neighbor_area = neighbor.area
                            merged = unary_union([poly, neighbor])

                            if merged.is_valid:
                                # Handle MultiPolygon results
                                if merged.geom_type == 'MultiPolygon':
                                    merged = max(merged.geoms, key=lambda p: p.area)

                                if merged.geom_type == 'Polygon':
                                    # Remove both polygons and add merged
                                    # Remove larger index first
                                    if best_neighbor_idx > i:
                                        working_polygons.pop(best_neighbor_idx)
                                        working_polygons.pop(i)
                                    else:
                                        working_polygons.pop(i)
                                        working_polygons.pop(best_neighbor_idx)

                                    working_polygons.append(merged)
                                    removed_count += 1
                                    found_small = True
                                    print(f"    Merged small division ({self._convert_area_to_m2(poly.area, poly):.0f} m²) into neighbor ({self._convert_area_to_m2(neighbor_area, neighbor):.0f} m²)")
                                    break
                        except Exception as e:
                            print(f"    Error merging small division: {e}")

            # If no small divisions found in this pass, we're done
            if not found_small:
                break

            # Recalculate threshold in case divisions changed significantly
            if len(working_polygons) > 2:
                total_area = sum(p.area for p in working_polygons)
                avg_area = total_area / len(working_polygons)
                min_area_threshold = avg_area * min_size_ratio

        if removed_count > 0:
            print(f"  Removed {removed_count} small division(s), {len(working_polygons)} divisions remaining")

        return working_polygons

    def _merge_adjacent_polygons(
        self, polygons: List[Polygon], target_count: int, incident_location: Point = None
    ) -> List[Polygon]:
        """Merge adjacent polygons to reach target count

        Strategy: Iteratively merge the smallest polygon with its nearest neighbor
        """
        from shapely.ops import unary_union

        if len(polygons) <= target_count:
            return polygons

        # Make a working copy
        working_polygons = polygons.copy()

        while len(working_polygons) > target_count:
            # Find the smallest polygon
            smallest_idx = min(range(len(working_polygons)), key=lambda i: working_polygons[i].area)
            smallest = working_polygons[smallest_idx]

            # Find the nearest neighbor
            min_distance = float('inf')
            nearest_idx = None

            for i, poly in enumerate(working_polygons):
                if i != smallest_idx:
                    distance = smallest.distance(poly)
                    if distance < min_distance:
                        min_distance = distance
                        nearest_idx = i

            if nearest_idx is not None:
                # Merge the two polygons
                try:
                    merged = unary_union([smallest, working_polygons[nearest_idx]])

                    # Remove the two original polygons and add the merged one
                    # Remove larger index first to avoid index shifting
                    if nearest_idx > smallest_idx:
                        working_polygons.pop(nearest_idx)
                        working_polygons.pop(smallest_idx)
                    else:
                        working_polygons.pop(smallest_idx)
                        working_polygons.pop(nearest_idx)

                    # Add merged polygon if it's valid
                    if merged.is_valid and merged.geom_type == 'Polygon':
                        working_polygons.append(merged)
                    elif merged.geom_type == 'MultiPolygon':
                        # If merge created a MultiPolygon, add the largest part
                        largest_part = max(merged.geoms, key=lambda p: p.area)
                        working_polygons.append(largest_part)
                except Exception as e:
                    print(f"Error merging polygons: {e}")
                    break
            else:
                # Can't find a neighbor, stop merging
                break

        return working_polygons

    def _fill_division_holes(self, polygons: List[Polygon], search_area: Polygon = None) -> List[Polygon]:
        """Fill holes in division polygons

        This handles two types of holes:
        1. Interior rings within individual polygons (donut shapes)
        2. Gaps between divisions (uncovered areas in the search zone)
        """
        from shapely.ops import unary_union

        filled_polygons = []

        # Step 1: Remove interior rings from individual polygons
        for poly in polygons:
            if poly.geom_type == 'Polygon':
                # Check if polygon has interior rings (holes)
                if len(poly.interiors) > 0:
                    # Create a new polygon with only the exterior ring (no holes)
                    filled_poly = Polygon(poly.exterior.coords)
                    filled_polygons.append(filled_poly)
                    print(f"  Removed {len(poly.interiors)} interior ring(s) from division")
                else:
                    # No holes, keep as is
                    filled_polygons.append(poly)
            else:
                # Not a polygon, keep as is
                filled_polygons.append(poly)

        # Step 2: Find and fill gaps between divisions
        if search_area is not None and len(filled_polygons) > 0:
            # Create union of all divisions
            divisions_union = unary_union(filled_polygons)

            # Find uncovered areas (gaps/holes)
            uncovered = search_area.difference(divisions_union)

            if uncovered.is_valid and not uncovered.is_empty:
                # Handle different geometry types
                gaps = []
                if uncovered.geom_type == 'Polygon':
                    gaps = [uncovered]
                elif uncovered.geom_type == 'MultiPolygon':
                    gaps = list(uncovered.geoms)
                elif uncovered.geom_type == 'GeometryCollection':
                    gaps = [g for g in uncovered.geoms if g.geom_type == 'Polygon']

                if gaps:
                    print(f"  Found {len(gaps)} gap(s) between divisions")

                    # Store original division shapes to prevent snowball effect
                    # We check distance against original divisions, not enlarged ones
                    original_divisions = [poly for poly in filled_polygons]

                    # For each gap, find which division it's enclosed by or closest to
                    for gap in gaps:
                        if gap.area < 0.0000001:  # Skip tiny gaps
                            continue

                        # Find which division encloses or is closest to this gap
                        # Use ORIGINAL divisions for distance calculation
                        best_division_idx = None
                        min_distance = float('inf')

                        for i, original_div in enumerate(original_divisions):
                            # Check if gap is within this division
                            if original_div.contains(gap):
                                best_division_idx = i
                                break
                            # Check if gap touches this division (shared boundary)
                            if original_div.touches(gap):
                                best_division_idx = i
                                break
                            # Otherwise, check distance
                            distance = original_div.distance(gap)
                            if distance < min_distance:
                                min_distance = distance
                                best_division_idx = i

                        # Merge gap with the best division
                        if best_division_idx is not None:
                            try:
                                merged = unary_union([filled_polygons[best_division_idx], gap])
                                if merged.is_valid and merged.geom_type == 'Polygon':
                                    filled_polygons[best_division_idx] = merged
                                    print(f"    Merged gap ({self._calculate_area_m2(gap):.0f} m²) into division {chr(65 + best_division_idx)}")
                                elif merged.geom_type == 'MultiPolygon':
                                    # Take the largest part if merge created MultiPolygon
                                    largest = max(merged.geoms, key=lambda p: p.area)
                                    filled_polygons[best_division_idx] = largest
                            except Exception as e:
                                print(f"    Error merging gap: {e}")

        return filled_polygons

    def _balance_division_areas(
        self, polygons: List[Polygon], max_iterations: int = 5
    ) -> List[Polygon]:
        """Iteratively balance division areas to make them more equal

        Strategy:
        1. Calculate target area (total area / number of divisions)
        2. Identify largest and smallest divisions
        3. Transfer area from largest to smallest by adjusting shared boundaries
        4. Repeat until areas are balanced or max iterations reached
        """
        from shapely.ops import unary_union
        from shapely.affinity import scale

        if len(polygons) <= 1:
            return polygons

        # Calculate total area and target area per division
        total_area = sum(p.area for p in polygons)
        target_area = total_area / len(polygons)

        print(f"Balancing {len(polygons)} divisions - target area: {self._convert_area_to_m2(target_area, polygons[0]):.0f} m²")

        for iteration in range(max_iterations):
            # Calculate area deviation
            areas = [p.area for p in polygons]
            min_area = min(areas)
            max_area = max(areas)
            avg_area = sum(areas) / len(areas)

            # Calculate coefficient of variation (std dev / mean)
            variance = sum((a - avg_area) ** 2 for a in areas) / len(areas)
            std_dev = variance ** 0.5
            cv = std_dev / avg_area if avg_area > 0 else 0

            print(f"  Iteration {iteration + 1}: Area CV={cv:.3f}, min={min_area/avg_area:.2f}x, max={max_area/avg_area:.2f}x target")

            # If areas are well balanced (CV < 0.2), stop
            if cv < 0.2:
                print(f"  Areas well balanced (CV={cv:.3f}), stopping")
                break

            # Find largest and smallest divisions
            largest_idx = max(range(len(polygons)), key=lambda i: areas[i])
            smallest_idx = min(range(len(polygons)), key=lambda i: areas[i])

            if largest_idx == smallest_idx:
                break

            largest = polygons[largest_idx]
            smallest = polygons[smallest_idx]

            # Only transfer if the difference is significant (>10% of target)
            if largest.area - smallest.area < target_area * 0.1:
                print(f"  Divisions within 10% of target, stopping")
                break

            # Try to transfer area by finding shared boundary or nearest point
            try:
                # Check if they share a boundary
                if largest.touches(smallest) or largest.distance(smallest) < 0.001:
                    # They're adjacent - try to shift the boundary
                    # Calculate how much area to transfer (half the difference)
                    area_to_transfer = (largest.area - smallest.area) / 2

                    # Create a buffer zone from largest toward smallest
                    # Use negative buffer on largest, positive on smallest
                    perimeter = largest.boundary.length if hasattr(largest, 'boundary') else largest.length
                    buffer_distance = (area_to_transfer / perimeter) ** 0.5 if perimeter > 0 else 0.0001

                    # Erode the largest slightly
                    new_largest = largest.buffer(-buffer_distance * 0.5)
                    if new_largest.is_valid and hasattr(new_largest, 'area') and new_largest.area > 0:
                        # Expand the smallest slightly
                        new_smallest = smallest.buffer(buffer_distance * 0.5)
                        if new_smallest.is_valid and hasattr(new_smallest, 'area') and new_smallest.area > 0:
                            # Update the polygons
                            if new_largest.geom_type == 'Polygon':
                                polygons[largest_idx] = new_largest
                            if new_smallest.geom_type == 'Polygon':
                                polygons[smallest_idx] = new_smallest
                        else:
                            break
                    else:
                        break
                else:
                    # Not adjacent - harder to transfer area, skip
                    break

            except Exception as e:
                print(f"  Error balancing areas: {e}")
                break

        # Final stats
        final_areas = [p.area for p in polygons]
        final_avg = sum(final_areas) / len(final_areas)
        final_variance = sum((a - final_avg) ** 2 for a in final_areas) / len(final_areas)
        final_cv = (final_variance ** 0.5) / final_avg if final_avg > 0 else 0
        print(f"  Final area balance: CV={final_cv:.3f}")

        return polygons

    def _create_hybrid_divisions_preview(
        self, polygon: Polygon, num_divisions: int, incident_location: Point, road_lines: List
    ) -> List[Dict]:
        """Create grid divisions but snap boundaries to nearby roads where possible"""
        # Start with grid divisions
        grid_divisions = self._create_grid_divisions_preview(polygon, num_divisions, incident_location)

        # TODO: Enhance by snapping division boundaries to nearby roads
        # For now, return grid divisions with awareness that roads exist

        return grid_divisions

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
