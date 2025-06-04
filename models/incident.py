import uuid
import requests
import os
from datetime import datetime
from typing import List, Tuple, Optional, Dict
from shapely.geometry import Point, Polygon
from .database import DatabaseManager

class Incident:
    """Incident management class"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()
        self.incident_id = None
        self.name = None
        self.incident_type = None
        self.description = None
        self.incident_location = None
        self.address = None
        self.search_area = None
        self.search_divisions = []
        self.search_area_size_m2 = int(os.getenv('SEARCH_AREA_SIZE_M2', 40000))
        self.team_size = int(os.getenv('TEAM_SIZE', 4))
        
    def create_incident(self, name: str, incident_type: str, description: str = "") -> str:
        """Create a new incident"""
        self.incident_id = f"INC-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        self.name = name
        self.incident_type = incident_type
        self.description = description
        
        # Insert into database
        query = """
        INSERT INTO incidents (incident_id, name, incident_type, description)
        VALUES (%s, %s, %s, %s)
        RETURNING id
        """
        
        result = self.db.execute_query(
            query, 
            (self.incident_id, self.name, self.incident_type, self.description),
            fetch=True
        )
        
        return self.incident_id
    
    def set_location(self, latitude: float, longitude: float) -> bool:
        """Set incident location and reverse geocode to address"""
        try:
            self.incident_location = Point(longitude, latitude)
            
            # Reverse geocode
            self.address = self._reverse_geocode(latitude, longitude)
            
            # Update database
            query = """
            UPDATE incidents 
            SET incident_location = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                address = %s
            WHERE incident_id = %s
            """
            
            self.db.execute_query(
                query,
                (longitude, latitude, self.address, self.incident_id)
            )
            
            return True
            
        except Exception as e:
            print(f"Failed to set location: {e}")
            return False
    
    def set_search_area(self, coordinates: List[Tuple[float, float]]) -> bool:
        """Set search area polygon"""
        try:
            # Create polygon from coordinates
            self.search_area = Polygon(coordinates)
            
            # Convert to WKT for PostGIS
            coords_str = ', '.join([f"{lng} {lat}" for lat, lng in coordinates])
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
    
    def generate_divisions(self) -> List[Dict]:
        """Generate search divisions based on search area and team capacity"""
        if not self.search_area:
            raise ValueError("Search area must be set before generating divisions")
        
        try:
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
    
    def _reverse_geocode(self, latitude: float, longitude: float) -> str:
        """Reverse geocode coordinates to address using Nominatim"""
        try:
            nominatim_url = os.getenv('NOMINATIM_URL', 'https://nominatim.openstreetmap.org')
            url = f"{nominatim_url}/reverse"
            
            params = {
                'lat': latitude,
                'lon': longitude,
                'format': 'json',
                'addressdetails': 1
            }
            
            headers = {
                'User-Agent': 'EmergencyIncidentApp/1.0'
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('display_name', f"{latitude}, {longitude}")
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
    
    def _create_grid_divisions(self, num_divisions: int) -> List[Dict]:
        """Create grid-based divisions"""
        divisions = []
        bounds = self.search_area.bounds
        
        # Calculate grid dimensions
        cols = int((num_divisions ** 0.5))
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
                
                if hasattr(clipped, 'area') and clipped.area > 0:
                    division_name = f"Division {chr(65 + division_counter)}"
                    
                    divisions.append({
                        'name': division_name,
                        'geometry': clipped,
                        'area_m2': self._calculate_area_m2(clipped),
                        'status': 'unassigned'
                    })
                    
                    division_counter += 1
        
        return divisions
    
    def _save_divisions(self, divisions: List[Dict]):
        """Save divisions to database"""
        for division in divisions:
            # Convert geometry to WKT
            if hasattr(division['geometry'], 'exterior'):
                coords = list(division['geometry'].exterior.coords)
                coords_str = ', '.join([f"{x} {y}" for x, y in coords])
                polygon_wkt = f"POLYGON(({coords_str}))"
                
                query = """
                INSERT INTO search_divisions 
                (incident_id, division_name, area_geometry, estimated_area_m2, status)
                VALUES (%s, %s, ST_GeomFromText(%s, 4326), %s, %s)
                """
                
                self.db.execute_query(
                    query,
                    (self.incident_id, division['name'], polygon_wkt, 
                     division['area_m2'], division['status'])
                )