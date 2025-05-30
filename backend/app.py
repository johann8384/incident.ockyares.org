from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
import os
import logging

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'incident_app'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'postgres_password')
}

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return None

@app.route('/')
def hello_world():
    """Hello world endpoint"""
    return jsonify({
        'message': 'Hello World from Flask!',
        'status': 'running',
        'service': 'incident-management-backend'
    })

@app.route('/health')
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'message': 'All systems operational'
            }), 200
        else:
            return jsonify({
                'status': 'unhealthy',
                'database': 'disconnected',
                'message': 'Database connection failed'
            }), 503
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503

@app.route('/api/incidents', methods=['GET'])
def get_incidents():
    """Get all incidents"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, description, 
                   ST_X(location) as longitude, 
                   ST_Y(location) as latitude,
                   created_at, updated_at
            FROM incidents 
            ORDER BY created_at DESC
        """)
        
        incidents = []
        for row in cursor.fetchall():
            incidents.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'longitude': row[3],
                'latitude': row[4],
                'created_at': row[5].isoformat() if row[5] else None,
                'updated_at': row[6].isoformat() if row[6] else None
            })
        
        cursor.close()
        conn.close()
        
        return jsonify(incidents)
        
    except Exception as e:
        logger.error(f"Error fetching incidents: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/incidents', methods=['POST'])
def create_incident():
    """Create new incident"""
    try:
        data = request.json
        
        if not data or not data.get('name'):
            return jsonify({'error': 'Name is required'}), 400
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO incidents (name, description, location)
            VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
            RETURNING id, name, description, 
                     ST_X(location) as longitude, 
                     ST_Y(location) as latitude,
                     created_at
        """, (
            data['name'],
            data.get('description', ''),
            data.get('longitude', -84.27277),
            data.get('latitude', 37.839333)
        ))
        
        row = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        
        incident = {
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'longitude': row[3],
            'latitude': row[4],
            'created_at': row[5].isoformat() if row[5] else None
        }
        
        return jsonify(incident), 201
        
    except Exception as e:
        logger.error(f"Error creating incident: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
