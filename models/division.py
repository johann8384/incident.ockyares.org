import hashlib
import os
from typing import Dict, List, Optional, Tuple, Set
import numpy as np
from collections import deque

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
    """Manages search area divisions with walkable road-based expansion"""

    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()
        self._road_cache = {}
        self._building_cache = {}
        
        # Target searchable area per division (default ~5000 sq meters)
        self.TARGET_STRUCTURE_AREA_M2 = int(os.getenv("TARGET_STRUCTURE_AREA_M2", 5000))
        
        # Maximum walking distance for expansion
        self.MAX_WALKING_DISTANCE_DEGREES = 0.008  # ~800m per expansion step
        
        # Buffer distance for buildings near roads
        self.ROAD_BUILDING_BUFFER_DEGREES = 0.001  # ~100m

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

            # Try walkable road expansion divisions first
            try:
                buildings = self._fetch_building_data(polygon)
                roads = self._fetch_road_data(polygon)
                
                if buildings and incident_location:
                    divisions = self._create_walkable_divisions_preview(
                        polygon, incident_location, buildings, roads
                    )
                    if divisions:
                        return divisions
            except Exception as e:
                print(f"Walkable division failed, falling back to grid: {e}")

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

            # Try walkable road expansion divisions first
            try:
                buildings = self._fetch_building_data(search_area)
                roads = self._fetch_road_data(search_area)
                
                if buildings and incident_location:
                    divisions = self._create_walkable_divisions(
                        search_area, incident_location, buildings, roads
                    )
                    if divisions:
                        self._save_divisions(incident_id, divisions)
                        return divisions
            except Exception as e:
                print(f"Walkable division failed, falling back to grid: {e}")

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

    def _create_walkable_divisions_preview(
        self, polygon: Polygon, incident_location: Point,
        buildings: List[Dict], roads: List[LineString]
    ) -> List[Dict]:
        """Create walkable divisions by expanding along roads from incident location"""
        try:
            print(f"Creating walkable divisions from incident location")
            print(f"Buildings: {len(buildings)}, Roads: {len(roads)}")
            print(f"Target area per division: {self.TARGET_STRUCTURE_AREA_M2:,} sq meters")
            
            # Step 1: Map buildings to nearby road segments
            building_road_map = self._map_buildings_to_roads(buildings, roads)
            
            # Step 2: Expand divisions from incident location using simple distance-based expansion
            divisions_data = self._expand_divisions_walkable(
                incident_location, buildings, roads, polygon
            )
            
            if not divisions_data:
                print("No walkable divisions created")
                return []

            # Step 3: Convert to division format
            divisions = []
            for i, division_data in enumerate(divisions_data):
                try:
                    division_letter = chr(65 + i) if i < 26 else f"A{chr(65 + (i-26))}"
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    # Create division polygon
                    division_poly = self._create_walkable_division_polygon(
                        division_data, polygon
                    )
                    
                    if division_poly and hasattr(division_poly, 'exterior'):
                        coords = list(division_poly.exterior.coords)
                        
                        priority = self._calculate_division_priority(
                            division_poly, incident_location, divisions
                        )

                        # Calculate summary statistics
                        total_structures = len(division_data['buildings'])
                        total_searchable_area = sum(b['searchable_area_m2'] for b in division_data['buildings'])
                        building_types = self._summarize_building_types(division_data['buildings'])
                        
                        # Calculate walking distance from incident
                        avg_distance = sum(
                            incident_location.distance(b['centroid']) for b in division_data['buildings']
                        ) / len(division_data['buildings']) if division_data['buildings'] else 0
                        
                        walking_distance_m = avg_distance * 111000  # Rough conversion to meters

                        divisions.append({
                            "division_name": division_name,
                            "division_id": division_id,
                            "coordinates": coords,
                            "estimated_area_m2": self._calculate_area_m2(division_poly),
                            "structure_count": total_structures,
                            "searchable_area_m2": total_searchable_area,
                            "building_types": building_types,
                            "avg_walking_distance_m": int(walking_distance_m),
                            "walkable_from_incident": True,
                            "status": "unassigned",
                            "priority": priority,
                            "search_type": "walkable_structure_search",
                            "estimated_duration": f"{max(1, int(total_searchable_area / 2500))} hours",
                        })
                        
                except Exception as e:
                    print(f"Error creating walkable division: {e}")
                    continue

            print(f"Successfully created {len(divisions)} walkable divisions")
            return divisions

        except Exception as e:
            print(f"Walkable division creation failed: {e}")
            return []

    def _create_walkable_divisions(
        self, search_area: Polygon, incident_location: Point,
        buildings: List[Dict], roads: List[LineString]
    ) -> List[Dict]:
        """Create walkable divisions - for actual generation"""
        try:
            print(f"Creating walkable divisions from incident location")
            
            # Expand divisions walkably
            divisions_data = self._expand_divisions_walkable(
                incident_location, buildings, roads, search_area
            )
            
            if not divisions_data:
                return []

            # Convert to division format
            divisions = []
            for i, division_data in enumerate(divisions_data):
                try:
                    division_letter = chr(65 + i) if i < 26 else f"A{chr(65 + (i-26))}"
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    division_poly = self._create_walkable_division_polygon(
                        division_data, search_area
                    )
                    
                    if division_poly:
                        priority = self._calculate_division_priority(
                            division_poly, incident_location, divisions
                        )

                        total_structures = len(division_data['buildings'])
                        total_searchable_area = sum(b['searchable_area_m2'] for b in division_data['buildings'])

                        divisions.append({
                            "name": division_name,
                            "division_id": division_id,
                            "geometry": division_poly,
                            "area_m2": self._calculate_area_m2(division_poly),
                            "structure_count": total_structures,
                            "searchable_area_m2": total_searchable_area,
                            "status": "unassigned",
                            "priority": priority,
                            "search_type": "walkable_structure_search",
                            "estimated_duration": f"{max(1, int(total_searchable_area / 2500))} hours",
                        })
                        
                except Exception as e:
                    print(f"Error creating walkable division: {e}")
                    continue

            print(f"Successfully created {len(divisions)} walkable divisions")
            return divisions

        except Exception as e:
            print(f"Walkable division creation failed: {e}")
            return []

    def _map_buildings_to_roads(self, buildings: List[Dict], roads: List[LineString]) -> Dict:
        """Map each building to its nearest road segment"""
        try:
            building_road_map = {}
            
            for i, building in enumerate(buildings):
                min_distance = float('inf')
                nearest_road = None
                
                building_point = building['centroid']
                
                for j, road in enumerate(roads):
                    distance = road.distance(building_point)
                    if distance < min_distance and distance <= self.ROAD_BUILDING_BUFFER_DEGREES:
                        min_distance = distance
                        nearest_road = j
                
                if nearest_road is not None:
                    if nearest_road not in building_road_map:
                        building_road_map[nearest_road] = []
                    building_road_map[nearest_road].append(i)
            
            mapped_buildings = sum(len(buildings) for buildings in building_road_map.values())
            print(f"Mapped {mapped_buildings}/{len(buildings)} buildings to roads")
            return building_road_map
            
        except Exception as e:
            print(f"Error mapping buildings to roads: {e}")
            return {}

    def _expand_divisions_walkable(
        self, incident_location: Point, buildings: List[Dict], 
        roads: List[LineString], polygon: Polygon
    ) -> List[Dict]:
        """Expand divisions walkably from incident location using distance-based growth"""
        try:
            divisions = []
            visited_buildings = set()
            
            # Start from incident location
            current_center = incident_location
            division_counter = 0
            
            print(f"Starting walkable expansion from incident location")
            
            while len(visited_buildings) < len(buildings) and division_counter < 25:
                current_division = {
                    'buildings': [],
                    'road_segments': [],
                    'total_area': 0,
                    'center': current_center
                }
                
                print(f"Division {division_counter + 1}: Starting from center")
                
                # Expand in rings until we hit target area
                expansion_radius = 0.002  # Start with ~200m radius
                max_radius = 0.015  # Max ~1.5km radius
                
                while (current_division['total_area'] < self.TARGET_STRUCTURE_AREA_M2 and 
                       expansion_radius <= max_radius):
                    
                    # Find buildings within current radius
                    buildings_in_radius = []
                    for i, building in enumerate(buildings):
                        if i in visited_buildings:
                            continue
                            
                        distance = current_center.distance(building['centroid'])
                        if distance <= expansion_radius:
                            # Check if building is road-accessible (simplified)
                            if self._is_road_accessible_simple(current_center, building['centroid'], roads):
                                buildings_in_radius.append((i, building, distance))
                    
                    # Add buildings from closest to furthest
                    buildings_in_radius.sort(key=lambda x: x[2])
                    
                    added_any = False
                    for building_idx, building, distance in buildings_in_radius:
                        if current_division['total_area'] >= self.TARGET_STRUCTURE_AREA_M2:
                            break
                            
                        current_division['buildings'].append(building)
                        current_division['total_area'] += building['searchable_area_m2']
                        visited_buildings.add(building_idx)
                        added_any = True
                    
                    if not added_any:
                        # Expand radius if no buildings found
                        expansion_radius *= 1.3
                    else:
                        # Found buildings, try slightly larger radius for more
                        expansion_radius *= 1.1
                
                # If we have buildings, save this division
                if current_division['buildings']:
                    divisions.append(current_division)
                    print(f"  Division {division_counter + 1}: {len(current_division['buildings'])} buildings, "
                          f"{current_division['total_area']:,.0f} sq m")
                    
                    # Update center for next division (furthest building from incident)
                    if len(visited_buildings) < len(buildings):
                        max_distance = 0
                        next_center = current_center
                        
                        for i, building in enumerate(buildings):
                            if i not in visited_buildings:
                                distance = incident_location.distance(building['centroid'])
                                if distance > max_distance:
                                    max_distance = distance
                                    next_center = building['centroid']
                        
                        current_center = next_center
                else:
                    # No more buildings found, try to grab any remaining
                    remaining_buildings = []
                    for i, building in enumerate(buildings):
                        if i not in visited_buildings:
                            remaining_buildings.append(building)
                            visited_buildings.add(i)
                    
                    if remaining_buildings:
                        current_division['buildings'] = remaining_buildings
                        current_division['total_area'] = sum(b['searchable_area_m2'] for b in remaining_buildings)
                        divisions.append(current_division)
                        print(f"  Division {division_counter + 1}: {len(remaining_buildings)} remaining buildings")
                    
                    break  # No more buildings
                
                division_counter += 1
            
            print(f"Walkable expansion created {len(divisions)} divisions, "
                  f"covered {len(visited_buildings)}/{len(buildings)} buildings")
            return divisions
            
        except Exception as e:
            print(f"Error in walkable expansion: {e}")
            return []

    def _is_road_accessible_simple(self, start: Point, end: Point, roads: List[LineString]) -> bool:
        """Simple check if two points are road-accessible (within reasonable distance)"""
        try:
            direct_distance = start.distance(end)
            
            # If very close, assume accessible
            if direct_distance <= 0.002:  # ~200m
                return True
            
            # Check if there are roads connecting the general area
            midpoint = Point((start.x + end.x) / 2, (start.y + end.y) / 2)
            search_radius = direct_distance * 0.7  # 70% of direct distance
            
            # Count roads near the path
            roads_near_path = 0
            for road in roads:
                if road.distance(midpoint) <= search_radius:
                    roads_near_path += 1
            
            # If we have roads in the area, assume accessible
            return roads_near_path > 0
            
        except Exception as e:
            print(f"Error checking road accessibility: {e}")
            return True  # Default to accessible

    def _create_walkable_division_polygon(self, division_data: Dict, polygon: Polygon) -> Optional[Polygon]:
        """Create polygon for a walkable division"""
        try:
            if not division_data['buildings']:
                return None
            
            # Create union of building geometries with buffer
            building_geometries = [b['geometry'] for b in division_data['buildings']]
            buildings_union = unary_union(building_geometries)
            
            # Buffer the area to include walking paths
            walking_buffer = self.ROAD_BUILDING_BUFFER_DEGREES * 2  # Larger buffer for walking area
            division_area = buildings_union.buffer(walking_buffer)
            
            # Clip to search area
            clipped = polygon.intersection(division_area)
            
            if hasattr(clipped, 'area') and clipped.area > 0.000001:
                if isinstance(clipped, MultiPolygon):
                    return max(clipped.geoms, key=lambda g: g.area)
                elif hasattr(clipped, 'exterior'):
                    return clipped
            
            return None
            
        except Exception as e:
            print(f"Error creating walkable division polygon: {e}")
            return None

    def _fetch_building_data(self, polygon: Polygon) -> List[Dict]:
        """Fetch building data from Overpass API (reused from previous implementation)"""
        try:
            bounds = polygon.bounds
            cache_key = hashlib.md5(str(bounds).encode()).hexdigest()
            
            if cache_key in self._building_cache:
                return self._building_cache[cache_key]

            overpass_url = "https://overpass-api.de/api/interpreter"
            
            query = f"""
            [out:json][timeout:30];
            (
              way["building"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
              relation["building"]({bounds[1]},{bounds[0]},{bounds[3]},{bounds[2]});
            );
            out geom;
            """

            response = requests.post(overpass_url, data=query, timeout=35)
            
            if response.status_code != 200:
                print(f"Overpass API error for buildings: {response.status_code}")
                return []

            data = response.json()
            buildings = []

            for element in data.get("elements", []):
                try:
                    building_data = self._process_building_element(element, polygon)
                    if building_data:
                        buildings.append(building_data)
                except Exception as e:
                    print(f"Error processing building element: {e}")
                    continue

            self._building_cache[cache_key] = buildings
            total_area = sum(b['area_m2'] for b in buildings)
            print(f"Fetched {len(buildings)} buildings, total area: {total_area:,.0f} sq meters")
            return buildings

        except Exception as e:
            print(f"Failed to fetch building data: {e}")
            return []

    def _process_building_element(self, element: Dict, polygon: Polygon) -> Optional[Dict]:
        """Process a single building element from OSM data (reused)"""
        try:
            building_type = element.get("tags", {}).get("building", "yes")
            
            if element["type"] == "way" and "geometry" in element:
                coords = [(node["lon"], node["lat"]) for node in element["geometry"]]
                if len(coords) >= 3:
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    
                    building_poly = Polygon(coords)
                    
                    if polygon.intersects(building_poly):
                        clipped = polygon.intersection(building_poly)
                        
                        if hasattr(clipped, 'area') and clipped.area > 0.000001:
                            if isinstance(clipped, MultiPolygon):
                                clipped = max(clipped.geoms, key=lambda g: g.area)
                            
                            if hasattr(clipped, 'exterior'):
                                area_m2 = self._calculate_area_m2(clipped)
                                levels = self._estimate_building_levels(element.get("tags", {}), building_type)
                                total_searchable_area = area_m2 * levels
                                
                                return {
                                    "geometry": clipped,
                                    "type": building_type,
                                    "area_m2": area_m2,
                                    "levels": levels,
                                    "searchable_area_m2": total_searchable_area,
                                    "centroid": clipped.centroid,
                                    "tags": element.get("tags", {})
                                }
            
            return None
            
        except Exception as e:
            print(f"Error processing building: {e}")
            return None

    def _estimate_building_levels(self, tags: Dict, building_type: str) -> int:
        """Estimate number of searchable levels in a building (reused)"""
        if "building:levels" in tags:
            try:
                return max(1, int(float(tags["building:levels"])))
            except:
                pass
        
        if "height" in tags:
            try:
                height_m = float(tags["height"])
                return max(1, int(height_m / 3.5))
            except:
                pass
        
        type_defaults = {
            "house": 2, "detached": 2, "residential": 2,
            "apartments": 3, "apartment": 3,
            "commercial": 1, "retail": 1, "office": 3,
            "industrial": 1, "warehouse": 1,
            "garage": 1, "shed": 1,
            "school": 2, "hospital": 4, "hotel": 4,
            "yes": 1
        }
        
        return type_defaults.get(building_type.lower(), 1)

    def _summarize_building_types(self, buildings: List[Dict]) -> str:
        """Create a summary of building types in a division (reused)"""
        type_counts = {}
        for building in buildings:
            building_type = building.get('type', 'unknown')
            type_counts[building_type] = type_counts.get(building_type, 0) + 1
        
        summaries = []
        for btype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            if btype == 'yes':
                btype = 'buildings'
            summaries.append(f"{count} {btype}")
        
        return ", ".join(summaries[:3])

    def save_divisions(self, incident_id: str, divisions: List[Dict]) -> bool:
        """Save divisions to database (reused)"""
        try:
            for division in divisions:
                coordinates = None
                if "coordinates" in division:
                    coordinates = division["coordinates"]
                elif "geom" in division and division["geom"]:
                    import json
                    geom_data = (
                        json.loads(division["geom"])
                        if isinstance(division["geom"], str)
                        else division["geom"]
                    )
                    if "coordinates" in geom_data:
                        coordinates = geom_data["coordinates"][0]

                if coordinates:
                    coords = coordinates.copy()
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])

                    coords_str = ", ".join([f"{coord[0]} {coord[1]}" for coord in coords])
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
        """Get search divisions for an incident (reused)"""
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
        """Fetch road data from Overpass API (reused)"""
        try:
            bounds = polygon.bounds
            cache_key = hashlib.md5(str(bounds).encode()).hexdigest()
            
            if cache_key in self._road_cache:
                return self._road_cache[cache_key]

            overpass_url = "https://overpass-api.de/api/interpreter"
            
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
                            if polygon.intersects(line):
                                roads.append(line)
                        except Exception as e:
                            print(f"Error creating LineString: {e}")
                            continue

            self._road_cache[cache_key] = roads
            print(f"Fetched {len(roads)} roads for area")
            return roads

        except Exception as e:
            print(f"Failed to fetch road data: {e}")
            return []

    def _calculate_division_priority(
        self, division_geom: Polygon, incident_location: Point, existing_divisions: List[Dict]
    ) -> str:
        """Calculate division priority based on distance from incident location (reused)"""
        if not incident_location:
            return "Low"
        
        if division_geom.contains(incident_location):
            return "High"
        
        division_centroid = division_geom.centroid
        distance = division_centroid.distance(incident_location)
        
        bounds = division_geom.bounds
        division_size = max(bounds[2] - bounds[0], bounds[3] - bounds[1])
        
        if distance <= division_size * 1.5:
            return "High"
        elif distance <= division_size * 3:
            return "Medium"
        
        return "Low"

    def _create_grid_divisions_preview(
        self, polygon: Polygon, num_divisions: int, incident_location: Point = None
    ) -> List[Dict]:
        """Create grid-based divisions for preview (fallback, reused)"""
        divisions = []
        bounds = polygon.bounds

        if not polygon.is_valid:
            polygon = polygon.buffer(0)

        cols = int((num_divisions**0.5)) if num_divisions > 1 else 1
        rows = int(num_divisions / cols) + (1 if num_divisions % cols else 0)

        width = (bounds[2] - bounds[0]) / cols
        height = (bounds[3] - bounds[1]) / rows

        division_counter = 0
        for row in range(rows):
            for col in range(cols):
                if division_counter >= num_divisions:
                    break

                x1 = bounds[0] + col * width
                y1 = bounds[1] + row * height
                x2 = x1 + width
                y2 = y1 + height

                cell = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])

                if not cell.is_valid:
                    cell = cell.buffer(0)

                try:
                    if polygon.intersects(cell):
                        clipped = polygon.intersection(cell)

                        if hasattr(clipped, "area") and clipped.area > 0:
                            if hasattr(clipped, "exterior"):
                                coords = list(clipped.exterior.coords)
                            elif hasattr(clipped, "geoms"):
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
        """Create grid-based divisions (fallback, reused)"""
        divisions = []
        bounds = search_area.bounds

        cols = int((num_divisions**0.5))
        rows = int(num_divisions / cols) + (1 if num_divisions % cols else 0)

        width = (bounds[2] - bounds[0]) / cols
        height = (bounds[3] - bounds[1]) / rows

        division_counter = 0
        for row in range(rows):
            for col in range(cols):
                if division_counter >= num_divisions:
                    break

                x1 = bounds[0] + col * width
                y1 = bounds[1] + row * height
                x2 = x1 + width
                y2 = y1 + height

                cell = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)])
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
        """Save divisions to database (reused)"""
        for division in divisions:
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
        """Clear existing divisions for an incident (reused)"""
        query = "DELETE FROM search_divisions WHERE incident_id = %s"
        self.db.execute_query(query, (incident_id,))

    def _calculate_area_m2(self, polygon: Polygon) -> float:
        """Calculate polygon area in square meters (reused)"""
        bounds = polygon.bounds
        lat_center = (bounds[1] + bounds[3]) / 2

        lat_m_per_deg = 111132.92 - 559.82 * (lat_center * 0.0174533) ** 2
        lng_m_per_deg = 111412.84 * (1 - (lat_center * 0.0174533) ** 2) ** 0.5

        area_deg2 = polygon.area
        area_m2 = area_deg2 * lat_m_per_deg * lng_m_per_deg

        return abs(area_m2)
