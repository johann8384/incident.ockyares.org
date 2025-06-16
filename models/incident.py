import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import hashlib

import requests
from shapely.geometry import Point, Polygon, LineString, MultiLineString
from shapely.ops import unary_union, polygonize

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

    def _create_road_aware_divisions_preview(
        self, polygon: Polygon, num_divisions: int, incident_location: Point = None, roads: List[LineString] = None
    ) -> List[Dict]:
        """Create road-aware divisions using roads as natural boundaries"""
        try:
            if not roads:
                return []

            print(f"Creating road-aware divisions with {len(roads)} roads")
            
            # Filter roads to only major ones within our polygon
            major_roads = []
            for road in roads:
                try:
                    # Only use roads that significantly cross our polygon
                    intersection = polygon.intersection(road)
                    if isinstance(intersection, LineString) and intersection.length > 0.001:  # Significant intersection
                        major_roads.append(road)
                    elif hasattr(intersection, 'geoms'):
                        for geom in intersection.geoms:
                            if isinstance(geom, LineString) and geom.length > 0.001:
                                major_roads.append(road)
                                break
                except Exception as e:
                    print(f"Error filtering road: {e}")
                    continue

            print(f"Filtered to {len(major_roads)} major roads")
            
            if not major_roads:
                return []

            # Create a simpler approach: use roads to create natural division boundaries
            bounds = polygon.bounds
            divisions = []
            
            # Start with a base grid but modify it based on roads
            cols = int((num_divisions**0.5)) if num_divisions > 1 else 1
            rows = int(num_divisions / cols) + (1 if num_divisions % cols else 0)

            width = (bounds[2] - bounds[0]) / cols
            height = (bounds[3] - bounds[1]) / rows

            division_counter = 0
            
            # Create horizontal and vertical division lines, but snap them to roads
            division_lines = []
            
            # Create vertical division lines (adjusted by roads)
            for i in range(1, cols):
                x = bounds[0] + i * width
                base_line = LineString([(x, bounds[1]), (x, bounds[3])])
                
                # Find nearest major road and snap to it if close
                best_road = None
                min_distance = float('inf')
                
                for road in major_roads:
                    try:
                        distance = base_line.distance(road)
                        if distance < min_distance and distance < width * 0.3:  # Within 30% of grid width
                            min_distance = distance
                            best_road = road
                    except:
                        continue
                
                if best_road:
                    # Use the road as the division line
                    road_intersection = polygon.intersection(best_road)
                    if isinstance(road_intersection, LineString):
                        division_lines.append(road_intersection)
                    elif hasattr(road_intersection, 'geoms'):
                        for geom in road_intersection.geoms:
                            if isinstance(geom, LineString):
                                division_lines.append(geom)
                else:
                    # Use original grid line
                    grid_intersection = polygon.intersection(base_line)
                    if isinstance(grid_intersection, LineString):
                        division_lines.append(grid_intersection)

            # Create horizontal division lines (adjusted by roads)
            for i in range(1, rows):
                y = bounds[1] + i * height
                base_line = LineString([(bounds[0], y), (bounds[2], y)])
                
                # Find nearest major road and snap to it if close
                best_road = None
                min_distance = float('inf')
                
                for road in major_roads:
                    try:
                        distance = base_line.distance(road)
                        if distance < min_distance and distance < height * 0.3:  # Within 30% of grid height
                            min_distance = distance
                            best_road = road
                    except:
                        continue
                
                if best_road:
                    # Use the road as the division line
                    road_intersection = polygon.intersection(best_road)
                    if isinstance(road_intersection, LineString):
                        division_lines.append(road_intersection)
                    elif hasattr(road_intersection, 'geoms'):
                        for geom in road_intersection.geoms:
                            if isinstance(geom, LineString):
                                division_lines.append(geom)
                else:
                    # Use original grid line
                    grid_intersection = polygon.intersection(base_line)
                    if isinstance(grid_intersection, LineString):
                        division_lines.append(grid_intersection)

            print(f"Created {len(division_lines)} division lines")

            # If we have division lines, try to use them to create polygons
            if division_lines:
                try:
                    # Extend division lines to ensure they create complete boundaries
                    extended_lines = []
                    polygon_boundary = polygon.boundary
                    
                    for line in division_lines:
                        coords = list(line.coords)
                        if len(coords) >= 2:
                            # Extend line to polygon boundary
                            start_point = Point(coords[0])
                            end_point = Point(coords[-1])
                            
                            # Extend line by 10% in both directions
                            dx = coords[-1][0] - coords[0][0]
                            dy = coords[-1][1] - coords[0][1]
                            
                            if abs(dx) > 0.0001 or abs(dy) > 0.0001:
                                length_factor = 0.1
                                extended_start = (coords[0][0] - dx * length_factor, coords[0][1] - dy * length_factor)
                                extended_end = (coords[-1][0] + dx * length_factor, coords[-1][1] + dy * length_factor)
                                extended_lines.append(LineString([extended_start] + coords + [extended_end]))
                            else:
                                extended_lines.append(line)
                    
                    # Add polygon boundary to help with polygonization
                    if hasattr(polygon.boundary, 'geoms'):
                        for boundary_part in polygon.boundary.geoms:
                            if isinstance(boundary_part, LineString):
                                extended_lines.append(boundary_part)
                    else:
                        extended_lines.append(polygon.boundary)
                    
                    # Create polygons from lines
                    try:
                        result_polygons = list(polygonize(extended_lines))
                        print(f"Polygonize created {len(result_polygons)} polygons")
                        
                        # Filter and validate polygons
                        valid_polygons = []
                        for poly in result_polygons:
                            try:
                                if hasattr(poly, 'area') and poly.area > 0.000001:
                                    # Check if polygon is within our search area
                                    if polygon.contains(poly.centroid) or polygon.intersects(poly):
                                        # Clip to our search area
                                        clipped = polygon.intersection(poly)
                                        if hasattr(clipped, 'area') and clipped.area > 0.000001:
                                            if hasattr(clipped, 'exterior'):
                                                valid_polygons.append(clipped)
                                            elif hasattr(clipped, 'geoms'):
                                                for geom in clipped.geoms:
                                                    if hasattr(geom, 'area') and geom.area > 0.000001 and hasattr(geom, 'exterior'):
                                                        valid_polygons.append(geom)
                            except Exception as e:
                                print(f"Error validating polygon: {e}")
                                continue
                        
                        print(f"Found {len(valid_polygons)} valid polygons")
                        
                        # Create divisions from valid polygons
                        if valid_polygons and len(valid_polygons) >= 2:
                            # Sort by area (largest first) and take up to num_divisions
                            valid_polygons.sort(key=lambda p: p.area, reverse=True)
                            
                            for i, geom in enumerate(valid_polygons[:num_divisions]):
                                if division_counter >= num_divisions:
                                    break
                                    
                                try:
                                    coords = list(geom.exterior.coords)
                                    
                                    division_letter = chr(65 + division_counter)
                                    division_name = f"Division {division_letter}"
                                    division_id = f"DIV-{division_letter}"

                                    priority = self._calculate_division_priority(
                                        geom, incident_location, divisions
                                    )

                                    divisions.append({
                                        "division_name": division_name,
                                        "division_id": division_id,
                                        "coordinates": coords,
                                        "estimated_area_m2": self._calculate_area_m2(geom),
                                        "status": "unassigned",
                                        "priority": priority,
                                        "search_type": "primary",
                                        "estimated_duration": "2 hours",
                                    })

                                    division_counter += 1
                                    
                                except Exception as e:
                                    print(f"Error creating division from polygon: {e}")
                                    continue
                        
                    except Exception as e:
                        print(f"Polygonize failed: {e}")
                
                except Exception as e:
                    print(f"Error in polygon creation: {e}")

            # If road-based approach didn't work well, ensure we have some divisions
            if len(divisions) < max(1, num_divisions // 2):
                print("Road-based approach didn't create enough divisions, falling back to grid")
                return []

            print(f"Successfully created {len(divisions)} road-aware divisions")
            return divisions

        except Exception as e:
            print(f"Road-aware division creation failed: {e}")
            return []

    # ... rest of the file continues as before