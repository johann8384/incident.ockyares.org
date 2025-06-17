import hashlib
from typing import Dict, List, Optional, Tuple
import numpy as np

import requests
from shapely.geometry import Point, Polygon, LineString, MultiPolygon
from shapely.ops import unary_union

try:
    from scipy.spatial import Voronoi
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available, will use PostGIS for Voronoi generation")

from .database import DatabaseManager


class DivisionManager:
    """Manages search area divisions with road-aware and grid-based generation"""

    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()
        self._road_cache = {}
        # Distance for road segments (4000 feet = ~1219 meters)
        self.ROAD_SEGMENT_DISTANCE_DEGREES = 0.013  # ~1219 meters / 4000 feet

    def generate_divisions_preview(
        self, 
        search_area_coordinates: List, 
        area_size_m2: int = 40000,
        incident_location: Point = None
    ) -> List[Dict]:
        """Generate divisions for preview without saving to database"""
        try:
            if not search_area_coordinates or len(search_area_coordinates) < 3:
                raise ValueError("At least 3 coordinates required for search area")

            # Convert coordinates to shapely polygon
            polygon_coords = [(coord[0], coord[1]) for coord in search_area_coordinates]
            polygon = Polygon(polygon_coords)

            # Try road-centric divisions first
            try:
                road_data = self._fetch_road_data(polygon)
                if road_data:
                    divisions = self._create_road_centric_divisions_preview(
                        polygon, incident_location, road_data
                    )
                    if divisions:
                        return divisions
            except Exception as e:
                print(f"Road-centric division failed, falling back to grid: {e}")

            # Calculate area and number of divisions for grid fallback
            area_m2 = self._calculate_area_m2(polygon)
            num_divisions = max(1, int(area_m2 / area_size_m2))

            # Fallback to grid divisions
            divisions = self._create_grid_divisions_preview(
                polygon, num_divisions, incident_location
            )

            return divisions

        except Exception as e:
            print(f"Failed to generate divisions preview: {e}")
            raise e

    def generate_divisions(
        self, 
        incident_id: str,
        search_area: Polygon, 
        area_size_m2: int = 40000,
        incident_location: Point = None
    ) -> List[Dict]:
        """Generate and save search divisions for an incident"""
        try:
            # Clear existing divisions
            self._clear_existing_divisions(incident_id)

            # Try road-centric divisions first
            try:
                road_data = self._fetch_road_data(search_area)
                if road_data:
                    divisions = self._create_road_centric_divisions(
                        search_area, incident_location, road_data
                    )
                    if divisions:
                        self._save_divisions(incident_id, divisions)
                        return divisions
            except Exception as e:
                print(f"Road-centric division failed, falling back to grid: {e}")

            # Calculate approximate number of divisions needed for grid fallback
            area_m2 = self._calculate_area_m2(search_area)
            num_divisions = max(1, int(area_m2 / area_size_m2))

            # Fallback to grid divisions
            divisions = self._create_grid_divisions(search_area, num_divisions, incident_location)
            self._save_divisions(incident_id, divisions)
            return divisions

        except Exception as e:
            print(f"Failed to generate divisions: {e}")
            return []

    def _create_road_centric_divisions_preview(
        self, polygon: Polygon, incident_location: Point = None, roads: List[LineString] = None
    ) -> List[Dict]:
        """Create road-centric divisions using Voronoi with road segment centroids"""
        try:
            if not roads:
                return []

            print(f"Creating road-centric divisions with {len(roads)} roads")
            
            # Step 1: Segment roads into 4000-foot chunks
            road_segments = self._segment_roads_into_chunks(roads, polygon)
            
            if not road_segments:
                print("No road segments created")
                return []

            print(f"Created {len(road_segments)} road segments")

            # Step 2: Create Voronoi diagram using road segment centroids
            division_polygons = self._create_voronoi_from_road_segments(road_segments, polygon)
            
            if not division_polygons:
                print("No Voronoi divisions created")
                return []

            print(f"Created {len(division_polygons)} Voronoi divisions")

            # Step 3: Convert to division format
            divisions = []
            for i, division_poly in enumerate(division_polygons):
                try:
                    if hasattr(division_poly, 'exterior') and division_poly.area > 0.000001:
                        coords = list(division_poly.exterior.coords)
                        
                        division_letter = chr(65 + i) if i < 26 else f"A{chr(65 + (i-26))}"
                        division_name = f"Division {division_letter}"
                        division_id = f"DIV-{division_letter}"

                        priority = self._calculate_division_priority(
                            division_poly, incident_location, divisions
                        )

                        divisions.append({
                            "division_name": division_name,
                            "division_id": division_id,
                            "coordinates": coords,
                            "estimated_area_m2": self._calculate_area_m2(division_poly),
                            "status": "unassigned",
                            "priority": priority,
                            "search_type": "primary",
                            "estimated_duration": "2 hours",
                        })
                        
                except Exception as e:
                    print(f"Error creating division from polygon: {e}")
                    continue

            print(f"Successfully created {len(divisions)} road-centric divisions")
            return divisions

        except Exception as e:
            print(f"Road-centric division creation failed: {e}")
            return []

    def _create_road_centric_divisions(
        self, search_area: Polygon, incident_location: Point = None, roads: List[LineString] = None
    ) -> List[Dict]:
        """Create road-centric divisions - for actual generation"""
        try:
            if not roads:
                return []

            print(f"Creating road-centric divisions with {len(roads)} roads")
            
            # Segment roads into chunks
            road_segments = self._segment_roads_into_chunks(roads, search_area)
            
            if not road_segments:
                return []

            # Create Voronoi from road segments
            division_polygons = self._create_voronoi_from_road_segments(road_segments, search_area)
            
            if not division_polygons:
                return []

            # Convert to division format
            divisions = []
            for i, division_poly in enumerate(division_polygons):
                try:
                    division_letter = chr(65 + i) if i < 26 else f"A{chr(65 + (i-26))}"
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    priority = self._calculate_division_priority(
                        division_poly, incident_location, divisions
                    )

                    divisions.append({
                        "name": division_name,
                        "division_id": division_id,
                        "geometry": division_poly,
                        "area_m2": self._calculate_area_m2(division_poly),
                        "status": "unassigned",
                        "priority": priority,
                        "search_type": "primary",
                        "estimated_duration": "2 hours",
                    })
                        
                except Exception as e:
                    print(f"Error creating division from polygon: {e}")
                    continue

            print(f"Successfully created {len(divisions)} road-centric divisions")
            return divisions

        except Exception as e:
            print(f"Road-centric division creation failed: {e}")
            return []

    def _segment_roads_into_chunks(self, roads: List[LineString], polygon: Polygon) -> List[LineString]:
        """Segment roads into 4000-foot chunks within the search area"""
        try:
            road_segments = []
            
            for road_idx, road in enumerate(roads):
                try:
                    # Clip road to search area
                    clipped_road = polygon.intersection(road)
                    
                    # Handle different intersection results
                    road_lines = []
                    if isinstance(clipped_road, LineString):
                        road_lines = [clipped_road]
                    elif hasattr(clipped_road, 'geoms'):
                        road_lines = [geom for geom in clipped_road.geoms 
                                    if isinstance(geom, LineString) and geom.length > 0.001]
                    
                    # Segment each road line into chunks
                    for line in road_lines:
                        segments = self._segment_line_into_chunks(line)
                        road_segments.extend(segments)
                        
                except Exception as e:
                    print(f"Error processing road {road_idx}: {e}")
                    continue
            
            print(f"Segmented roads into {len(road_segments)} chunks")
            return road_segments
            
        except Exception as e:
            print(f"Error segmenting roads: {e}")
            return []

    def _segment_line_into_chunks(self, line: LineString) -> List[LineString]:
        """Segment a single road line into 4000-foot chunks"""
        try:
            segments = []
            total_length = line.length
            
            if total_length <= self.ROAD_SEGMENT_DISTANCE_DEGREES:
                # Road is shorter than segment length, keep as single segment
                return [line]
            
            # Calculate number of segments needed
            num_segments = max(1, int(total_length / self.ROAD_SEGMENT_DISTANCE_DEGREES))
            segment_length = total_length / num_segments
            
            for i in range(num_segments):
                start_distance = i * segment_length
                end_distance = min((i + 1) * segment_length, total_length)
                
                try:
                    # Extract segment by interpolating points along the line
                    segment_coords = []
                    
                    # Number of points to include in segment (to preserve road shape)
                    num_points = max(2, int((end_distance - start_distance) / (segment_length / 20)))
                    
                    for j in range(num_points):
                        distance = start_distance + (j * (end_distance - start_distance) / (num_points - 1))
                        point = line.interpolate(distance)
                        segment_coords.append((point.x, point.y))
                    
                    if len(segment_coords) >= 2:
                        segment = LineString(segment_coords)
                        segments.append(segment)
                        
                except Exception as e:
                    print(f"Error creating segment {i}: {e}")
                    continue
            
            return segments
            
        except Exception as e:
            print(f"Error segmenting line: {e}")
            return [line]  # Return original line if segmentation fails

    def _create_voronoi_from_road_segments(self, road_segments: List[LineString], polygon: Polygon) -> List[Polygon]:
        """Create Voronoi diagram using road segment centroids as seed points"""
        try:
            if len(road_segments) < 2:
                # If only one road segment, just return the entire search area
                return [polygon]
            
            # Get centroids of road segments as seed points
            seed_points = []
            for segment in road_segments:
                centroid = segment.centroid
                if polygon.contains(centroid) or polygon.touches(centroid):
                    seed_points.append((centroid.x, centroid.y))
            
            if len(seed_points) < 2:
                return [polygon]
            
            print(f"Using {len(seed_points)} seed points from road segments")
            
            # Create Voronoi diagram
            if SCIPY_AVAILABLE:
                return self._generate_voronoi_cells_scipy(seed_points, polygon)
            else:
                return self._generate_voronoi_cells_postgis(seed_points, polygon)
                
        except Exception as e:
            print(f"Error creating Voronoi from road segments: {e}")
            return []

    def _generate_voronoi_cells_scipy(self, seed_points: List[Tuple[float, float]], polygon: Polygon) -> List[Polygon]:
        """Generate Voronoi cells using scipy.spatial.Voronoi"""
        try:
            points = np.array(seed_points)
            
            # Expand bounds to ensure complete coverage
            bounds = polygon.bounds
            margin = max((bounds[2] - bounds[0]), (bounds[3] - bounds[1])) * 0.5
            
            # Add boundary points well outside the search area
            boundary_buffer_points = [
                (bounds[0] - margin, bounds[1] - margin),  # SW
                (bounds[2] + margin, bounds[1] - margin),  # SE  
                (bounds[2] + margin, bounds[3] + margin),  # NE
                (bounds[0] - margin, bounds[3] + margin),  # NW
                (bounds[0] - margin, (bounds[1] + bounds[3]) / 2),  # W
                (bounds[2] + margin, (bounds[1] + bounds[3]) / 2),  # E
                ((bounds[0] + bounds[2]) / 2, bounds[1] - margin),  # S
                ((bounds[0] + bounds[2]) / 2, bounds[3] + margin),  # N
            ]
            
            # Combine original points with boundary buffer points
            all_points = np.vstack([points, np.array(boundary_buffer_points)])
            
            # Create Voronoi diagram
            vor = Voronoi(all_points)
            
            voronoi_polygons = []
            
            # Only process regions corresponding to original seed points (not buffer points)
            for point_idx in range(len(seed_points)):
                # Find the Voronoi region containing this seed point
                for region in vor.regions:
                    if len(region) >= 3 and -1 not in region:  # Valid finite region
                        try:
                            region_vertices = [vor.vertices[i] for i in region]
                            if len(region_vertices) >= 3:
                                region_poly = Polygon(region_vertices)
                                
                                # Check if this region contains our seed point
                                seed_point = Point(seed_points[point_idx])
                                if region_poly.contains(seed_point) or region_poly.distance(seed_point) < 0.001:
                                    # Clip to search area
                                    clipped = polygon.intersection(region_poly)
                                    
                                    if hasattr(clipped, 'area') and clipped.area > 0.000001:
                                        if hasattr(clipped, 'exterior'):
                                            voronoi_polygons.append(clipped)
                                        elif hasattr(clipped, 'geoms'):
                                            # Take largest polygon from multipolygon
                                            largest = max(clipped.geoms, key=lambda g: g.area if hasattr(g, 'area') else 0)
                                            if hasattr(largest, 'exterior'):
                                                voronoi_polygons.append(largest)
                                    break
                                                
                        except Exception as e:
                            print(f"Error processing Voronoi region for point {point_idx}: {e}")
                            continue

            # Ensure complete coverage
            voronoi_polygons = self._ensure_complete_coverage(voronoi_polygons, polygon)
            
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
            # Add boundary buffer points for complete coverage
            bounds = polygon.bounds
            margin = max((bounds[2] - bounds[0]), (bounds[3] - bounds[1])) * 0.5
            
            boundary_buffer_points = [
                (bounds[0] - margin, bounds[1] - margin),  # SW
                (bounds[2] + margin, bounds[1] - margin),  # SE  
                (bounds[2] + margin, bounds[3] + margin),  # NE
                (bounds[0] - margin, bounds[3] + margin),  # NW
            ]
            
            # Combine original points with boundary buffer points
            all_points = seed_points + boundary_buffer_points
            
            # Create points collection for PostGIS
            points_wkt = "MULTIPOINT(" + ", ".join([f"({p[0]} {p[1]})" for p in all_points]) + ")"
            
            # Get polygon boundary for clipping
            polygon_wkt = polygon.wkt
            
            # Use PostGIS to generate Voronoi diagram
            query = """
            WITH voronoi_cells AS (
                SELECT (ST_Dump(ST_VoronoiPolygons(ST_GeomFromText(%s, 4326)))).geom as cell_geom
            ),
            clipped_cells AS (
                SELECT ST_Intersection(cell_geom, ST_GeomFromText(%s, 4326)) as clipped_geom
                FROM voronoi_cells
                WHERE ST_Intersects(cell_geom, ST_GeomFromText(%s, 4326))
                AND ST_Area(ST_Intersection(cell_geom, ST_GeomFromText(%s, 4326))) > 0.000001
            )
            SELECT ST_AsText(clipped_geom) as geom_wkt
            FROM clipped_cells
            WHERE ST_GeometryType(clipped_geom) = 'ST_Polygon'
            ORDER BY ST_Area(clipped_geom) DESC
            """
            
            result = self.db.execute_query(
                query, 
                (points_wkt, polygon_wkt, polygon_wkt, polygon_wkt), 
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

    def _ensure_complete_coverage(self, voronoi_polygons: List[Polygon], search_area: Polygon) -> List[Polygon]:
        """Ensure Voronoi polygons completely cover the search area with no gaps"""
        try:
            if not voronoi_polygons:
                return []
            
            # Union all Voronoi cells
            covered_area = unary_union(voronoi_polygons)
            
            # Find uncovered area (gaps)
            uncovered = search_area.difference(covered_area)
            
            # If there are gaps, add them to nearest divisions
            if hasattr(uncovered, 'area') and uncovered.area > 0.000001:
                print(f"Found uncovered area of {uncovered.area:.6f} square degrees, filling gaps...")
                
                # Handle different geometry types for uncovered areas
                gap_polygons = []
                if hasattr(uncovered, 'exterior'):
                    gap_polygons = [uncovered]
                elif hasattr(uncovered, 'geoms'):
                    gap_polygons = [g for g in uncovered.geoms 
                                  if hasattr(g, 'area') and g.area > 0.000001 and hasattr(g, 'exterior')]
                
                # For each gap, merge it with the nearest existing division
                for gap in gap_polygons:
                    try:
                        gap_centroid = gap.centroid
                        
                        # Find the nearest Voronoi cell
                        min_distance = float('inf')
                        nearest_idx = -1
                        
                        for i, cell in enumerate(voronoi_polygons):
                            try:
                                distance = cell.distance(gap_centroid)
                                if distance < min_distance:
                                    min_distance = distance
                                    nearest_idx = i
                            except:
                                continue
                        
                        # Merge the gap with the nearest cell
                        if nearest_idx >= 0:
                            try:
                                merged = unary_union([voronoi_polygons[nearest_idx], gap])
                                if hasattr(merged, 'exterior'):
                                    voronoi_polygons[nearest_idx] = merged
                                elif hasattr(merged, 'geoms'):
                                    # Take the largest component
                                    largest = max(merged.geoms, key=lambda g: g.area if hasattr(g, 'area') else 0)
                                    if hasattr(largest, 'exterior'):
                                        voronoi_polygons[nearest_idx] = largest
                                        
                            except Exception as e:
                                print(f"Error merging gap: {e}")
                                voronoi_polygons.append(gap)
                        else:
                            voronoi_polygons.append(gap)
                            
                    except Exception as e:
                        print(f"Error processing gap: {e}")
                        continue
            
            return voronoi_polygons
            
        except Exception as e:
            print(f"Error ensuring complete coverage: {e}")
            return voronoi_polygons

    def save_divisions(self, incident_id: str, divisions: List[Dict]) -> bool:
        """Save divisions to database"""
        try:
            for division in divisions:
                # Extract coordinates from division data
                coordinates = None
                if "coordinates" in division:
                    coordinates = division["coordinates"]
                elif "geom" in division and division["geom"]:
                    # Parse geometry if it's in different format
                    import json
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
                        incident_id,
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

    def get_divisions(self, incident_id: str) -> List[Dict]:
        """Get search divisions for an incident"""
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

            result = self.db.execute_query(query, (incident_id,), fetch=True)
            return [dict(row) for row in result] if result else []

        except Exception as e:
            print(f"Failed to get divisions: {e}")
            return []

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
        
        # Calculate distance from division centroid to incident location
        division_centroid = division_geom.centroid
        distance = division_centroid.distance(incident_location)
        
        # If very close to incident, make it High
        bounds = division_geom.bounds
        division_size = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
        
        if distance <= division_size * 1.5:  # Within 1.5 division widths
            return "High"
        elif distance <= division_size * 3:  # Within 3 division widths
            return "Medium"
        
        return "Low"

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

                # Create grid cell
                x1 = bounds[0] + col * width
                y1 = bounds[1] + row * height
                x2 = x1 + width
                y2 = y1 + height

                cell = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])

                # Ensure cell is valid
                if not cell.is_valid:
                    cell = cell.buffer(0)

                try:
                    # Clip to search area
                    if polygon.intersects(cell):
                        clipped = polygon.intersection(cell)

                        # Handle different geometry types
                        if hasattr(clipped, "area") and clipped.area > 0:
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
                                continue

                            division_letter = chr(65 + division_counter)
                            division_name = f"Division {division_letter}"
                            division_id = f"DIV-{division_letter}"

                            priority = self._calculate_division_priority(
                                clipped, incident_location, divisions
                            )

                            divisions.append({
                                "division_name": division_name,
                                "division_id": division_id,
                                "coordinates": coords,
                                "estimated_area_m2": self._calculate_area_m2(clipped),
                                "status": "unassigned",
                                "priority": priority,
                                "search_type": "primary",
                                "estimated_duration": "2 hours",
                            })

                            division_counter += 1

                except Exception as e:
                    print(f"Error processing grid cell {row},{col}: {e}")
                    continue

        return divisions

    def _create_grid_divisions(self, search_area: Polygon, num_divisions: int, incident_location: Point = None) -> List[Dict]:
        """Create grid-based divisions"""
        divisions = []
        bounds = search_area.bounds

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
                clipped = search_area.intersection(cell)

                if hasattr(clipped, "area") and clipped.area > 0:
                    division_letter = chr(65 + division_counter)
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    priority = self._calculate_division_priority(
                        clipped, incident_location, divisions
                    )

                    divisions.append({
                        "name": division_name,
                        "division_id": division_id,
                        "geometry": clipped,
                        "area_m2": self._calculate_area_m2(clipped),
                        "status": "unassigned",
                        "priority": priority,
                        "search_type": "primary",
                        "estimated_duration": "2 hours",
                    })

                    division_counter += 1

        return divisions

    def _save_divisions(self, incident_id: str, divisions: List[Dict]):
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
                    incident_id,
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

    def _clear_existing_divisions(self, incident_id: str):
        """Clear existing divisions for an incident"""
        query = "DELETE FROM search_divisions WHERE incident_id = %s"
        self.db.execute_query(query, (incident_id,))

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
