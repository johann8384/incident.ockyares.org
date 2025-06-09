import os
import logging
import traceback
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from models.database import DatabaseManager
from models.hospital import Hospital
from models.incident import Incident
from models.unit import Unit
from services.geocoding import GeocodingService

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-key")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize services
db_manager = DatabaseManager()
geocoding_service = GeocodingService()


def log_request_data(func):
    """Decorator to log request data for API endpoints"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            # Log request details
            logger.info(f"API Call: {request.method} {request.path}")
            logger.info(f"Remote IP: {request.remote_addr}")
            logger.info(f"User Agent: {request.headers.get('User-Agent', 'Unknown')}")
            
            # Log request data for POST/PUT requests
            if request.method in ['POST', 'PUT', 'PATCH']:
                if request.is_json:
                    data = request.get_json()
                    # Sanitize sensitive data
                    sanitized_data = {k: v for k, v in data.items() if k not in ['password', 'token']}
                    logger.info(f"Request data: {sanitized_data}")
                else:
                    logger.info(f"Request content type: {request.content_type}")
            
            # Call the actual function
            result = func(*args, **kwargs)
            
            # Log successful response
            if hasattr(result, 'status_code'):
                logger.info(f"Response status: {result.status_code}")
            
            return result
            
        except Exception as e:
            # Log the full exception with traceback
            logger.error(f"Error in {func.__name__}: {str(e)}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            
            # Return structured error response
            return jsonify({
                "error": str(e),
                "endpoint": request.path,
                "method": request.method,
                "timestamp": str(logger.handlers[0].formatter.formatTime(logging.LogRecord(
                    name='', level=0, pathname='', lineno=0, msg='', args=(), exc_info=None
                ), logger.handlers[0].formatter.datefmt))
            }), 500
    
    return wrapper


@app.errorhandler(404)
def not_found(error):
    logger.warning(f"404 error: {request.path} not found")
    return jsonify({"error": "Endpoint not found", "path": request.path}), 404


@app.errorhandler(405)
def method_not_allowed(error):
    logger.warning(f"405 error: {request.method} not allowed for {request.path}")
    return jsonify({"error": "Method not allowed", "method": request.method, "path": request.path}), 405


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {str(error)}")
    logger.error(f"Full traceback: {traceback.format_exc()}")
    return jsonify({"error": "Internal server error", "message": str(error)}), 500


@app.route("/")
def index():
    """Main incident creation page"""
    return render_template("index.html")


@app.route("/incident/<incident_id>")
def view_incident(incident_id):
    """View specific incident"""
    return render_template("incident_view.html", incident_id=incident_id)


@app.route("/incident/<incident_id>/unit-checkin")
def unit_checkin(incident_id):
    """Unit checkin page"""
    return render_template("unit_checkin.html", incident_id=incident_id)


@app.route("/incident/<incident_id>/unit-status")
def unit_status_page(incident_id):
    """Unit status update page"""
    return render_template("unit_status.html", incident_id=incident_id)


@app.route("/api/incidents/active", methods=["GET"])
@log_request_data
def get_active_incidents():
    """Get all incidents with status 'Active'"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT incident_id, name, incident_type, description, 
                       latitude, longitude, address, status, created_at
                FROM incidents 
                WHERE status = 'Active'
                ORDER BY created_at DESC
            """)
            
            incidents = []
            for row in cursor.fetchall():
                incidents.append({
                    'incident_id': row[0],
                    'name': row[1],
                    'incident_type': row[2],
                    'description': row[3] or '',
                    'latitude': float(row[4]) if row[4] else None,
                    'longitude': float(row[5]) if row[5] else None,
                    'address': row[6] or '',
                    'status': row[7],
                    'created_at': row[8].isoformat() if row[8] else None
                })
            
            logger.info(f"Retrieved {len(incidents)} active incidents")
            return jsonify({
                "success": True,
                "incidents": incidents,
                "count": len(incidents)
            })
            
    except Exception as e:
        logger.error(f"Error getting active incidents: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/unit/checkin", methods=["POST"])
@log_request_data
def unit_checkin_api():
    """
    Backward compatibility endpoint for unit check-in
    Redirects to unified status update with staging status
    """
    data = request.get_json()
    
    # Check if incident exists first
    incident = Incident.get_incident_by_id(data.get("incident_id"), db_manager)
    if not incident:
        logger.warning(f"Unit checkin attempted for non-existent incident: {data.get('incident_id')}")
        return jsonify({"error": "Incident not found"}), 404

    logger.info(f"Unit {data.get('unit_id')} checking in to incident {data.get('incident_id')}")

    # Map old checkin fields to new status update format
    status_data = {
        'incident_id': data.get('incident_id'),
        'new_status': 'staging',  # Check-in is staging status
        'unit_name': data.get('unit_id'),  # Use unit_id as name if no name provided
        'unit_type': data.get('unit_type', 'Unknown'),
        'unit_leader': data.get('company_officer'),
        'contact_info': data.get('contact_info'),
        'number_of_personnel': data.get('number_of_personnel'),
        'bsar_tech': data.get('bsar_tech', False),
        'latitude': data.get('latitude'),
        'longitude': data.get('longitude'),
        'notes': data.get('notes', 'Unit checked in'),
        'user_name': data.get('company_officer')
    }
    
    # Create unit and update status
    unit = Unit()
    unit.unit_id = data.get('unit_id')
    result = unit.update_status(**status_data)
    
    if result["success"]:
        logger.info(f"Unit checkin successful: {data.get('unit_id')}")
        return jsonify({
            "success": True,
            "unit_id": data.get('unit_id'),
            "message": result["message"]
        })
    else:
        logger.error(f"Unit checkin failed: {result['error']}")
        return jsonify({"error": result["error"]}), 400


@app.route("/health")
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db_manager.connect()
        db_manager.close()

        logger.info("Health check successful")
        return jsonify({"status": "healthy", "database": "connected"})
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "unhealthy", "error": str(e)}), 503


if __name__ == "__main__":
    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)
    
    # Initialize database schema on startup
    try:
        db_manager.create_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")

    logger.info("Starting Emergency Incident Management System")
    app.run(
        debug=os.getenv("FLASK_DEBUG", "True").lower() == "true",
        host="0.0.0.0",
        port=int(os.getenv("FLASK_PORT", 5000)),
    )
