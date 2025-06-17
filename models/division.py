import hashlib
import os
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
    """Manages search area divisions with structure-centric and road-aware generation"""

    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()
        self._road_cache = {}
        self._building_cache = {}
        
        # Configurable target structure area per division (default ~5000 sq meters)
        # This represents roughly 1-2 hours of detailed search time
        self.TARGET_STRUCTURE_AREA_M2 = int(os.getenv("TARGET_STRUCTURE_AREA_M2", 5000))
        
        # Road segment distance for grouping structures
        road_segment_feet = int(os.getenv("ROAD_SEGMENT_DISTANCE_FEET", 8000))
        self.ROAD_SEGMENT_DISTANCE_DEGREES = (road_segment_feet / 1000) * 0.009

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

            # Try structure-centric divisions first
            try:
                buildings = self._fetch_building_data(polygon)
                roads = self._fetch_road_data(polygon)
                
                if buildings:
                    divisions = self._create_structure_centric_divisions_preview(
                        polygon, incident_location, buildings, roads
                    )
                    if divisions:
                        return divisions
            except Exception as e:
                print(f"Structure-centric division failed, falling back to grid: {e}")

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

            # Try structure-centric divisions first
            try:
                buildings = self._fetch_building_data(search_area)
                roads = self._fetch_road_data(search_area)
                
                if buildings:
                    divisions = self._create_structure_centric_divisions(
                        search_area, incident_location, buildings, roads
                    )
                    if divisions:
                        self._save_divisions(incident_id, divisions)
                        return divisions
            except Exception as e:
                print(f"Structure-centric division failed, falling back to grid: {e}")

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

    def _fetch_building_data(self, polygon: Polygon) -> List[Dict]:
        """Fetch building data from Overpass API within polygon bounds"""
        try:
            # Create cache key from polygon bounds
            bounds = polygon.bounds
            cache_key = hashlib.md5(str(bounds).encode()).hexdigest()
            
            # Check cache first
            if cache_key in self._building_cache:
                return self._building_cache[cache_key]

            # Build Overpass API query for buildings
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

            # Cache the result
            self._building_cache[cache_key] = buildings
            total_area = sum(b['area_m2'] for b in buildings)
            print(f"Fetched {len(buildings)} buildings, total area: {total_area:,.0f} sq meters")
            return buildings

        except Exception as e:
            print(f"Failed to fetch building data: {e}")
            return []

    def _process_building_element(self, element: Dict, polygon: Polygon) -> Optional[Dict]:
        """Process a single building element from OSM data"""
        try:
            building_type = element.get("tags", {}).get("building", "yes")
            
            # Extract geometry
            if element["type"] == "way" and "geometry" in element:
                coords = [(node["lon"], node["lat"]) for node in element["geometry"]]
                if len(coords) >= 3:
                    # Ensure polygon is closed
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    
                    building_poly = Polygon(coords)
                    
                    # Only include buildings that intersect our search area
                    if polygon.intersects(building_poly):
                        # Clip to search area
                        clipped = polygon.intersection(building_poly)
                        
                        if hasattr(clipped, 'area') and clipped.area > 0.000001:
                            # Handle MultiPolygon case
                            if isinstance(clipped, MultiPolygon):
                                # Take the largest polygon
                                clipped = max(clipped.geoms, key=lambda g: g.area)
                            
                            if hasattr(clipped, 'exterior'):
                                area_m2 = self._calculate_area_m2(clipped)
                                
                                # Estimate floors and total searchable area
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
        """Estimate number of searchable levels in a building"""
        # Check for explicit level information
        if "building:levels" in tags:
            try:
                return max(1, int(float(tags["building:levels"])))
            except:
                pass
        
        if "height" in tags:
            try:
                height_m = float(tags["height"])
                # Estimate 3.5m per level
                return max(1, int(height_m / 3.5))
            except:
                pass
        
        # Default estimates by building type
        type_defaults = {
            "house": 2,
            "detached": 2, 
            "residential": 2,
            "apartments": 3,
            "apartment": 3,
            "commercial": 1,
            "retail": 1,
            "office": 3,
            "industrial": 1,
            "warehouse": 1,
            "garage": 1,
            "shed": 1,
            "school": 2,
            "hospital": 4,
            "hotel": 4,
            "yes": 1  # Generic building
        }
        
        return type_defaults.get(building_type.lower(), 1)

    def _create_structure_centric_divisions_preview(
        self, polygon: Polygon, incident_location: Point = None, 
        buildings: List[Dict] = None, roads: List[LineString] = None
    ) -> List[Dict]:
        """Create structure-centric divisions balanced by searchable area"""
        try:
            if not buildings:
                return []

            print(f"Creating structure-centric divisions with {len(buildings)} buildings")
            print(f"Target structure area per division: {self.TARGET_STRUCTURE_AREA_M2:,} sq meters")
            
            # Step 1: Group buildings by proximity to roads (if roads available)
            building_groups = self._group_buildings_by_roads(buildings, roads, polygon)
            
            # Step 2: Balance groups by target searchable area
            balanced_divisions = self._balance_divisions_by_area(building_groups, polygon)
            
            if not balanced_divisions:
                print("No balanced divisions created")
                return []

            # Step 3: Convert to division format
            divisions = []
            for i, division_data in enumerate(balanced_divisions):
                try:
                    division_letter = chr(65 + i) if i < 26 else f"A{chr(65 + (i-26))}"
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    # Create division polygon from building cluster
                    division_poly = self._create_division_polygon(division_data['buildings'], polygon)
                    
                    if division_poly and hasattr(division_poly, 'exterior'):
                        coords = list(division_poly.exterior.coords)
                        
                        priority = self._calculate_division_priority(
                            division_poly, incident_location, divisions
                        )

                        # Calculate summary statistics
                        total_structures = len(division_data['buildings'])
                        total_searchable_area = sum(b['searchable_area_m2'] for b in division_data['buildings'])
                        building_types = self._summarize_building_types(division_data['buildings'])

                        divisions.append({
                            "division_name": division_name,
                            "division_id": division_id,
                            "coordinates": coords,
                            "estimated_area_m2": self._calculate_area_m2(division_poly),
                            "structure_count": total_structures,
                            "searchable_area_m2": total_searchable_area,
                            "building_types": building_types,
                            "status": "unassigned",
                            "priority": priority,
                            "search_type": "structure_search",
                            "estimated_duration": f"{max(1, int(total_searchable_area / 2500))} hours",  # ~2500 sq m per hour
                        })
                        
                except Exception as e:
                    print(f"Error creating division from buildings: {e}")
                    continue

            print(f"Successfully created {len(divisions)} structure-centric divisions")
            return divisions

        except Exception as e:
            print(f"Structure-centric division creation failed: {e}")
            return []

    def _create_structure_centric_divisions(
        self, search_area: Polygon, incident_location: Point = None,
        buildings: List[Dict] = None, roads: List[LineString] = None
    ) -> List[Dict]:
        """Create structure-centric divisions - for actual generation"""
        try:
            if not buildings:
                return []

            print(f"Creating structure-centric divisions with {len(buildings)} buildings")
            
            # Group and balance buildings
            building_groups = self._group_buildings_by_roads(buildings, roads, search_area)
            balanced_divisions = self._balance_divisions_by_area(building_groups, search_area)
            
            if not balanced_divisions:
                return []

            # Convert to division format
            divisions = []
            for i, division_data in enumerate(balanced_divisions):
                try:
                    division_letter = chr(65 + i) if i < 26 else f"A{chr(65 + (i-26))}"
                    division_name = f"Division {division_letter}"
                    division_id = f"DIV-{division_letter}"

                    division_poly = self._create_division_polygon(division_data['buildings'], search_area)
                    
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
                            "search_type": "structure_search",
                            "estimated_duration": f"{max(1, int(total_searchable_area / 2500))} hours",
                        })
                        
                except Exception as e:
                    print(f"Error creating division from buildings: {e}")
                    continue

            print(f"Successfully created {len(divisions)} structure-centric divisions")
            return divisions

        except Exception as e:
            print(f"Structure-centric division creation failed: {e}")
            return []

    def _group_buildings_by_roads(self, buildings: List[Dict], roads: List[LineString], polygon: Polygon) -> List[List[Dict]]:
        """Group buildings by proximity to road segments"""
        try:
            if not roads:
                # No roads available, group by geographic proximity
                return self._group_buildings_geographically(buildings, polygon)
            
            # Segment roads first
            road_segments = self._segment_roads_into_chunks(roads, polygon)
            
            if not road_segments:
                return self._group_buildings_geographically(buildings, polygon)
            
            building_groups = []
            assigned_buildings = set()
            
            # For each road segment, find nearby buildings
            for segment in road_segments:
                nearby_buildings = []
                segment_buffer = segment.buffer(0.005)  # ~500m buffer around road
                
                for i, building in enumerate(buildings):
                    if i in assigned_buildings:
                        continue
                        
                    if segment_buffer.intersects(building['geometry']):
                        nearby_buildings.append(building)
                        assigned_buildings.add(i)
                
                if nearby_buildings:
                    building_groups.append(nearby_buildings)
            
            # Assign any remaining unassigned buildings to nearest group
            for i, building in enumerate(buildings):
                if i not in assigned_buildings:
                    if building_groups:
                        # Find closest group by centroid distance
                        min_distance = float('inf')
                        closest_group_idx = 0
                        
                        for j, group in enumerate(building_groups):
                            group_centroid = self._get_group_centroid(group)
                            distance = building['centroid'].distance(group_centroid)
                            if distance < min_distance:
                                min_distance = distance
                                closest_group_idx = j
                        
                        building_groups[closest_group_idx].append(building)
                    else:
                        # No groups yet, create first group
                        building_groups.append([building])
            
            print(f"Grouped {len(buildings)} buildings into {len(building_groups)} road-based groups")
            return building_groups
            
        except Exception as e:
            print(f"Error grouping buildings by roads: {e}")
            return self._group_buildings_geographically(buildings, polygon)

    def _group_buildings_geographically(self, buildings: List[Dict], polygon: Polygon) -> List[List[Dict]]:
        """Fallback: group buildings by geographic proximity"""
        try:
            # Simple clustering by distance
            groups = []
            assigned = set()
            cluster_distance = 0.002  # ~200m
            
            for i, building in enumerate(buildings):
                if i in assigned:
                    continue
                    
                # Start new group
                group = [building]
                assigned.add(i)
                
                # Find nearby buildings
                for j, other_building in enumerate(buildings):
                    if j in assigned:
                        continue
                        
                    distance = building['centroid'].distance(other_building['centroid'])
                    if distance <= cluster_distance:
                        group.append(other_building)
                        assigned.add(j)
                
                groups.append(group)
            
            print(f"Grouped {len(buildings)} buildings into {len(groups)} geographic clusters")
            return groups
            
        except Exception as e:
            print(f"Error in geographic grouping: {e}")
            return [[building] for building in buildings]  # Fallback: each building its own group

    def _balance_divisions_by_area(self, building_groups: List[List[Dict]], polygon: Polygon) -> List[Dict]:
        """Balance building groups to achieve target searchable area per division"""
        try:
            if not building_groups:
                return []
            
            # Calculate total searchable area
            total_searchable_area = sum(
                sum(building['searchable_area_m2'] for building in group) 
                for group in building_groups
            )
            
            # Estimate number of divisions needed
            target_divisions = max(1, int(total_searchable_area / self.TARGET_STRUCTURE_AREA_M2))
            
            print(f"Total searchable area: {total_searchable_area:,.0f} sq m")
            print(f"Target area per division: {self.TARGET_STRUCTURE_AREA_M2:,} sq m") 
            print(f"Target divisions: {target_divisions}")
            
            # Sort groups by size (largest first)
            sorted_groups = sorted(building_groups, 
                                 key=lambda g: sum(b['searchable_area_m2'] for b in g), 
                                 reverse=True)
            
            balanced_divisions = []
            
            # Create divisions by filling up to target area
            current_division = {'buildings': [], 'area': 0}
            
            for group in sorted_groups:
                group_area = sum(building['searchable_area_m2'] for building in group)
                
                # If adding this group would exceed target significantly, start new division
                if (current_division['area'] > 0 and 
                    current_division['area'] + group_area > self.TARGET_STRUCTURE_AREA_M2 * 1.5):
                    
                    # Finish current division
                    if current_division['buildings']:
                        balanced_divisions.append(current_division)
                    
                    # Start new division
                    current_division = {'buildings': group.copy(), 'area': group_area}
                else:
                    # Add group to current division
                    current_division['buildings'].extend(group)
                    current_division['area'] += group_area
            
            # Add final division
            if current_division['buildings']:
                balanced_divisions.append(current_division)
            
            # If we have too few divisions, split the largest ones
            while len(balanced_divisions) < target_divisions and len(balanced_divisions) > 0:
                # Find largest division
                largest_idx = max(range(len(balanced_divisions)), 
                                key=lambda i: balanced_divisions[i]['area'])
                
                largest_div = balanced_divisions[largest_idx]
                
                # Only split if it has more than one building
                if len(largest_div['buildings']) > 1:
                    # Split roughly in half
                    mid = len(largest_div['buildings']) // 2
                    buildings1 = largest_div['buildings'][:mid]
                    buildings2 = largest_div['buildings'][mid:]
                    
                    area1 = sum(b['searchable_area_m2'] for b in buildings1)
                    area2 = sum(b['searchable_area_m2'] for b in buildings2)
                    
                    # Replace largest division with two smaller ones
                    balanced_divisions[largest_idx] = {'buildings': buildings1, 'area': area1}
                    balanced_divisions.append({'buildings': buildings2, 'area': area2})
                else:
                    break  # Can't split further
            
            print(f"Created {len(balanced_divisions)} balanced divisions")
            for i, div in enumerate(balanced_divisions):
                print(f"  Division {chr(65+i)}: {len(div['buildings'])} buildings, {div['area']:,.0f} sq m")
            
            return balanced_divisions
            
        except Exception as e:
            print(f"Error balancing divisions: {e}")
            return []

    def _create_division_polygon(self, buildings: List[Dict], search_area: Polygon) -> Optional[Polygon]:
        """Create a polygon that encompasses all buildings in a division"""
        try:
            if not buildings:
                return None
            
            # Create buffer around all building geometries
            building_geometries = [b['geometry'] for b in buildings]
            buildings_union = unary_union(building_geometries)
            
            # Buffer to create search area around buildings
            buffer_distance = 0.001  # ~100m buffer
            division_area = buildings_union.buffer(buffer_distance)
            
            # Clip to search area
            clipped = search_area.intersection(division_area)
            
            if hasattr(clipped, 'area') and clipped.area > 0.000001:
                if isinstance(clipped, MultiPolygon):
                    # Take the largest polygon
                    return max(clipped.geoms, key=lambda g: g.area)
                elif hasattr(clipped, 'exterior'):
                    return clipped
            
            return None
            
        except Exception as e:
            print(f"Error creating division polygon: {e}")
            return None

    def _get_group_centroid(self, buildings: List[Dict]) -> Point:
        """Get centroid of a group of buildings"""
        if not buildings:
            return Point(0, 0)
        
        x_coords = [b['centroid'].x for b in buildings]
        y_coords = [b['centroid'].y for b in buildings]
        
        avg_x = sum(x_coords) / len(x_coords)
        avg_y = sum(y_coords) / len(y_coords)
        
        return Point(avg_x, avg_y)

    def _summarize_building_types(self, buildings: List[Dict]) -> str:
        """Create a summary of building types in a division"""
        type_counts = {}
        for building in buildings:
            building_type = building.get('type', 'unknown')
            type_counts[building_type] = type_counts.get(building_type, 0) + 1
        
        # Create readable summary
        summaries = []
        for btype, count in sorted(type_counts.items(), key=lambda x: x[1], reverse=True):
            if btype == 'yes':
                btype = 'buildings'
            summaries.append(f"{count} {btype}")
        
        return ", ".join(summaries[:3])  # Top 3 types

    def _segment_roads_into_chunks(self, roads: List[LineString], polygon: Polygon) -> List[LineString]:
        """Segment roads into chunks (reused from previous implementation)"""
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
            
            return road_segments
            
        except Exception as e:
            print(f"Error segmenting roads: {e}")
            return []

    def _segment_line_into_chunks(self, line: LineString) -> List[LineString]:
        """Segment a single road line into chunks (reused from previous implementation)"""
        try:
            segments = []
            total_length = line.length
            
            if total_length <= self.ROAD_SEGMENT_DISTANCE_DEGREES:
                return [line]
            
            num_segments = max(1, int(total_length / self.ROAD_SEGMENT_DISTANCE_DEGREES))
            segment_length = total_length / num_segments
            
            for i in range(num_segments):
                start_distance = i * segment_length
                end_distance = min((i + 1) * segment_length, total_length)
                
                try:
                    segment_coords = []
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
            return [line]

    def save_divisions(self, incident_id: str, divisions: List[Dict]) -> bool:
        """Save divisions to database"""
        try:
            for division in divisions:
                # Extract coordinates from division data
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
        """Fetch road data from Overpass API (reused from previous implementation)"""
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
        """Calculate division priority based on distance from incident location"""
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
        """Create grid-based divisions for preview (fallback)"""
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
        """Create grid-based divisions (fallback)"""
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
        """Save divisions to database"""
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
        """Clear existing divisions for an incident"""
        query = "DELETE FROM search_divisions WHERE incident_id = %s"
        self.db.execute_query(query, (incident_id,))

    def _calculate_area_m2(self, polygon: Polygon) -> float:
        """Calculate polygon area in square meters (approximate)"""
        bounds = polygon.bounds
        lat_center = (bounds[1] + bounds[3]) / 2

        lat_m_per_deg = 111132.92 - 559.82 * (lat_center * 0.0174533) ** 2
        lng_m_per_deg = 111412.84 * (1 - (lat_center * 0.0174533) ** 2) ** 0.5

        area_deg2 = polygon.area
        area_m2 = area_deg2 * lat_m_per_deg * lng_m_per_deg

        return abs(area_m2)
