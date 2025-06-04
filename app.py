from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import os

from models.database import DatabaseManager
from models.incident import Incident

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')

# Initialize database
db_manager = DatabaseManager()

@app.route('/')
def index():
    """Main incident creation page"""
    return render_template('index.html')

@app.route('/api/incident', methods=['POST'])
def create_incident():
    """Create new incident"""
    try:
        data = request.get_json()
        
        # Validate required fields
        if not data.get('name') or not data.get('incident_type'):
            return jsonify({'error': 'Name and incident type are required'}), 400
        
        # Create incident
        incident = Incident(db_manager)
        incident_id = incident.create_incident(
            name=data['name'],
            incident_type=data['incident_type'],
            description=data.get('description', '')
        )
        
        return jsonify({
            'success': True,
            'incident_id': incident_id,
            'message': 'Incident created successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/incident/<incident_id>/location', methods=['POST'])
def set_incident_location(incident_id):
    """Set incident location"""
    try:
        data = request.get_json()
        
        if not data.get('latitude') or not data.get('longitude'):
            return jsonify({'error': 'Latitude and longitude are required'}), 400
        
        incident = Incident(db_manager)
        incident.incident_id = incident_id
        
        success = incident.set_location(
            latitude=float(data['latitude']),
            longitude=float(data['longitude'])
        )
        
        if success:
            return jsonify({
                'success': True,
                'address': incident.address,
                'message': 'Location set successfully'
            })
        else:
            return jsonify({'error': 'Failed to set location'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/incident/<incident_id>/search-area', methods=['POST'])
def set_search_area(incident_id):
    """Set search area polygon"""
    try:
        data = request.get_json()
        
        if not data.get('coordinates') or len(data['coordinates']) < 3:
            return jsonify({'error': 'At least 3 coordinates required for polygon'}), 400
        
        incident = Incident(db_manager)
        incident.incident_id = incident_id
        
        success = incident.set_search_area(data['coordinates'])
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Search area set successfully'
            })
        else:
            return jsonify({'error': 'Failed to set search area'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/incident/<incident_id>/divisions', methods=['POST'])
def generate_divisions(incident_id):
    """Generate search divisions"""
    try:
        incident = Incident(db_manager)
        incident.incident_id = incident_id
        
        # Load incident data from database to get search area
        # TODO: Add method to load existing incident
        
        divisions = incident.generate_divisions()
        
        return jsonify({
            'success': True,
            'divisions': divisions,
            'count': len(divisions),
            'message': f'Generated {len(divisions)} search divisions'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db_manager.connect()
        db_manager.close()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected'
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503

if __name__ == '__main__':
    # Initialize database schema on startup
    try:
        db_manager.create_tables()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Database initialization failed: {e}")
    
    app.run(
        debug=os.getenv('FLASK_DEBUG', 'True').lower() == 'true',
        host='0.0.0.0',
        port=int(os.getenv('FLASK_PORT', 5000))
    )