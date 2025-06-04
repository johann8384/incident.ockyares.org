import requests
import os
from typing import Dict, List, Optional
from .database import DatabaseManager


class Hospital:
    """Hospital model for storing and managing hospital data"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()
        self.arcgis_url = "https://services1.arcgis.com/Hp6G80Pky0om7QvQ/arcgis/rest/services/Hospitals_gdb/FeatureServer/0/query"
        
    def fetch_hospitals_from_arcgis(self, latitude: float, longitude: float, 
                                   radius_km: float = 100) -> List[Dict]:
        """Fetch hospital data from ArcGIS service"""
        try:
            params = {
                'where': '1=1',
                'outFields': '*',
                'f': 'json',
                'returnGeometry': 'true',
                'geometryType': 'esriGeometryPoint',
                'inSR': '4326',
                'spatialRel': 'esriSpatialRelIntersects',
                'geometry': f'{longitude},{latitude}',
                'distance': radius_km * 1000,  # Convert km to meters
                'units': 'esriSRUnit_Meter'
            }
            
            headers = {
                'User-Agent': 'EmergencyIncidentApp/1.0'
            }
            
            response = requests.get(self.arcgis_url, params=params, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('features'):
                    hospitals = []
                    for feature in data['features']:
                        # Calculate distance
                        hospital_lat = feature['geometry']['y']
                        hospital_lng = feature['geometry']['x']
                        distance = self._calculate_distance(latitude, longitude, hospital_lat, hospital_lng)
                        
                        # Add distance to the feature
                        feature['distance'] = distance
                        feature['attributes']['distance'] = distance
                        hospitals.append(feature)
                    
                    # Sort by distance
                    hospitals.sort(key=lambda h: h['distance'])
                    return hospitals
                
            return []
            
        except Exception as e:
            print(f"Failed to fetch hospitals from ArcGIS: {e}")
            return []
    
    def _calculate_distance(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """Calculate distance between two points using Haversine formula"""
        import math
        
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        
        a = (math.sin(delta_lat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * 
             math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
    
    def find_key_hospitals(self, hospitals: List[Dict], latitude: float, longitude: float) -> Dict:
        """Find the closest hospital, Level I trauma center, and Level I pediatric center"""
        if not hospitals:
            return {}
        
        key_hospitals = {}
        
        # Closest hospital overall
        key_hospitals['closest'] = hospitals[0] if hospitals else None
        
        # Closest Level I trauma center
        level1_hospitals = [h for h in hospitals if self._is_level1_trauma(h)]
        key_hospitals['level1'] = level1_hospitals[0] if level1_hospitals else None
        
        # Closest Level 1 Pediatric trauma center
        pediatric_hospitals = [h for h in hospitals if self._is_level1_pediatric(h)]
        key_hospitals['pediatric'] = pediatric_hospitals[0] if pediatric_hospitals else None
        
        return key_hospitals
    
    def _is_level1_trauma(self, hospital: Dict) -> bool:
        """Check if hospital is a Level I trauma center"""
        trauma_level = hospital.get('attributes', {}).get('TRAUMA', '')
        if trauma_level:
            trauma_upper = trauma_level.upper()
            return ('LEVEL I' in trauma_upper or 'LEVEL 1' in trauma_upper) and 'PEDIATRIC' not in trauma_upper
        return False
    
    def _is_level1_pediatric(self, hospital: Dict) -> bool:
        """Check if hospital is a Level I pediatric trauma center"""
        trauma_level = hospital.get('attributes', {}).get('TRAUMA', '')
        if trauma_level:
            trauma_upper = trauma_level.upper()
            return (('LEVEL I' in trauma_upper or 'LEVEL 1' in trauma_upper) and 
                   'PEDIATRIC' in trauma_upper)
        return False
    
    def cache_hospitals(self, hospitals: List[Dict]) -> bool:
        """Cache hospital data in local database"""
        try:
            for hospital_data in hospitals:
                self.save_hospital(hospital_data)
            return True
        except Exception as e:
            print(f"Failed to cache hospitals: {e}")
            return False
    
    def get_cached_hospitals(self, latitude: float, longitude: float, 
                           radius_km: float = 100) -> List[Dict]:
        """Get cached hospitals within radius"""
        try:
            query = """
            SELECT 
                id, name, trauma_level, address, city, state, telephone,
                latitude, longitude, source_id,
                ST_Distance(
                    hospital_location,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                ) / 1000 as distance_km
            FROM hospitals
            WHERE ST_DWithin(
                hospital_location,
                ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                %s * 1000
            )
            ORDER BY distance_km
            """
            
            params = (longitude, latitude, longitude, latitude, radius_km)
            result = self.db.execute_query(query, params, fetch=True)
            
            if result:
                # Convert to format similar to ArcGIS response
                hospitals = []
                for row in result:
                    hospital = {
                        'attributes': {
                            'OBJECTID': row['source_id'],
                            'NAME': row['name'],
                            'TRAUMA': row['trauma_level'],
                            'ADDRESS': row['address'],
                            'CITY': row['city'],
                            'STATE': row['state'],
                            'TELEPHONE': row['telephone'],
                            'distance': row['distance_km']
                        },
                        'geometry': {
                            'x': float(row['longitude']),
                            'y': float(row['latitude'])
                        },
                        'distance': row['distance_km']
                    }
                    hospitals.append(hospital)
                
                return hospitals
            
            return []
            
        except Exception as e:
            print(f"Failed to get cached hospitals: {e}")
            return []
    
    def get_hospitals_for_location(self, latitude: float, longitude: float, 
                                 use_cache: bool = True, cache_duration_hours: int = 24) -> Dict:
        """Get hospital data for a location, using cache if available and recent"""
        try:
            hospitals = []
            
            # Try to get from cache first if enabled
            if use_cache:
                hospitals = self.get_cached_hospitals(latitude, longitude)
                
                # Check if we have recent data (simple check - could be improved)
                if hospitals and len(hospitals) > 0:
                    print(f"Using cached hospital data: {len(hospitals)} hospitals found")
                
            # If no cached data or cache disabled, fetch from ArcGIS
            if not hospitals:
                print("Fetching fresh hospital data from ArcGIS...")
                hospitals = self.fetch_hospitals_from_arcgis(latitude, longitude)
                
                # Cache the fresh data
                if hospitals and use_cache:
                    self.cache_hospitals(hospitals)
                    print(f"Cached {len(hospitals)} hospitals")
            
            # Find key hospitals
            key_hospitals = self.find_key_hospitals(hospitals, latitude, longitude)
            
            return {
                'success': True,
                'hospitals': key_hospitals,
                'total_found': len(hospitals),
                'source': 'cache' if use_cache and hospitals else 'arcgis'
            }
            
        except Exception as e:
            print(f"Failed to get hospitals for location: {e}")
            return {
                'success': False,
                'error': str(e),
                'hospitals': {},
                'total_found': 0
            }
        
    def save_hospital(self, hospital_data: Dict) -> int:
        """Save hospital data to database"""
        try:
            # Extract hospital attributes
            attributes = hospital_data.get('attributes', {})
            geometry = hospital_data.get('geometry', {})
            
            query = """
            INSERT INTO hospitals (
                name, trauma_level, address, city, state, 
                telephone, latitude, longitude, 
                hospital_location, distance_km, source_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, 
                ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s
            )
            ON CONFLICT (source_id) DO UPDATE SET
                name = EXCLUDED.name,
                trauma_level = EXCLUDED.trauma_level,
                address = EXCLUDED.address,
                city = EXCLUDED.city,
                state = EXCLUDED.state,
                telephone = EXCLUDED.telephone,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                hospital_location = EXCLUDED.hospital_location,
                distance_km = EXCLUDED.distance_km,
                updated_at = NOW()
            RETURNING id
            """
            
            params = (
                attributes.get('NAME', ''),
                attributes.get('TRAUMA', ''),
                attributes.get('ADDRESS', ''),
                attributes.get('CITY', ''),
                attributes.get('STATE', ''),
                attributes.get('TELEPHONE', ''),
                geometry.get('y', 0.0),  # latitude
                geometry.get('x', 0.0),  # longitude
                geometry.get('x', 0.0),  # longitude for PostGIS point
                geometry.get('y', 0.0),  # latitude for PostGIS point
                hospital_data.get('distance', 0.0),
                attributes.get('OBJECTID') or attributes.get('FID', 0)
            )
            
            result = self.db.execute_query(query, params, fetch=True)
            return result[0]['id'] if result else None
            
        except Exception as e:
            print(f"Failed to save hospital: {e}")
            return None
    
    def save_incident_hospitals(self, incident_id: str, hospital_data: Dict) -> bool:
        """Save hospital data associated with an incident"""
        try:
            # Save each hospital type
            hospital_ids = {}
            
            if hospital_data.get('closest'):
                hospital_id = self.save_hospital(hospital_data['closest'])
                if hospital_id:
                    hospital_ids['closest'] = hospital_id
            
            if hospital_data.get('level1'):
                hospital_id = self.save_hospital(hospital_data['level1'])
                if hospital_id:
                    hospital_ids['level1'] = hospital_id
            
            if hospital_data.get('pediatric'):
                hospital_id = self.save_hospital(hospital_data['pediatric'])
                if hospital_id:
                    hospital_ids['pediatric'] = hospital_id
            
            # Link hospitals to incident
            query = """
            INSERT INTO incident_hospitals (
                incident_id, closest_hospital_id, level1_hospital_id, pediatric_hospital_id
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (incident_id) DO UPDATE SET
                closest_hospital_id = EXCLUDED.closest_hospital_id,
                level1_hospital_id = EXCLUDED.level1_hospital_id,
                pediatric_hospital_id = EXCLUDED.pediatric_hospital_id,
                updated_at = NOW()
            """
            
            params = (
                incident_id,
                hospital_ids.get('closest'),
                hospital_ids.get('level1'),
                hospital_ids.get('pediatric')
            )
            
            self.db.execute_query(query, params)
            return True
            
        except Exception as e:
            print(f"Failed to save incident hospitals: {e}")
            return False
    
    def get_incident_hospitals(self, incident_id: str) -> Dict:
        """Get hospital data for an incident"""
        try:
            query = """
            SELECT 
                h_closest.name as closest_name,
                h_closest.trauma_level as closest_trauma,
                h_closest.address as closest_address,
                h_closest.city as closest_city,
                h_closest.telephone as closest_phone,
                h_closest.distance_km as closest_distance,
                
                h_level1.name as level1_name,
                h_level1.trauma_level as level1_trauma,
                h_level1.address as level1_address,
                h_level1.city as level1_city,
                h_level1.telephone as level1_phone,
                h_level1.distance_km as level1_distance,
                
                h_pediatric.name as pediatric_name,
                h_pediatric.trauma_level as pediatric_trauma,
                h_pediatric.address as pediatric_address,
                h_pediatric.city as pediatric_city,
                h_pediatric.telephone as pediatric_phone,
                h_pediatric.distance_km as pediatric_distance
                
            FROM incident_hospitals ih
            LEFT JOIN hospitals h_closest ON ih.closest_hospital_id = h_closest.id
            LEFT JOIN hospitals h_level1 ON ih.level1_hospital_id = h_level1.id
            LEFT JOIN hospitals h_pediatric ON ih.pediatric_hospital_id = h_pediatric.id
            WHERE ih.incident_id = %s
            """
            
            result = self.db.execute_query(query, (incident_id,), fetch=True)
            
            if result:
                row = result[0]
                return {
                    'closest': {
                        'name': row['closest_name'],
                        'trauma_level': row['closest_trauma'],
                        'address': row['closest_address'],
                        'city': row['closest_city'],
                        'phone': row['closest_phone'],
                        'distance': row['closest_distance']
                    } if row['closest_name'] else None,
                    'level1': {
                        'name': row['level1_name'],
                        'trauma_level': row['level1_trauma'],
                        'address': row['level1_address'],
                        'city': row['level1_city'],
                        'phone': row['level1_phone'],
                        'distance': row['level1_distance']
                    } if row['level1_name'] else None,
                    'pediatric': {
                        'name': row['pediatric_name'],
                        'trauma_level': row['pediatric_trauma'],
                        'address': row['pediatric_address'],
                        'city': row['pediatric_city'],
                        'phone': row['pediatric_phone'],
                        'distance': row['pediatric_distance']
                    } if row['pediatric_name'] else None
                }
            
            return {}
            
        except Exception as e:
            print(f"Failed to get incident hospitals: {e}")
            return {}
