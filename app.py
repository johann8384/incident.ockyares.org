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
    
    def create_incident(self, incident_data):
        """Create new incident record"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            # Generate incident ID
            incident_id = f"USR{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:4].upper()}"
            
            # Insert incident
            cursor.execute("""
                INSERT INTO incidents (
                    incident_id, incident_name, incident_type, ic_name, 
                    start_time, status, center_point, description
                ) VALUES (%s, %s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
                RETURNING incident_id
            """, (
                incident_id,
                incident_data['incident_name'],
                incident_data['incident_type'],
                incident_data['ic_name'],
                datetime.now(),
                'active',
                float(incident_data['longitude']),
                float(incident_data['latitude']),
                incident_data.get('description', '')
            ))
            
            conn.commit()
            app.logger.info(f"Created incident: {incident_id}")
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
    
    def create_divisions(self, incident_id, search_area_coords, grid_size=100, teams=[]):
        """Create search divisions"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            # Create polygon from coordinates
            polygon = Polygon(search_area_coords)
            bounds = polygon.bounds
            
            divisions = []
            division_counter = 0
            
            # Create grid divisions
            min_x, min_y, max_x, max_y = bounds
            
            x_steps = max(1, int((max_x - min_x) * 111000 / grid_size))  # Convert to meters approx
            y_steps = max(1, int((max_y - min_y) * 111000 / grid_size))
            
            x_step_size = (max_x - min_x) / x_steps
            y_step_size = (max_y - min_y) / y_steps
            
            division_letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            
            for i in range(x_steps):
                for j in range(y_steps):
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
                            division_name = f"Division {division_letters[division_counter % 26]}"
                            division_id = f"DIV-{division_letters[division_counter % 26]}"
                            
                            # Assign team if available
                            assigned_team = None
                            team_leader = None
                            if division_counter < len(teams):
                                assigned_team = teams[division_counter]['team_name']
                                team_leader = teams[division_counter]['team_leader']
                            
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
                                    assigned_team,
                                    team_leader,
                                    1,
                                    'primary',
                                    '2 hours',
                                    'assigned' if assigned_team else 'unassigned',
                                    polygon_wkt
                                ))
                                
                                div_id = cursor.fetchone()[0]
                                divisions.append({
                                    'id': div_id,
                                    'division_id': division_id,
                                    'division_name': division_name,
                                    'assigned_team': assigned_team,
                                    'team_leader': team_leader
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

@app.route('/create_incident', methods=['POST'])
def create_incident():
    try:
        data = request.json
        
        # Validate input
        if not data.get('incident', {}).get('incident_name'):
            return jsonify({'success': False, 'error': 'Incident name is required'}), 400
        
        if not data.get('search_area_coordinates') or len(data.get('search_area_coordinates', [])) < 3:
            return jsonify({'success': False, 'error': 'Search area must have at least 3 coordinates'}), 400
        
        # Create incident
        incident_id = incident_mgr.create_incident(data['incident'])
        
        # Create search area
        area_id = incident_mgr.create_search_area(
            incident_id, 
            data['search_area_coordinates']
        )
        
        # Create divisions
        divisions = incident_mgr.create_divisions(
            incident_id,
            data['search_area_coordinates'],
            data.get('grid_size', 100),
            data.get('teams', [])
        )
        
        # Generate QR codes
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