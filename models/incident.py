import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib

import requests
from shapely.geometry import Point, Polygon, LineString, MultiLineString, MultiPolygon
from shapely.ops import unary_union, polygonize
import numpy as np

try:
    from scipy.spatial import Voronoi
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available, will use PostGIS for Voronoi generation")

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
        self._road_cache = {}

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
        self, search_area_coordinates: List, area_size_m2: int = 40000
    ) -> List[Dict]:
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

            # Try road-aware divisions first
            try:
                road_data = self._fetch_road_data(polygon)
                if road_data:
                    divisions = self._create_voronoi_road_divisions_preview(
                        polygon, num_divisions, self.incident_location, road_data
                    )
                    if divisions:
                        return divisions
            except Exception as e:
                print(f"Voronoi road-aware division failed, falling back to grid: {e}")

            # Fallback to grid divisions
            divisions = self._create_grid_divisions_preview(
                polygon, num_divisions, self.incident_location
            )

            return divisions

        except Exception as e:
            print(f"Failed to generate divisions preview: {e}")
            raise e

    def _fetch_road_data(self, polygon: Polygon) -> List[LineString]:
        """Fetch road data from Overpass API within polygon bounds"""
        try:
            # Create cache key from polygon bounds
            bounds = polygon.bounds
            cache_key = hashlib.md5(str(bounds).encode()).hexdigest()
            
            # Check cache first
            if cache_key in self._road_cache:
                return self._road_cache[cache_key]

            # Build Overpass API query
            overpass_url = "https://overpass-api.de/api/interpreter"
            
            # Query for major roads (highways, primary, secondary, tertiary)
            query = f"""
            [out:json][timeout:25];
            (
              way["highway"~"^(motorway|trunk|primary|secondary|tertiary|residential)$"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
            );
            out geom;
            """

            response = requests.post(overpass_url, data=query, timeout=30)
            
            if response.status_code != 200:
                print(f"Overpass API error: {response.status_code}")
                return []

            data = response.json()
            roads = []

            for element in data.get("elements", []):
                if element["type"] == "way" and "geometry" in element:
                    coords = [(node["lon"], node["lat"]) for node in element["geometry"]]
                    if len(coords) >= 2:
                        try:
                            line = LineString(coords)
                            # Only include roads that intersect our polygon
                            if polygon.intersects(line):
                                roads.append(line)
                        except Exception as e:
                            print(f"Error creating LineString: {e}")
                            continue

            # Cache the result
            self._road_cache[cache_key] = roads
            print(f"Fetched {len(roads)} roads for area")
            return roads

        except Exception as e:
            print(f"Failed to fetch road data: {e}")
            return []

    def _create_voronoi_road_divisions_preview(
        self, polygon: Polygon, num_divisions: int, incident_location: Point = None, roads: List[LineString] = None
    ) -> List[Dict]:
        """Create road-aware divisions using Voronoi diagram with road-based seed points"""
        try:
            if not roads:
                return []

            print(f"Creating Voronoi road-aware divisions with {len(roads)} roads")
            
            # Step 1: Extract road centerlines and create seed points
            seed_points = self._generate_road_seed_points(roads, polygon, num_divisions)
            
            if len(seed_points) < 2:
                print("Not enough seed points for Voronoi diagram")
                return []

            print(f"Generated {len(seed_points)} seed points from roads")

            # Step 2: Generate Voronoi diagram
            voronoi_cells = self._generate_voronoi_cells(seed_points, polygon)
            
            if not voronoi_cells:
                print("Failed to generate Voronoi cells")
                return []

            print(f"Generated {len(voronoi_cells)} Voronoi cells")

            # Step 3: Create divisions from Voronoi cells
            divisions = []
            for i, cell in enumerate(voronoi_cells[:num_divisions]):
                if i >= num_divisions:
                    break
                    
                try:
                    if hasattr(cell, 'exterior') and cell.area > 0.000001:
                        coords = list(cell.exterior.coords)
                        
                        division_letter = chr(65 + i)
                        division_name = f"Division {division_letter}"
                        division_id = f"DIV-{division_letter}"

                        priority = self._calculate_division_priority(
                            cell, incident_location, divisions
                        )

                        divisions.append({
                            "division_name": division_name,
                            "division_id": division_id,
                            "coordinates": coords,
                            "estimated_area_m2": self._calculate_area_m2(cell),
                            "status": "unassigned",
                            "priority": priority,
                            "search_type": "primary",
                            "estimated_duration": "2 hours",
                        })
                        
                except Exception as e:
                    print(f"Error creating division from Voronoi cell: {e}")
                    continue

            # Step 4: If we need more divisions, subdivide existing ones
            if len(divisions) < num_divisions and len(divisions) > 0:
                print(f"Voronoi created {len(divisions)} divisions, need {num_divisions}. Subdividing...")
                divisions = self._subdivide_divisions(divisions, num_divisions, polygon)

            print(f"Successfully created {len(divisions)} Voronoi road-aware divisions")
            return divisions

        except Exception as e:
            print(f"Voronoi road-aware division creation failed: {e}")
            return []

    def _generate_road_seed_points(self, roads: List[LineString], polygon: Polygon, target_divisions: int) -> List[Tuple[float, float]]:
        """Generate evenly spaced seed points along road centerlines"""
        try:
            seed_points = []
            
            # Filter roads to only those significantly within our polygon
            major_roads = []
            for road in roads:
                try:
                    intersection = polygon.intersection(road)
                    if isinstance(intersection, LineString) and intersection.length > 0.001:
                        major_roads.append(intersection)
                    elif hasattr(intersection, 'geoms'):
                        for geom in intersection.geoms:
                            if isinstance(geom, LineString) and geom.length > 0.001:
                                major_roads.append(geom)
                except Exception as e:
                    print(f"Error filtering road: {e}")
                    continue

            if not major_roads:
                return []

            # Calculate total road length to determine point spacing
            total_length = sum(road.length for road in major_roads)
            
            # Target spacing based on number of divisions desired
            # Use more points than divisions to ensure good coverage
            target_points = max(target_divisions * 2, 10)
            spacing = total_length / target_points if total_length > 0 else 0.001

            print(f"Total road length: {total_length:.6f}, target spacing: {spacing:.6f}")

            # Place points along each road
            for road in major_roads:
                try:
                    road_length = road.length
                    if road_length <= 0:
                        continue
                        
                    # Number of points for this road proportional to its length
                    num_points_on_road = max(1, int(road_length / spacing))
                    
                    for i in range(num_points_on_road):
                        # Calculate distance along the road
                        distance = (i / max(1, num_points_on_road - 1)) * road_length if num_points_on_road > 1 else 0.5 * road_length
                        
                        # Get point at that distance
                        point = road.interpolate(distance)
                        if point and hasattr(point, 'x') and hasattr(point, 'y'):
                            # Ensure point is within polygon
                            if polygon.contains(point) or polygon.touches(point):
                                seed_points.append((point.x, point.y))
                                
                except Exception as e:
                    print(f"Error placing points on road: {e}")
                    continue

            # Add some boundary points to ensure good coverage at edges
            bounds = polygon.bounds
            boundary_points = [
                (bounds[0] + (bounds[2] - bounds[0]) * 0.1, bounds[1] + (bounds[3] - bounds[1]) * 0.1),
                (bounds[0] + (bounds[2] - bounds[0]) * 0.9, bounds[1] + (bounds[3] - bounds[1]) * 0.1),
                (bounds[0] + (bounds[2] - bounds[0]) * 0.1, bounds[1] + (bounds[3] - bounds[1]) * 0.9),
                (bounds[0] + (bounds[2] - bounds[0]) * 0.9, bounds[1] + (bounds[3] - bounds[1]) * 0.9),
            ]
            
            for bp in boundary_points:
                boundary_point = Point(bp)
                if polygon.contains(boundary_point):
                    seed_points.append(bp)

            # Remove duplicate points
            unique_points = []
            tolerance = spacing / 10  # 10% of spacing
            for point in seed_points:
                is_duplicate = False
                for existing in unique_points:
                    if abs(point[0] - existing[0]) < tolerance and abs(point[1] - existing[1]) < tolerance:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    unique_points.append(point)

            print(f"Generated {len(unique_points)} unique seed points")
            return unique_points

        except Exception as e:
            print(f"Error generating road seed points: {e}")
            return []

    def _generate_voronoi_cells(self, seed_points: List[Tuple[float, float]], polygon: Polygon) -> List[Polygon]:
        """Generate Voronoi cells from seed points and clip to polygon boundary"""
        try:
            if len(seed_points) < 2:
                return []

            # Try scipy Voronoi first (faster and more reliable)
            if SCIPY_AVAILABLE:
                return self._generate_voronoi_cells_scipy(seed_points, polygon)
            else:
                return self._generate_voronoi_cells_postgis(seed_points, polygon)

        except Exception as e:
            print(f"Error generating Voronoi cells: {e}")
            return []

    def _generate_voronoi_cells_scipy(self, seed_points: List[Tuple[float, float]], polygon: Polygon) -> List[Polygon]:
        """Generate Voronoi cells using scipy.spatial.Voronoi"""
        try:
            points = np.array(seed_points)
            
            # Create Voronoi diagram
            vor = Voronoi(points)
            
            voronoi_polygons = []
            
            # Convert Voronoi regions to polygons
            for region_idx in vor.regions:
                if len(region_idx) >= 3 and -1 not in region_idx:  # Valid finite region
                    try:
                        # Get vertices for this region
                        region_vertices = [vor.vertices[i] for i in region_idx]
                        
                        # Create polygon from vertices
                        if len(region_vertices) >= 3:
                            vor_poly = Polygon(region_vertices)
                            
                            # Clip to search area
                            if polygon.intersects(vor_poly):
                                clipped = polygon.intersection(vor_poly)
                                
                                if hasattr(clipped, 'area') and clipped.area > 0.000001:
                                    if hasattr(clipped, 'exterior'):
                                        voronoi_polygons.append(clipped)
                                    elif hasattr(clipped, 'geoms'):
                                        for geom in clipped.geoms:
                                            if hasattr(geom, 'area') and geom.area > 0.000001 and hasattr(geom, 'exterior'):
                                                voronoi_polygons.append(geom)
                                                
                    except Exception as e:
                        print(f"Error processing Voronoi region: {e}")
                        continue

            # Sort by area (largest first) for consistent ordering
            voronoi_polygons.sort(key=lambda p: p.area, reverse=True)
            
            print(f"Scipy Voronoi generated {len(voronoi_polygons)} valid cells")
            return voronoi_polygons

        except Exception as e:
            print(f"Error in scipy Voronoi generation: {e}")
            return []

    def _generate_voronoi_cells_postgis(self, seed_points: List[Tuple[float, float]], polygon: Polygon) -> List[Polygon]:
        """Generate Voronoi cells using PostGIS ST_VoronoiPolygons as fallback"""
        try:
            # Create points collection for PostGIS
            points_wkt = "MULTIPOINT(" + ", ".join([f"({p[0]} {p[1]})" for p in seed_points]) + ")"
            
            # Get polygon boundary for clipping
            polygon_wkt = polygon.wkt
            
            # Use PostGIS to generate Voronoi diagram
            query = """
            WITH voronoi_cells AS (
                SELECT (ST_Dump(ST_VoronoiPolygons(ST_GeomFromText(%s, 4326)))).geom as cell_geom
            )
            SELECT ST_AsText(ST_Intersection(cell_geom, ST_GeomFromText(%s, 4326))) as clipped_geom
            FROM voronoi_cells
            WHERE ST_Intersects(cell_geom, ST_GeomFromText(%s, 4326))
            AND ST_Area(ST_Intersection(cell_geom, ST_GeomFromText(%s, 4326))) > 0.000001
            ORDER BY ST_Area(ST_Intersection(cell_geom, ST_GeomFromText(%s, 4326))) DESC
            """
            
            result = self.db.execute_query(
                query, 
                (points_wkt, polygon_wkt, polygon_wkt, polygon_wkt, polygon_wkt), 
                fetch=True
            )
            
            voronoi_polygons = []
            if result:
                for row in result:
                    try:
                        wkt_geom = row[0]
                        if wkt_geom and wkt_geom.startswith('POLYGON'):
                            # Parse WKT back to Shapely polygon
                            from shapely import wkt
                            geom = wkt.loads(wkt_geom)
                            if hasattr(geom, 'area') and geom.area > 0.000001:
                                voronoi_polygons.append(geom)
                    except Exception as e:
                        print(f"Error parsing PostGIS Voronoi result: {e}")
                        continue

            print(f"PostGIS Voronoi generated {len(voronoi_polygons)} valid cells")
            return voronoi_polygons

        except Exception as e:
            print(f"Error in PostGIS Voronoi generation: {e}")
            return []

    def _subdivide_divisions(self, divisions: List[Dict], target_count: int, search_area: Polygon) -> List[Dict]:
        """Subdivide existing divisions to reach target count"""
        try:
            all_divisions = []
            
            # Sort divisions by area (largest first) to subdivide biggest ones
            sorted_divisions = sorted(divisions, key=lambda d: d.get('estimated_area_m2', 0), reverse=True)
            
            divisions_needed = target_count - len(divisions)
            divisions_to_subdivide = min(divisions_needed, len(sorted_divisions))
            
            for i, division in enumerate(sorted_divisions):
                if i < divisions_to_subdivide and len(all_divisions) < target_count:
                    # Subdivide this division
                    sub_divisions = self._subdivide_single_division(division, search_area)
                    all_divisions.extend(sub_divisions)
                elif len(all_divisions) < target_count:
                    # Keep original division
                    all_divisions.append(division)
                    
                # Stop if we have enough divisions
                if len(all_divisions) >= target_count:
                    break
            
            # Trim to exact target count and rename ALL divisions sequentially
            final_divisions = all_divisions[:target_count]
            
            for i, division in enumerate(final_divisions):
                if i < 26:
                    division_letter = chr(65 + i)  # A-Z
                else:
                    # After Z, use AA, AB, AC, etc.
                    first_letter = chr(65 + (i - 26) // 26)
                    second_letter = chr(65 + (i - 26) % 26)
                    division_letter = f"{first_letter}{second_letter}"
                
                division['division_name'] = f"Division {division_letter}"
                division['division_id'] = f"DIV-{division_letter}"
            
            print(f"Subdivided {divisions_to_subdivide} divisions, total now: {len(final_divisions)}")
            return final_divisions
            
        except Exception as e:
            print(f"Error subdividing divisions: {e}")
            return divisions

    def _subdivide_single_division(self, division: Dict, search_area: Polygon) -> List[Dict]:
        """Subdivide a single division into two halves"""
        try:
            coords = division.get('coordinates', [])
            if not coords:
                return [division]
            
            # Create polygon from coordinates
            poly = Polygon(coords)
            bounds = poly.bounds
            
            # Determine split direction based on aspect ratio
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]
            
            if width > height:
                # Split vertically (east/west)
                mid_x = (bounds[0] + bounds[2]) / 2
                west_box = Polygon([
                    (bounds[0], bounds[1]),
                    (mid_x, bounds[1]),
                    (mid_x, bounds[3]),
                    (bounds[0], bounds[3])
                ])
                east_box = Polygon([
                    (mid_x, bounds[1]),
                    (bounds[2], bounds[1]),
                    (bounds[2], bounds[3]),
                    (mid_x, bounds[3])
                ])
                boxes = [west_box, east_box]
            else:
                # Split horizontally (north/south)
                mid_y = (bounds[1] + bounds[3]) / 2
                south_box = Polygon([
                    (bounds[0], bounds[1]),
                    (bounds[2], bounds[1]),
                    (bounds[2], mid_y),
                    (bounds[0], mid_y)
                ])
                north_box = Polygon([
                    (bounds[0], mid_y),
                    (bounds[2], mid_y),
                    (bounds[2], bounds[3]),
                    (bounds[0], bounds[3])
                ])
                boxes = [south_box, north_box]
            
            subdivisions = []
            for i, box in enumerate(boxes):
                try:
                    # Intersect with original division and search area
                    clipped = poly.intersection(box)
                    if search_area:
                        clipped = search_area.intersection(clipped)
                    
                    if hasattr(clipped, 'area') and clipped.area > 0.000001:
                        # Handle MultiPolygon case
                        if hasattr(clipped, 'exterior'):
                            geoms = [clipped]
                        elif hasattr(clipped, 'geoms'):
                            geoms = [g for g in clipped.geoms if hasattr(g, 'area') and g.area > 0.000001]
                        else:
                            continue
                        
                        for geom in geoms:
                            if hasattr(geom, 'exterior'):
                                sub_coords = list(geom.exterior.coords)
                                
                                # Create new division (names will be assigned later)
                                sub_division = {
                                    'division_name': f"temp_{i}",  # Temporary name
                                    'division_id': f"temp_{i}",    # Temporary ID
                                    'coordinates': sub_coords,
                                    'estimated_area_m2': self._calculate_area_m2(geom),
                                    'status': division.get('status', 'unassigned'),
                                    'priority': division.get('priority', 'Low'),
                                    'search_type': division.get('search_type', 'primary'),
                                    'estimated_duration': division.get('estimated_duration', '2 hours'),
                                }
                                subdivisions.append(sub_division)
                
                except Exception as e:
                    print(f"Error creating subdivision {i}: {e}")
                    continue
            
            # If subdivision failed, return original
            if not subdivisions:
                return [division]
            
            return subdivisions
            
        except Exception as e:
            print(f"Error subdividing single division: {e}")
            return [division]

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
        """Save divisions to database"""
        try:
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

                    query = """
                    INSERT INTO search_divisions 
                    (incident_id, division_name, division_id, area_geometry, 
                     estimated_area_m2, status, priority, 
                     search_type, estimated_duration, assigned_team)
                    VALUES (%s, %s, %s, ST_GeomFromText(%s, 4326), %s, %s, %s, %s, %s, %s)
                    """

                    params = (
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
        """Get search divisions for this incident"""
        try:
            query = """
            SELECT 
                id, division_name, division_id, estimated_area_m2,
                assigned_team, team_leader, priority, search_type,
                estimated_duration, status, assigned_unit_id,
                ST_AsGeoJSON(area_geometry) as geometry_geojson
            FROM search_divisions
            WHERE incident_id = %s
            ORDER BY priority DESC, division_name
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

            # Try road-aware divisions first
            try:
                road_data = self._fetch_road_data(self.search_area)
                if road_data:
                    divisions = self._create_voronoi_road_divisions(num_divisions, road_data)
                    if divisions:
                        self._save_divisions(divisions)
                        return divisions
            except Exception as e:
                print(f"Voronoi road-aware division failed, falling back to grid: {e}")

            # Fallback to grid divisions
            divisions = self._create_grid_divisions(num_divisions)
            self._save_divisions(divisions)
            return divisions

        except Exception as e:
            print(f"Failed to generate divisions: {e}")
            return []

    def _create_voronoi_road_divisions(self, num_divisions: int, roads: List[LineString]) -> List[Dict]:
        """Create road-aware divisions using Voronoi diagram with road-based seed points"""
        try:
            if not roads:
                return []

            print(f"Creating Voronoi road-aware divisions with {len(roads)} roads")
            
            # Generate seed points from roads
            seed_points = self._generate_road_seed_points(roads, self.search_area, num_divisions)
            
            if len(seed_points) < 2:
                print("Not enough seed points for Voronoi diagram")
                return []

            # Generate Voronoi cells
            voronoi_cells = self._generate_voronoi_cells(seed_points, self.search_area)
            
            if not voronoi_cells:
                print("Failed to generate Voronoi cells")
                return []

            # Create divisions from Voronoi cells
            divisions = []
            for i, cell in enumerate(voronoi_cells[:num_divisions]):
                if i >= num_divisions:
                    break
                    
                try:
                    division_letter = chr(65 + i)
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    priority = self._calculate_division_priority(
                        cell, self.incident_location, divisions
                    )

                    divisions.append({
                        "name": division_name,
                        "division_id": division_id,
                        "geometry": cell,
                        "area_m2": self._calculate_area_m2(cell),
                        "status": "unassigned",
                        "priority": priority,
                        "search_type": "primary",
                        "estimated_duration": "2 hours",
                    })
                        
                except Exception as e:
                    print(f"Error creating division from Voronoi cell: {e}")
                    continue

            print(f"Successfully created {len(divisions)} Voronoi road-aware divisions")
            return divisions

        except Exception as e:
            print(f"Voronoi road-aware division creation failed: {e}")
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
