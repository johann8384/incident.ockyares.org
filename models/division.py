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
        # Converting to degrees: approximately 0.011 degrees per 1000 meters
        self.ROAD_SEGMENT_DISTANCE_DEGREES = 0.013  # ~1219 meters / 4000 feet
        # Initial buffer for road corridors (start small and expand)
        self.INITIAL_ROAD_BUFFER_DEGREES = 0.002  # ~200 meters

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
        """Create road-centric divisions by segmenting roads and expanding into corridors"""
        try:
            if not roads:
                return []

            print(f"Creating road-centric divisions with {len(roads)} roads")
            
            # Step 1: Filter and segment roads into 4000-foot chunks
            road_segments = self._segment_roads_into_chunks(roads, polygon)
            
            if not road_segments:
                print("No road segments created")
                return []

            print(f"Created {len(road_segments)} road segments")

            # Step 2: Create initial corridors for each road segment
            road_corridors = self._create_road_corridors(road_segments, polygon)
            
            if not road_corridors:
                print("No road corridors created")
                return []

            print(f"Created {len(road_corridors)} road corridors")

            # Step 3: Expand corridors to fill entire search area
            expanded_divisions = self._expand_corridors_to_fill_area(road_corridors, polygon)
            
            if not expanded_divisions:
                print("Failed to expand corridors")
                return []

            # Step 4: Convert to division format
            divisions = []
            for i, corridor in enumerate(expanded_divisions):
                try:
                    if hasattr(corridor, 'exterior') and corridor.area > 0.000001:
                        coords = list(corridor.exterior.coords)
                        
                        division_letter = chr(65 + i) if i < 26 else f"A{chr(65 + (i-26))}"
                        division_name = f"Division {division_letter}"
                        division_id = f"DIV-{division_letter}"

                        priority = self._calculate_division_priority(
                            corridor, incident_location, divisions
                        )

                        divisions.append({
                            "division_name": division_name,
                            "division_id": division_id,
                            "coordinates": coords,
                            "estimated_area_m2": self._calculate_area_m2(corridor),
                            "status": "unassigned",
                            "priority": priority,
                            "search_type": "primary",
                            "estimated_duration": "2 hours",
                        })
                        
                except Exception as e:
                    print(f"Error creating division from corridor: {e}")
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

            # Create corridors
            road_corridors = self._create_road_corridors(road_segments, search_area)
            
            if not road_corridors:
                return []

            # Expand to fill area
            expanded_divisions = self._expand_corridors_to_fill_area(road_corridors, search_area)
            
            if not expanded_divisions:
                return []

            # Convert to division format
            divisions = []
            for i, corridor in enumerate(expanded_divisions):
                try:
                    division_letter = chr(65 + i) if i < 26 else f"A{chr(65 + (i-26))}"
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    priority = self._calculate_division_priority(
                        corridor, incident_location, divisions
                    )

                    divisions.append({
                        "name": division_name,
                        "division_id": division_id,
                        "geometry": corridor,
                        "area_m2": self._calculate_area_m2(corridor),
                        "status": "unassigned",
                        "priority": priority,
                        "search_type": "primary",
                        "estimated_duration": "2 hours",
                    })
                        
                except Exception as e:
                    print(f"Error creating division from corridor: {e}")
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
                    # Extract segment
                    start_point = line.interpolate(start_distance)
                    end_point = line.interpolate(end_distance)
                    
                    # Create line segment from points along the original line
                    segment_coords = []
                    
                    # Add start point
                    segment_coords.append((start_point.x, start_point.y))
                    
                    # Add intermediate points to follow the road
                    num_intermediate = max(1, int((end_distance - start_distance) / (segment_length / 10)))
                    for j in range(1, num_intermediate):
                        intermediate_distance = start_distance + (j * (end_distance - start_distance) / num_intermediate)
                        intermediate_point = line.interpolate(intermediate_distance)
                        segment_coords.append((intermediate_point.x, intermediate_point.y))
                    
                    # Add end point
                    segment_coords.append((end_point.x, end_point.y))
                    
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

    def _create_road_corridors(self, road_segments: List[LineString], polygon: Polygon) -> List[Polygon]:
        """Create initial buffer corridors around road segments"""
        try:
            corridors = []
            
            for segment in road_segments:
                try:
                    # Create initial buffer around road segment
                    corridor = segment.buffer(self.INITIAL_ROAD_BUFFER_DEGREES)
                    
                    # Clip to search area
                    clipped_corridor = polygon.intersection(corridor)
                    
                    if hasattr(clipped_corridor, 'area') and clipped_corridor.area > 0.000001:
                        if isinstance(clipped_corridor, Polygon):
                            corridors.append(clipped_corridor)
                        elif isinstance(clipped_corridor, MultiPolygon):
                            # Take the largest polygon from multipolygon
                            largest = max(clipped_corridor.geoms, key=lambda g: g.area)
                            corridors.append(largest)
                            
                except Exception as e:
                    print(f"Error creating corridor: {e}")
                    continue
            
            print(f"Created {len(corridors)} initial corridors")
            return corridors
            
        except Exception as e:
            print(f"Error creating road corridors: {e}")
            return []

    def _expand_corridors_to_fill_area(self, corridors: List[Polygon], polygon: Polygon) -> List[Polygon]:
        """Expand road corridors until they fill the entire search area"""
        try:
            if not corridors:
                return []
            
            expanded_corridors = corridors.copy()
            max_iterations = 20
            buffer_increment = 0.001  # Small increment for expansion
            
            for iteration in range(max_iterations):
                # Calculate current coverage
                current_coverage = unary_union(expanded_corridors)
                uncovered = polygon.difference(current_coverage)
                
                if hasattr(uncovered, 'area') and uncovered.area < 0.000001:
                    print(f"Complete coverage achieved in {iteration} iterations")
                    break
                
                # Expand each corridor slightly
                new_corridors = []
                for corridor in expanded_corridors:
                    try:
                        # Expand corridor
                        expanded = corridor.buffer(buffer_increment)
                        
                        # Clip to search area
                        clipped = polygon.intersection(expanded)
                        
                        if hasattr(clipped, 'area') and clipped.area > 0.000001:
                            if isinstance(clipped, Polygon):
                                new_corridors.append(clipped)
                            elif isinstance(clipped, MultiPolygon):
                                largest = max(clipped.geoms, key=lambda g: g.area)
                                new_corridors.append(largest)
                        else:
                            # Keep original if expansion failed
                            new_corridors.append(corridor)
                            
                    except Exception as e:
                        print(f"Error expanding corridor: {e}")
                        new_corridors.append(corridor)  # Keep original
                
                expanded_corridors = new_corridors
                
                # Prevent infinite expansion
                if iteration % 5 == 0:
                    buffer_increment *= 1.5  # Increase expansion rate
            
            # Final step: ensure no overlaps by using Voronoi-like approach
            final_corridors = self._resolve_corridor_overlaps(expanded_corridors, polygon)
            
            print(f"Final expanded corridors: {len(final_corridors)}")
            return final_corridors
            
        except Exception as e:
            print(f"Error expanding corridors: {e}")
            return corridors

    def _resolve_corridor_overlaps(self, corridors: List[Polygon], polygon: Polygon) -> List[Polygon]:
        """Resolve overlaps between expanded corridors"""
        try:
            if len(corridors) <= 1:
                return corridors
            
            # Create seed points from corridor centroids
            seed_points = []
            for corridor in corridors:
                centroid = corridor.centroid
                seed_points.append((centroid.x, centroid.y))
            
            # Use Voronoi to create non-overlapping regions
            if SCIPY_AVAILABLE and len(seed_points) >= 2:
                try:
                    points = np.array(seed_points)
                    bounds = polygon.bounds
                    margin = max((bounds[2] - bounds[0]), (bounds[3] - bounds[1])) * 0.5
                    
                    # Add boundary points
                    boundary_points = [
                        (bounds[0] - margin, bounds[1] - margin),
                        (bounds[2] + margin, bounds[1] - margin),
                        (bounds[2] + margin, bounds[3] + margin),
                        (bounds[0] - margin, bounds[3] + margin),
                    ]
                    
                    all_points = np.vstack([points, np.array(boundary_points)])
                    vor = Voronoi(all_points)
                    
                    resolved_corridors = []
                    for i in range(len(seed_points)):
                        for region_idx, region in enumerate(vor.regions):
                            if len(region) >= 3 and -1 not in region:
                                try:
                                    region_vertices = [vor.vertices[j] for j in region]
                                    region_poly = Polygon(region_vertices)
                                    
                                    seed_point = Point(seed_points[i])
                                    if region_poly.contains(seed_point):
                                        clipped = polygon.intersection(region_poly)
                                        if hasattr(clipped, 'area') and clipped.area > 0.000001:
                                            if isinstance(clipped, Polygon):
                                                resolved_corridors.append(clipped)
                                        break
                                except:
                                    continue
                    
                    if resolved_corridors:
                        print(f"Resolved overlaps using Voronoi: {len(resolved_corridors)} corridors")
                        return resolved_corridors
                        
                except Exception as e:
                    print(f"Voronoi overlap resolution failed: {e}")
            
            # Fallback: return original corridors
            return corridors
            
        except Exception as e:
            print(f"Error resolving overlaps: {e}")
            return corridors

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
                    division_letter = chr(65 + division_counter)  # A, B, C, etc.
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    # Calculate priority based on incident location
                    priority = self._calculate_division_priority(
                        clipped, incident_location, divisions
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
