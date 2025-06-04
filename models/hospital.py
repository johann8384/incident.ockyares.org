from typing import Dict, List, Optional
from .database import DatabaseManager


class Hospital:
    """Hospital model for storing and managing hospital data"""
    
    def __init__(self, db_manager: DatabaseManager = None):
        self.db = db_manager or DatabaseManager()
        
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
    
    def search_hospitals_by_location(self, latitude: float, longitude: float, 
                                   radius_km: float = 50) -> List[Dict]:
        """Search for hospitals within radius of a location"""
        try:
            query = """
            SELECT 
                id, name, trauma_level, address, city, state, telephone,
                latitude, longitude,
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
            
            return [dict(row) for row in result] if result else []
            
        except Exception as e:
            print(f"Failed to search hospitals: {e}")
            return []
