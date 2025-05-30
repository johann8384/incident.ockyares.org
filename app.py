from flask import Flask, render_template, request, jsonify, send_file
import psycopg2
import psycopg2.extras
import json
import qrcode
from datetime import datetime
import os
import uuid
from shapely.geometry import Polygon, Point
from shapely import wkt
import geopandas as gpd
from io import BytesIO
import base64
import logging
from logging.handlers import RotatingFileHandler
import requests
import time

app = Flask(__name__)

# Configure logging
if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/incident_app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Incident Management System startup')

# Database configuration from environment variables
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgis'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'emergency_ops'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'emergency_password')
}

def reverse_geocode(lat, lng):
    """
    Reverse geocode coordinates to get an approximate address
    Uses Nominatim (OpenStreetMap) as primary service with fallbacks
    """
    try:
        # Primary: Nominatim (OpenStreetMap) - Free, no API key required
        nominatim_url = f"https://nominatim.openstreetmap.org/reverse"
        params = {
            'lat': lat,
            'lon': lng,
            'format': 'json',
            'zoom': 18,  # Address level detail
            'addressdetails': 1,
            'extratags': 1
        }
        
        headers = {
            'User-Agent': 'Emergency-Incident-Management-System/1.0 (emergency@ockyeoc.org)'
        }
        
        response = requests.get(nominatim_url, params=params, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            
            if 'address' in data:
                address_parts = data['address']
                
                # Build formatted address
                address_components = []
                
                # Street number and name
                if 'house_number' in address_parts and 'road' in address_parts:
                    address_components.append(f"{address_parts['house_number']} {address_parts['road']}")
                elif 'road' in address_parts:
                    address_components.append(address_parts['road'])
                elif 'footway' in address_parts:
                    address_components.append(address_parts['footway'])
                elif 'path' in address_parts:
                    address_components.append(address_parts['path'])
                
                # City/Town
                city = (address_parts.get('city') or 
                       address_parts.get('town') or 
                       address_parts.get('village') or 
                       address_parts.get('hamlet'))
                if city:
                    address_components.append(city)
                
                # County/State
                county = address_parts.get('county')
                state = address_parts.get('state')
                if county:
                    address_components.append(county)
                if state:
                    address_components.append(state)
                
                # Postal code
                postcode = address_parts.get('postcode')
                if postcode:
                    address_components.append(postcode)
                
                formatted_address = ', '.join(address_components)
                
                # If we have a good address, return it
                if len(address_components) >= 2:
                    app.logger.info(f"Geocoded {lat}, {lng} to: {formatted_address}")
                    return {
                        'success': True,
                        'address': formatted_address,
                        'source': 'Nominatim',
                        'components': address_parts,
                        'display_name': data.get('display_name', formatted_address)
                    }
            
        app.logger.warning(f"Nominatim returned limited data for {lat}, {lng}")
        
    except requests.RequestException as e:
        app.logger.error(f"Nominatim geocoding failed for {lat}, {lng}: {e}")
    except Exception as e:
        app.logger.error(f"Unexpected error during geocoding {lat}, {lng}: {e}")
    
    # Fallback: Try a simpler coordinate-based description
    try:
        # Simple coordinate-based location description
        return {
            'success': True,
            'address': f"Coordinates: {lat:.6f}, {lng:.6f}",
            'source': 'Coordinates',
            'components': {},
            'display_name': f"Location at {lat:.6f}, {lng:.6f}"
        }
    except Exception as e:
        app.logger.error(f"Coordinate fallback failed: {e}")
        return {
            'success': False,
            'error': 'Geocoding failed',
            'address': None
        }

class IncidentManager:
    def __init__(self):
        self.conn = None
        
    def connect_db(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            return self.conn
        except Exception as e:
            app.logger.error(f"Database connection failed: {e}")
            raise
    
    def close_db(self):
        if self.conn:
            self.conn.close()
    
    def test_connection(self):
        """Test database connection for health checks"""
        try:
            conn = self.connect_db()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            self.close_db()
            return result is not None
        except Exception as e:
            app.logger.error(f"Database health check failed: {e}")
            return False

    def get_active_incidents(self):
        """Get list of active incidents for dropdown"""
        conn = self.connect_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            cursor.execute("""
                SELECT incident_id, incident_name, incident_type, start_time, stage,
                       ST_X(center_point) as longitude, ST_Y(center_point) as latitude,
                       address
                FROM incidents 
                WHERE stage != 'Closed'
                ORDER BY start_time DESC
            """)
            
            incidents = []
            for incident in cursor.fetchall():
                incident_dict = dict(incident)
                if incident_dict['start_time']:
                    incident_dict['start_time'] = incident_dict['start_time'].isoformat()
                incidents.append(incident_dict)
            
            app.logger.info(f"Retrieved {len(incidents)} active incidents")
            return incidents
            
        except Exception as e:
            app.logger.error(f"Failed to get active incidents: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()

    def update_incident_stage(self, incident_id, new_stage):
        """Update incident stage"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            # Validate stage
            valid_stages = ['New', 'Response', 'Recovery', 'Closed']
            if new_stage not in valid_stages:
                raise ValueError(f"Invalid stage. Must be one of: {', '.join(valid_stages)}")
            
            cursor.execute("""
                UPDATE incidents 
                SET stage = %s, updated_at = NOW()
                WHERE incident_id = %s
                RETURNING incident_id
            """, (new_stage, incident_id))
            
            result = cursor.fetchone()
            if not result:
                raise ValueError("Incident not found")
            
            conn.commit()
            app.logger.info(f"Updated incident {incident_id} stage to {new_stage}")
            return True
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Failed to update incident stage: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()

    def submit_unit_checkin(self, checkin_data):
        """Submit unit check-in data and create/update unit record"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            # First, insert or update the unit record
            cursor.execute("""
                INSERT INTO units (
                    unit_id, incident_id, officer_name, personnel_count, equipment_status, unit_status
                ) VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (unit_id, incident_id) DO UPDATE SET
                    officer_name = EXCLUDED.officer_name,
                    personnel_count = EXCLUDED.personnel_count,
                    equipment_status = EXCLUDED.equipment_status,
                    updated_at = NOW()
                RETURNING id
            """, (
                checkin_data['unit_id'],
                checkin_data['incident_id'],
                checkin_data['officer_name'],
                int(checkin_data['personnel_count']),
                checkin_data['equipment_status'],
                'staging'  # Default status when checking in
            ))
            
            unit_record_id = cursor.fetchone()[0]
            
            # Then insert the check-in record
            cursor.execute("""
                INSERT INTO unit_checkins (
                    incident_id, unit_id, officer_name, personnel_count,
                    equipment_status, location_point, photo_path, checkin_time
                ) VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s)
                RETURNING id
            """, (
                checkin_data['incident_id'],
                checkin_data['unit_id'],
                checkin_data['officer_name'],
                int(checkin_data['personnel_count']),
                checkin_data['equipment_status'],
                float(checkin_data['longitude']) if checkin_data.get('longitude') else None,
                float(checkin_data['latitude']) if checkin_data.get('latitude') else None,
                checkin_data.get('photo_path'),
                datetime.now()
            ))
            
            checkin_id = cursor.fetchone()[0]
            conn.commit()
            
            app.logger.info(f"Unit {checkin_data['unit_id']} checked in for incident {checkin_data['incident_id']}")
            return checkin_id
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Failed to submit unit check-in: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()

    def get_incident_units(self, incident_id):
        """Get all units for an incident with their current status"""
        conn = self.connect_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            cursor.execute("""
                SELECT u.unit_id, u.officer_name, u.personnel_count, u.equipment_status,
                       u.unit_status, u.assigned_division, u.created_at, u.updated_at,
                       uc.checkin_time, uc.photo_path,
                       ST_X(uc.location_point) as longitude, ST_Y(uc.location_point) as latitude
                FROM units u
                LEFT JOIN LATERAL (
                    SELECT checkin_time, photo_path, location_point
                    FROM unit_checkins 
                    WHERE unit_checkins.unit_id = u.unit_id 
                      AND unit_checkins.incident_id = u.incident_id
                    ORDER BY checkin_time DESC 
                    LIMIT 1
                ) uc ON true
                WHERE u.incident_id = %s
                ORDER BY u.unit_id
            """, (incident_id,))
            
            units = []
            for unit in cursor.fetchall():
                unit_dict = dict(unit)
                # Convert datetime objects to strings for JSON serialization
                if unit_dict['created_at']:
                    unit_dict['created_at'] = unit_dict['created_at'].isoformat()
                if unit_dict['updated_at']:
                    unit_dict['updated_at'] = unit_dict['updated_at'].isoformat()
                if unit_dict['checkin_time']:
                    unit_dict['checkin_time'] = unit_dict['checkin_time'].isoformat()
                units.append(unit_dict)
            
            app.logger.info(f"Retrieved {len(units)} units for incident {incident_id}")
            return units
            
        except Exception as e:
            app.logger.error(f"Failed to get incident units: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()

    def update_unit_status(self, incident_id, unit_id, new_status):
        """Update unit status"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            # Validate status
            valid_statuses = ['staging', 'assigned', 'operating', 'recovering', 'returned']
            if new_status not in valid_statuses:
                raise ValueError(f"Invalid status. Must be one of: {', '.join(valid_statuses)}")
            
            cursor.execute("""
                UPDATE units 
                SET unit_status = %s, updated_at = NOW()
                WHERE incident_id = %s AND unit_id = %s
                RETURNING unit_id
            """, (new_status, incident_id, unit_id))
            
            result = cursor.fetchone()
            if not result:
                raise ValueError("Unit not found")
            
            conn.commit()
            app.logger.info(f"Updated unit {unit_id} status to {new_status}")
            return True
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Failed to update unit status: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()

    def get_incident_unit_checkins(self, incident_id):
        """Get all unit check-ins for an incident"""
        conn = self.connect_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            cursor.execute("""
                SELECT id, unit_id, officer_name, personnel_count, equipment_status,
                       ST_X(location_point) as longitude, ST_Y(location_point) as latitude,
                       photo_path, checkin_time, created_at, updated_at
                FROM unit_checkins 
                WHERE incident_id = %s
                ORDER BY checkin_time DESC
            """, (incident_id,))
            
            checkins = []
            for checkin in cursor.fetchall():
                checkin_dict = dict(checkin)
                # Convert datetime objects to strings for JSON serialization
                if checkin_dict['checkin_time']:
                    checkin_dict['checkin_time'] = checkin_dict['checkin_time'].isoformat()
                if checkin_dict['created_at']:
                    checkin_dict['created_at'] = checkin_dict['created_at'].isoformat()
                if checkin_dict['updated_at']:
                    checkin_dict['updated_at'] = checkin_dict['updated_at'].isoformat()
                checkins.append(checkin_dict)
            
            app.logger.info(f"Retrieved {len(checkins)} unit check-ins for incident {incident_id}")
            return checkins
            
        except Exception as e:
            app.logger.error(f"Failed to get unit check-ins: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()

    def get_available_assignment(self, incident_id):
        """Get an available assignment for a unit"""
        conn = self.connect_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Find unassigned division with highest priority
            cursor.execute("""
                SELECT division_id, division_name, priority, search_type,
                       estimated_duration, ST_AsGeoJSON(geom) as geometry
                FROM search_divisions 
                WHERE incident_id = %s AND status = 'unassigned'
                ORDER BY priority ASC, division_id ASC
                LIMIT 1
            """, (incident_id,))
            
            assignment = cursor.fetchone()
            if assignment:
                assignment_dict = dict(assignment)
                if assignment_dict['geometry']:
                    assignment_dict['geometry'] = json.loads(assignment_dict['geometry'])
                return assignment_dict
            
            return None
            
        except Exception as e:
            app.logger.error(f"Failed to get available assignment: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()

    def assign_unit_to_division(self, incident_id, unit_id, division_id, officer_name):
        """Assign a unit to a specific division"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            # Update the division
            cursor.execute("""
                UPDATE search_divisions 
                SET assigned_team = %s, team_leader = %s, status = 'assigned'
                WHERE incident_id = %s AND division_id = %s
            """, (unit_id, officer_name, incident_id, division_id))
            
            # Update the unit status and assignment
            cursor.execute("""
                UPDATE units 
                SET unit_status = 'assigned', assigned_division = %s, updated_at = NOW()
                WHERE incident_id = %s AND unit_id = %s
            """, (division_id, incident_id, unit_id))
            
            conn.commit()
            app.logger.info(f"Unit {unit_id} assigned to division {division_id}")
            return True
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Failed to assign unit to division: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()
    
    def get_incident_details(self, incident_id):
        """Get incident details including geospatial data"""
        conn = self.connect_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Get basic incident information
            cursor.execute("""
                SELECT incident_id, incident_name, incident_type, ic_name,
                       start_time, end_time, stage, description, address,
                       ST_X(center_point) as longitude, ST_Y(center_point) as latitude,
                       created_at, updated_at
                FROM incidents 
                WHERE incident_id = %s
            """, (incident_id,))
            
            incident = cursor.fetchone()
            if not incident:
                return None
            
            # Convert datetime objects to strings for JSON serialization
            if incident['start_time']:
                incident['start_time'] = incident['start_time'].isoformat()
            if incident['end_time']:
                incident['end_time'] = incident['end_time'].isoformat()
            if incident['created_at']:
                incident['created_at'] = incident['created_at'].isoformat()
            if incident['updated_at']:
                incident['updated_at'] = incident['updated_at'].isoformat()
            
            # Get search areas
            cursor.execute("""
                SELECT id, area_name, area_type, priority,
                       ST_AsGeoJSON(geom) as geometry
                FROM search_areas 
                WHERE incident_id = %s
                ORDER BY priority
            """, (incident_id,))
            
            search_areas = []
            for area in cursor.fetchall():
                area_dict = dict(area)
                area_dict['geometry'] = json.loads(area_dict['geometry'])
                search_areas.append(area_dict)
            
            incident['search_areas'] = search_areas
            
            app.logger.info(f"Retrieved incident details for {incident_id}")
            return dict(incident)
            
        except Exception as e:
            app.logger.error(f"Failed to get incident details: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()
    
    def get_incident_divisions(self, incident_id):
        """Get all divisions for an incident"""
        conn = self.connect_db()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            cursor.execute("""
                SELECT id, division_id, division_name, assigned_team, team_leader,
                       priority, search_type, estimated_duration, status,
                       created_at, updated_at,
                       ST_AsGeoJSON(geom) as geometry
                FROM search_divisions 
                WHERE incident_id = %s
                ORDER BY division_id
            """, (incident_id,))
            
            divisions = []
            for division in cursor.fetchall():
                div_dict = dict(division)
                if div_dict['geometry']:
                    div_dict['geometry'] = json.loads(div_dict['geometry'])
                if div_dict['created_at']:
                    div_dict['created_at'] = div_dict['created_at'].isoformat()
                if div_dict['updated_at']:
                    div_dict['updated_at'] = div_dict['updated_at'].isoformat()
                divisions.append(div_dict)
            
            app.logger.info(f"Retrieved {len(divisions)} divisions for incident {incident_id}")
            return divisions
            
        except Exception as e:
            app.logger.error(f"Failed to get incident divisions: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()
    
    def get_incident_qr_codes(self, incident_id):
        """Get QR codes for teams assigned to incident"""
        try:
            # Get unique teams from divisions
            divisions = self.get_incident_divisions(incident_id)
            teams = {}
            
            for division in divisions:
                if division['assigned_team'] and division['team_leader']:
                    team_id = division['assigned_team'].lower().replace(' ', '_')
                    if team_id not in teams:
                        teams[team_id] = {
                            'team_id': team_id,
                            'team_name': division['assigned_team'],
                            'team_leader': division['team_leader']
                        }
            
            # Check if QR codes already exist, if not generate them
            qr_codes = {}
            for team_id, team_info in teams.items():
                qr_filename = f"qr_{incident_id}_{team_id}.png"
                qr_path = os.path.join('static', 'qr_codes', qr_filename)
                
                if os.path.exists(qr_path):
                    # Load existing QR code
                    with open(qr_path, 'rb') as f:
                        qr_base64 = base64.b64encode(f.read()).decode()
                    
                    qr_codes[team_id] = {
                        'team_name': team_info['team_name'],
                        'team_leader': team_info['team_leader'],
                        'qr_code': qr_base64,
                        'qr_file': qr_filename
                    }
                else:
                    # Generate new QR code
                    project_config = {
                        'incident_id': incident_id,
                        'team_id': team_id,
                        'team_name': team_info['team_name'],
                        'team_leader': team_info['team_leader'],
                        'project_url': f'https://cloud.qfield.org/projects/{incident_id}_{team_id}',
                        'check_in_frequency': 15,
                        'emergency_contact': '+1-555-COMMAND',
                        'database_config': {
                            'host': os.getenv('EXTERNAL_DB_HOST', DB_CONFIG['host']),
                            'database': DB_CONFIG['database'],
                            'username': f"team_{team_id}",
                            'filter': f"assigned_team = '{team_info['team_name']}'"
                        }
                    }
                    
                    # Generate QR code
                    qr = qrcode.QRCode(version=1, box_size=10, border=5)
                    qr.add_data(json.dumps(project_config))
                    qr.make(fit=True)
                    
                    # Create QR code image
                    qr_image = qr.make_image(fill_color="black", back_color="white")
                    
                    # Save QR code to file
                    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
                    qr_image.save(qr_path)
                    
                    # Convert to base64 for web display
                    buffer = BytesIO()
                    qr_image.save(buffer, format='PNG')
                    buffer.seek(0)
                    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
                    
                    qr_codes[team_id] = {
                        'team_name': team_info['team_name'],
                        'team_leader': team_info['team_leader'],
                        'qr_code': qr_base64,
                        'qr_file': qr_filename,
                        'config': project_config
                    }
            
            app.logger.info(f"Retrieved/generated {len(qr_codes)} QR codes for incident {incident_id}")
            return qr_codes
            
        except Exception as e:
            app.logger.error(f"Failed to get incident QR codes: {e}")
            raise e
    
    def create_incident(self, incident_data):
        """Create new incident record with geocoded address"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            # Generate incident ID
            incident_id = f"USR{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:4].upper()}"
            
            # Geocode the location to get an address
            lat = float(incident_data['latitude'])
            lng = float(incident_data['longitude'])
            
            app.logger.info(f"Geocoding location for incident {incident_id}: {lat}, {lng}")
            geocode_result = reverse_geocode(lat, lng)
            
            address = None
            if geocode_result['success']:
                address = geocode_result['address']
                app.logger.info(f"Geocoded address for incident {incident_id}: {address}")
            else:
                app.logger.warning(f"Geocoding failed for incident {incident_id}")
            
            # Insert incident with address
            cursor.execute("""
                INSERT INTO incidents (
                    incident_id, incident_name, incident_type, ic_name, 
                    start_time, stage, center_point, description, address
                ) VALUES (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s)
                RETURNING incident_id
            """, (
                incident_id,
                incident_data['incident_name'],
                incident_data['incident_type'],
                incident_data['ic_name'],
                datetime.now(),
                'New',
                lng,  # longitude first for PostGIS
                lat,
                incident_data.get('description', ''),
                address
            ))
            
            conn.commit()
            app.logger.info(f"Created incident: {incident_id} at {address or f'{lat}, {lng}'}")
            return incident_id
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Failed to create incident: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()
    
    def create_search_area(self, incident_id, area_coordinates):
        """Create search area polygon"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            # Convert coordinates to polygon WKT
            if len(area_coordinates) >= 3:
                # Ensure polygon is closed
                if area_coordinates[0] != area_coordinates[-1]:
                    area_coordinates.append(area_coordinates[0])
                
                coords_str = ', '.join([f"{coord[0]} {coord[1]}" for coord in area_coordinates])
                polygon_wkt = f"POLYGON(({coords_str}))"
                
                cursor.execute("""
                    INSERT INTO search_areas (
                        incident_id, area_name, area_type, priority, geom
                    ) VALUES (%s, %s, %s, %s, ST_GeomFromText(%s, 4326))
                    RETURNING id
                """, (
                    incident_id,
                    'Primary Search Zone',
                    'hot_zone',
                    1,
                    polygon_wkt
                ))
                
                area_id = cursor.fetchone()[0]
                conn.commit()
                app.logger.info(f"Created search area {area_id} for incident {incident_id}")
                return area_id
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Failed to create search area: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()
    
    def create_divisions(self, incident_id, search_area_coords, division_count=4, teams=[]):
        """Create search divisions based on count rather than grid size"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            # Create polygon from coordinates
            polygon = Polygon(search_area_coords)
            bounds = polygon.bounds
            
            divisions = []
            division_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            
            # Calculate grid dimensions to get approximately the requested number of divisions
            import math
            total_divisions = min(division_count, 26)  # Max 26 divisions (A-Z)
            grid_ratio = math.sqrt(total_divisions)
            
            min_x, min_y, max_x, max_y = bounds
            x_steps = max(1, round(grid_ratio))
            y_steps = max(1, math.ceil(total_divisions / x_steps))
            
            x_step_size = (max_x - min_x) / x_steps
            y_step_size = (max_y - min_y) / y_steps
            
            division_counter = 0
            
            for i in range(x_steps):
                for j in range(y_steps):
                    if division_counter >= total_divisions:
                        break
                    
                    # Create grid cell
                    x1 = min_x + i * x_step_size
                    y1 = min_y + j * y_step_size
                    x2 = x1 + x_step_size
                    y2 = y1 + y_step_size
                    
                    cell = Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2), (x1, y1)])
                    
                    # Check if cell intersects with search area
                    if polygon.intersects(cell):
                        # Clip to search area
                        clipped = polygon.intersection(cell)
                        
                        if clipped.area > 0:
                            division_name = f"Division {division_letters[division_counter]}"
                            division_id = f"DIV-{division_letters[division_counter]}"
                            
                            # Convert back to WKT
                            if hasattr(clipped, 'exterior'):
                                coords = list(clipped.exterior.coords)
                                coords_str = ', '.join([f"{coord[0]} {coord[1]}" for coord in coords])
                                polygon_wkt = f"POLYGON(({coords_str}))"
                                
                                cursor.execute("""
                                    INSERT INTO search_divisions (
                                        incident_id, division_id, division_name,
                                        assigned_team, team_leader, priority,
                                        search_type, estimated_duration,
                                        status, geom
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))
                                    RETURNING id
                                """, (
                                    incident_id,
                                    division_id,
                                    division_name,
                                    None,  # No pre-assigned teams
                                    None,  # No pre-assigned team leaders
                                    1,
                                    'primary',
                                    '2 hours',
                                    'unassigned',
                                    polygon_wkt
                                ))
                                
                                div_id = cursor.fetchone()[0]
                                divisions.append({
                                    'id': div_id,
                                    'division_id': division_id,
                                    'division_name': division_name,
                                    'assigned_team': None,
                                    'team_leader': None
                                })
                                
                                division_counter += 1
            
            conn.commit()
            app.logger.info(f"Created {len(divisions)} divisions for incident {incident_id}")
            return divisions
            
        except Exception as e:
            conn.rollback()
            app.logger.error(f"Failed to create divisions: {e}")
            raise e
        finally:
            cursor.close()
            self.close_db()
    
    def generate_qr_codes(self, incident_id, teams):
        """Generate QR codes for teams"""
        qr_codes = {}
        
        for team in teams:
            # Create team-specific project configuration
            project_config = {
                'incident_id': incident_id,
                'team_id': team['team_id'],
                'team_name': team['team_name'],
                'team_leader': team['team_leader'],
                'project_url': f'https://cloud.qfield.org/projects/{incident_id}_{team["team_id"]}',
                'check_in_frequency': 15,
                'emergency_contact': '+1-555-COMMAND',
                'database_config': {
                    'host': os.getenv('EXTERNAL_DB_HOST', DB_CONFIG['host']),
                    'database': DB_CONFIG['database'],
                    'username': f"team_{team['team_id']}",
                    'filter': f"assigned_team = '{team['team_name']}'"
                }
            }
            
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(json.dumps(project_config))
            qr.make(fit=True)
            
            # Create QR code image
            qr_image = qr.make_image(fill_color="black", back_color="white")
            
            # Save QR code to file
            qr_filename = f"qr_{incident_id}_{team['team_id']}.png"
            qr_path = os.path.join('static', 'qr_codes', qr_filename)
            os.makedirs(os.path.dirname(qr_path), exist_ok=True)
            qr_image.save(qr_path)
            
            # Convert to base64 for web display
            buffer = BytesIO()
            qr_image.save(buffer, format='PNG')
            buffer.seek(0)
            qr_base64 = base64.b64encode(buffer.getvalue()).decode()
            
            qr_codes[team['team_id']] = {
                'team_name': team['team_name'],
                'team_leader': team['team_leader'],
                'qr_code': qr_base64,
                'qr_file': qr_filename,
                'config': project_config
            }
        
        app.logger.info(f"Generated {len(qr_codes)} QR codes for incident {incident_id}")
        return qr_codes

# Initialize incident manager
incident_mgr = IncidentManager()

@app.route('/health')
def health_check():
    """Health check endpoint for container orchestration"""
    try:
        db_healthy = incident_mgr.test_connection()
        if db_healthy:
            return jsonify({'status': 'healthy', 'database': 'connected'}), 200
        else:
            return jsonify({'status': 'unhealthy', 'database': 'disconnected'}), 503
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/unit-checkin')
def unit_checkin():
    """Mobile unit check-in page"""
    return render_template('unit_checkin.html')

@app.route('/api/geocode', methods=['POST'])
def geocode_location():
    """API endpoint for reverse geocoding coordinates"""
    try:
        data = request.json
        lat = float(data.get('latitude'))
        lng = float(data.get('longitude'))
        
        result = reverse_geocode(lat, lng)
        return jsonify(result)
        
    except (ValueError, TypeError) as e:
        return jsonify({
            'success': False,
            'error': 'Invalid coordinates provided'
        }), 400
    except Exception as e:
        app.logger.error(f"Geocoding API error: {e}")
        return jsonify({
            'success': False,
            'error': 'Geocoding service error'
        }), 500

@app.route('/api/incidents')
def get_incidents():
    """API endpoint to get active incidents"""
    try:
        incidents = incident_mgr.get_active_incidents()
        return jsonify({'success': True, 'incidents': incidents})
    except Exception as e:
        app.logger.error(f"Error getting incidents: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/incident/<incident_id>/stage', methods=['PUT'])
def update_incident_stage(incident_id):
    """Update incident stage"""
    try:
        data = request.json
        new_stage = data.get('stage')
        
        if not new_stage:
            return jsonify({'success': False, 'error': 'Stage is required'}), 400
        
        incident_mgr.update_incident_stage(incident_id, new_stage)
        
        return jsonify({'success': True, 'message': f'Incident stage updated to {new_stage}'})
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error updating incident stage: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/incident/<incident_id>/unit/<unit_id>/status', methods=['PUT'])
def update_unit_status(incident_id, unit_id):
    """Update unit status"""
    try:
        data = request.json
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({'success': False, 'error': 'Status is required'}), 400
        
        incident_mgr.update_unit_status(incident_id, unit_id, new_status)
        
        return jsonify({'success': True, 'message': f'Unit {unit_id} status updated to {new_status}'})
        
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        app.logger.error(f"Error updating unit status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/unit-checkin', methods=['POST'])
def submit_unit_checkin():
    """Submit unit check-in"""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['incident_id', 'unit_id', 'officer_name', 'personnel_count', 'equipment_status']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        
        # Save photo if provided
        photo_path = None
        if 'photo' in request.files:
            photo = request.files['photo']
            if photo.filename:
                filename = f"unit_{data['unit_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                photo_path = os.path.join('static', 'unit_photos', filename)
                os.makedirs(os.path.dirname(photo_path), exist_ok=True)
                photo.save(photo_path)
                data['photo_path'] = photo_path
        
        # Submit check-in
        checkin_id = incident_mgr.submit_unit_checkin(data)
        
        # Get available assignment
        assignment = incident_mgr.get_available_assignment(data['incident_id'])
        
        # Assign unit to division if available
        if assignment:
            incident_mgr.assign_unit_to_division(
                data['incident_id'], 
                data['unit_id'], 
                assignment['division_id'],
                data['officer_name']
            )
        
        return jsonify({
            'success': True,
            'checkin_id': checkin_id,
            'assignment': assignment
        })
        
    except Exception as e:
        app.logger.error(f"Error submitting unit check-in: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/create_incident', methods=['POST'])
def create_incident():
    try:
        data = request.json
        
        # Validate input
        if not data.get('incident', {}).get('incident_name'):
            return jsonify({'success': False, 'error': 'Incident name is required'}), 400
        
        if not data.get('search_area_coordinates') or len(data.get('search_area_coordinates', [])) < 3:
            return jsonify({'success': False, 'error': 'Search area must have at least 3 coordinates'}), 400
        
        # Create incident (now includes geocoding)
        incident_id = incident_mgr.create_incident(data['incident'])
        
        # Create search area
        area_id = incident_mgr.create_search_area(
            incident_id, 
            data['search_area_coordinates']
        )
        
        # Create divisions based on division count
        divisions = incident_mgr.create_divisions(
            incident_id,
            data['search_area_coordinates'],
            data.get('division_count', 4),
            data.get('teams', [])
        )
        
        # Generate QR codes (empty for now since no pre-assigned teams)
        qr_codes = incident_mgr.generate_qr_codes(
            incident_id,
            data.get('teams', [])
        )
        
        return jsonify({
            'success': True,
            'incident_id': incident_id,
            'area_id': area_id,
            'divisions': divisions,
            'qr_codes': qr_codes
        })
        
    except Exception as e:
        app.logger.error(f"Error creating incident: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/incident/<incident_id>')
def view_incident(incident_id):
    """View incident details and QR codes"""
    return render_template('incident_view.html', incident_id=incident_id)

@app.route('/api/incident/<incident_id>')
def get_incident_data(incident_id):
    """API endpoint to get complete incident data for frontend"""
    try:
        # Get incident details
        incident = incident_mgr.get_incident_details(incident_id)
        if not incident:
            return jsonify({'success': False, 'error': 'Incident not found'}), 404
        
        # Get divisions
        divisions = incident_mgr.get_incident_divisions(incident_id)
        
        # Get units (new method)
        units = incident_mgr.get_incident_units(incident_id)
        
        # Get unit check-ins (for backwards compatibility)
        unit_checkins = incident_mgr.get_incident_unit_checkins(incident_id)
        
        # Get QR codes (for any assigned teams)
        qr_codes = incident_mgr.get_incident_qr_codes(incident_id)
        
        return jsonify({
            'success': True,
            'incident': incident,
            'divisions': divisions,
            'units': units,
            'unit_checkins': unit_checkins,
            'qr_codes': qr_codes
        })
        
    except Exception as e:
        app.logger.error(f"Error getting incident data for {incident_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/qr/<filename>')
def get_qr_code(filename):
    """Serve QR code images"""
    try:
        return send_file(os.path.join('static', 'qr_codes', filename))
    except Exception as e:
        app.logger.error(f"Error serving QR code {filename}: {e}")
        return "QR Code not found", 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
