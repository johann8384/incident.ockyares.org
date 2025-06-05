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


@app.route("/api/geocode/reverse", methods=["POST"])
@log_request_data
def reverse_geocode():
    """Reverse geocode coordinates to address using GeocodingService"""
    data = request.get_json()

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is None or longitude is None:
        logger.warning("Missing latitude or longitude in reverse geocode request")
        return jsonify({"error": "Latitude and longitude are required"}), 400

    # Convert to float
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid coordinate format: lat={latitude}, lng={longitude}, error={e}")
        return jsonify({"error": "Invalid latitude or longitude values"}), 400

    # Use GeocodingService instead of direct API call
    result = geocoding_service.reverse_geocode(latitude, longitude)

    if result["success"]:
        logger.info(f"Successful reverse geocode: {latitude},{longitude} -> {result.get('address')}")
        return jsonify(
            {
                "success": True,
                "address": result["address"],
                "formatted_address": result.get("formatted_address"),
                "address_components": result.get("address_components"),
                "data": result.get("raw_data"),
            }
        )
    else:
        logger.error(f"Reverse geocode failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]}), 500


@app.route("/api/geocode/forward", methods=["POST"])
@log_request_data
def forward_geocode():
    """Forward geocode address to coordinates using GeocodingService"""
    data = request.get_json()

    address = data.get("address")
    if not address:
        logger.warning("Missing address in forward geocode request")
        return jsonify({"error": "Address is required"}), 400

    # Use GeocodingService for forward geocoding
    result = geocoding_service.forward_geocode(address)

    if result["success"]:
        logger.info(f"Successful forward geocode: {address} -> {result['count']} results")
        return jsonify(
            {
                "success": True,
                "results": result["results"],
                "count": result["count"],
            }
        )
    else:
        logger.error(f"Forward geocode failed: {result['error']}")
        return jsonify({"success": False, "error": result["error"]}), 500


@app.route("/api/hospitals/search", methods=["POST"])
@log_request_data
def search_hospitals():
    """Search for hospitals near a location using server-side API call"""
    data = request.get_json()

    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is None or longitude is None:
        logger.warning("Missing coordinates in hospital search request")
        return jsonify({"error": "Latitude and longitude are required"}), 400

    # Convert to float
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid coordinates in hospital search: lat={latitude}, lng={longitude}, error={e}")
        return jsonify({"error": "Invalid latitude or longitude values"}), 400

    # Get hospital data using the hospital model
    hospital_manager = Hospital(db_manager)
    result = hospital_manager.get_hospitals_for_location(
        latitude=latitude, longitude=longitude, use_cache=True
    )

    if result["success"]:
        logger.info(f"Hospital search successful: {result['total_found']} hospitals found")
        return jsonify(
            {
                "success": True,
                "hospitals": result["hospitals"],
                "total_found": result["total_found"],
                "source": result["source"],
            }
        )
    else:
        logger.error(f"Hospital search failed: {result.get('error', 'Unknown error')}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": result.get("error", "Unknown error"),
                    "hospitals": {},
                }
            ),
            500,
        )


@app.route("/api/divisions/generate", methods=["POST"])
@log_request_data
def generate_divisions_preview():
    """Generate search divisions for preview (without saving to database)"""
    data = request.get_json()

    # Validate required fields
    if not data.get("coordinates") or len(data.get("coordinates", [])) < 3:
        logger.warning(f"Invalid coordinates for division generation: {data.get('coordinates')}")
        return (
            jsonify(
                {"error": "Search area coordinates required (minimum 3 points)"}
            ),
            400,
        )

    # Create temporary incident instance for division generation
    incident = Incident(db_manager)

    # Generate divisions without saving
    divisions = incident.generate_divisions_preview(
        search_area_coordinates=data["coordinates"],
        area_size_m2=data.get("area_size_m2", 40000),
    )

    logger.info(f"Generated {len(divisions)} divisions for preview")
    return jsonify(
        {
            "success": True,
            "divisions": divisions,
            "count": len(divisions),
            "message": f"Generated {len(divisions)} search divisions for preview",
        }
    )


# UNIFIED UNIT STATUS ENDPOINTS

@app.route("/api/unit/<unit_id>/status", methods=["POST"])
@log_request_data
def update_unit_status_unified(unit_id):
    """
    Unified status update endpoint for both check-ins and status changes
    Check-in is just a status update to 'staging' with unit details
    """
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['incident_id', 'status']
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        logger.warning(f"Missing required fields for unit {unit_id}: {missing_fields}")
        return jsonify({"error": f"Required fields missing: {', '.join(missing_fields)}"}), 400
    
    # Create unit instance
    unit = Unit()
    unit.unit_id = unit_id
    
    logger.info(f"Updating unit {unit_id} status to {data['status']} for incident {data['incident_id']}")
    
    # Call unified status update method
    result = unit.update_status(
        incident_id=data['incident_id'],
        new_status=data['status'],
        division_id=data.get('division_id'),
        percentage_complete=data.get('percentage_complete', 0),
        latitude=data.get('latitude'),
        longitude=data.get('longitude'),
        notes=data.get('notes'),
        user_name=data.get('user_name'),
        # Check-in specific fields (required for staging status)
        unit_name=data.get('unit_name'),
        unit_type=data.get('unit_type'),
        unit_leader=data.get('unit_leader'),
        contact_info=data.get('contact_info'),
        number_of_personnel=data.get('number_of_personnel'),
        bsar_tech=data.get('bsar_tech', False)
    )
    
    if result["success"]:
        logger.info(f"Unit {unit_id} status update successful: {result['message']}")
        return jsonify(result)
    else:
        logger.error(f"Unit {unit_id} status update failed: {result['error']}")
        return jsonify({"error": result["error"]}), 400


@app.route("/api/incident/<incident_id>/assign-division", methods=["POST"])
@log_request_data
def assign_division_to_unit(incident_id):
    """Assign a division to a unit"""
    data = request.get_json()
    
    if not data.get('unit_id') or not data.get('division_id'):
        logger.warning(f"Missing unit_id or division_id for division assignment in incident {incident_id}")
        return jsonify({"error": "unit_id and division_id are required"}), 400
    
    unit = Unit()
    unit.unit_id = data['unit_id']
    
    logger.info(f"Assigning unit {data['unit_id']} to division {data['division_id']} in incident {incident_id}")
    result = unit.assign_to_division(incident_id, data['division_id'])
    
    if result["success"]:
        logger.info(f"Division assignment successful: {result['message']}")
        return jsonify(result)
    else:
        logger.error(f"Division assignment failed: {result['error']}")
        return jsonify({"error": result["error"]}), 500


# NEW DIVISION MANAGEMENT ENDPOINTS

@app.route("/api/incident/<incident_id>/division/<division_id>/assign-unit", methods=["POST"])
@log_request_data
def assign_unit_to_division(incident_id, division_id):
    """Assign a unit to a division"""
    data = request.get_json()
    
    unit_id = data.get('unit_id')
    if not unit_id:
        return jsonify({"error": "unit_id is required"}), 400
    
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Update the search_divisions table with unit assignment and status change
            cursor.execute("""
                UPDATE search_divisions 
                SET assigned_unit_id = %s, status = 'assigned'
                WHERE incident_id = %s AND division_id = %s
            """, (unit_id, incident_id, division_id))
            
            if cursor.rowcount == 0:
                return jsonify({"error": "Division not found"}), 404
            
            # Update unit status to assigned
            cursor.execute("""
                UPDATE units 
                SET current_status = 'assigned',
                    current_division_id = %s
                WHERE unit_id = %s AND current_incident_id = %s
            """, (division_id, unit_id, incident_id))
            
            conn.commit()
            
            logger.info(f"Assigned unit {unit_id} to division {division_id} in incident {incident_id}")
            return jsonify({
                "success": True,
                "message": f"Unit {unit_id} assigned to division {division_id}"
            })
            
    except Exception as e:
        logger.error(f"Error assigning unit to division: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident/<incident_id>/division/<division_id>/priority", methods=["POST"])
@log_request_data
def update_division_priority(incident_id, division_id):
    """Update division priority"""
    data = request.get_json()
    
    priority = data.get('priority')
    if priority not in ['High', 'Medium', 'Low']:
        return jsonify({"error": "Priority must be High, Medium, or Low"}), 400
    
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE search_divisions 
                SET priority = %s
                WHERE incident_id = %s AND division_id = %s
            """, (priority, incident_id, division_id))
            
            if cursor.rowcount == 0:
                return jsonify({"error": "Division not found"}), 404
            
            conn.commit()
            
            logger.info(f"Updated division {division_id} priority to {priority} in incident {incident_id}")
            return jsonify({
                "success": True,
                "message": f"Division {division_id} priority updated to {priority}"
            })
            
    except Exception as e:
        logger.error(f"Error updating division priority: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident/<incident_id>/available-units", methods=["GET"])
@log_request_data
def get_available_units(incident_id):
    """Get units available for assignment (not Recovering, Quarters, or Out of Service)"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT unit_id, unit_name, unit_type, unit_leader, current_status
                FROM units 
                WHERE current_incident_id = %s 
                AND current_status NOT IN ('Recovering', 'Quarters', 'Out of Service')
                ORDER BY unit_id
            """, (incident_id,))
            
            units = []
            for row in cursor.fetchall():
                units.append({
                    'unit_id': row[0],
                    'unit_name': row[1],
                    'unit_type': row[2],
                    'unit_leader': row[3],
                    'current_status': row[4]
                })
            
            logger.info(f"Retrieved {len(units)} available units for incident {incident_id}")
            return jsonify({
                "success": True,
                "units": units,
                "count": len(units)
            })
            
    except Exception as e:
        logger.error(f"Error getting available units: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/incident/<incident_id>/units", methods=["GET"])
@log_request_data
def get_incident_units(incident_id):
    """Get all units for an incident"""
    units = Unit.get_units_by_incident(incident_id)
    logger.info(f"Retrieved {len(units)} units for incident {incident_id}")
    return jsonify({
        "success": True,
        "units": units,
        "count": len(units)
    })


@app.route("/api/unit/<unit_id>/history", methods=["GET"])
@log_request_data
def get_unit_history(unit_id):
    """Get status history for a unit"""
    incident_id = request.args.get('incident_id')
    history = Unit.get_unit_status_history(unit_id, incident_id)
    
    logger.info(f"Retrieved {len(history)} history records for unit {unit_id}")
    return jsonify({
        "success": True,
        "history": history,
        "count": len(history)
    })


# BACKWARD COMPATIBILITY ENDPOINTS

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


# EXISTING INCIDENT ENDPOINTS

@app.route("/api/incident", methods=["POST"])
@log_request_data
def create_incident():
    """Create new incident with full data including location, hospitals, and divisions"""
    data = request.get_json()

    # Validate required fields
    if not data.get("name") or not data.get("incident_type"):
        logger.warning("Incident creation attempted without required fields")
        return jsonify({"error": "Name and incident type are required"}), 400

    logger.info(f"Creating incident: {data.get('name')} ({data.get('incident_type')})")

    # Create incident with all available data
    incident = Incident(db_manager)
    incident_id = incident.create_incident(
        name=data["name"],
        incident_type=data["incident_type"],
        description=data.get("description", ""),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        address=data.get("address"),
        hospital_data=data.get("hospital_data"),
        search_area_coordinates=data.get("search_area_coordinates"),
        divisions=data.get("divisions"),  # Save divisions if provided
    )

    logger.info(f"Incident created successfully: {incident_id}")
    return jsonify(
        {
            "success": True,
            "incident_id": incident_id,
            "message": "Incident created successfully",
        }
    )


@app.route("/api/incident/<incident_id>", methods=["GET"])
@log_request_data
def get_incident(incident_id):
    """Get incident details including hospitals and divisions"""
    incident = Incident.get_incident_by_id(incident_id, db_manager)
    if not incident:
        logger.warning(f"Attempt to retrieve non-existent incident: {incident_id}")
        return jsonify({"error": "Incident not found"}), 404

    incident_data = incident.get_incident_data()
    logger.info(f"Retrieved incident data for: {incident_id}")
    return jsonify({"success": True, "incident": incident_data})


@app.route("/api/incident/<incident_id>/location", methods=["POST"])
@log_request_data
def set_incident_location(incident_id):
    """Set incident location"""
    data = request.get_json()

    if not data.get("latitude") or not data.get("longitude"):
        logger.warning(f"Invalid location data for incident {incident_id}")
        return jsonify({"error": "Latitude and longitude are required"}), 400

    incident = Incident(db_manager)
    incident.incident_id = incident_id

    success = incident.set_location(
        latitude=float(data["latitude"]), longitude=float(data["longitude"])
    )

    if success:
        logger.info(f"Location set for incident {incident_id}: {data['latitude']},{data['longitude']}")
        return jsonify(
            {
                "success": True,
                "address": incident.address,
                "message": "Location set successfully",
            }
        )
    else:
        logger.error(f"Failed to set location for incident {incident_id}")
        return jsonify({"error": "Failed to set location"}), 500


@app.route("/api/incident/<incident_id>/search-area", methods=["POST"])
@log_request_data
def set_search_area(incident_id):
    """Set search area polygon"""
    data = request.get_json()

    if not data.get("coordinates") or len(data["coordinates"]) < 3:
        logger.warning(f"Invalid search area coordinates for incident {incident_id}")
        return (
            jsonify({"error": "At least 3 coordinates required for polygon"}),
            400,
        )

    incident = Incident(db_manager)
    incident.incident_id = incident_id

    success = incident.set_search_area(data["coordinates"])

    if success:
        logger.info(f"Search area set for incident {incident_id}")
        return jsonify({"success": True, "message": "Search area set successfully"})
    else:
        logger.error(f"Failed to set search area for incident {incident_id}")
        return jsonify({"error": "Failed to set search area"}), 500


@app.route("/api/incident/<incident_id>/hospitals", methods=["POST"])
@log_request_data
def save_hospital_data(incident_id):
    """Save hospital data for incident"""
    data = request.get_json()

    if not data.get("hospital_data"):
        logger.warning(f"Missing hospital data for incident {incident_id}")
        return jsonify({"error": "Hospital data is required"}), 400

    incident = Incident(db_manager)
    incident.incident_id = incident_id

    success = incident.save_hospital_data(data["hospital_data"])

    if success:
        logger.info(f"Hospital data saved for incident {incident_id}")
        return jsonify(
            {"success": True, "message": "Hospital data saved successfully"}
        )
    else:
        logger.error(f"Failed to save hospital data for incident {incident_id}")
        return jsonify({"error": "Failed to save hospital data"}), 500


@app.route("/api/incident/<incident_id>/divisions", methods=["POST"])
@log_request_data
def save_divisions(incident_id):
    """Save search divisions for existing incident"""
    data = request.get_json()

    if not data.get("divisions"):
        logger.warning(f"Missing divisions data for incident {incident_id}")
        return jsonify({"error": "Divisions data is required"}), 400

    incident = Incident.get_incident_by_id(incident_id, db_manager)
    if not incident:
        logger.warning(f"Attempt to save divisions for non-existent incident: {incident_id}")
        return jsonify({"error": "Incident not found"}), 404

    success = incident.save_divisions(data["divisions"])

    if success:
        logger.info(f"Saved {len(data['divisions'])} divisions for incident {incident_id}")
        return jsonify(
            {
                "success": True,
                "message": f"Saved {len(data['divisions'])} divisions successfully",
            }
        )
    else:
        logger.error(f"Failed to save divisions for incident {incident_id}")
        return jsonify({"error": "Failed to save divisions"}), 500


@app.route("/api/incident/<incident_id>/divisions", methods=["GET"])
@log_request_data
def get_divisions(incident_id):
    """Get search divisions for incident"""
    incident = Incident(db_manager)
    incident.incident_id = incident_id

    divisions = incident.get_divisions()

    logger.info(f"Retrieved {len(divisions)} divisions for incident {incident_id}")
    return jsonify(
        {"success": True, "divisions": divisions, "count": len(divisions)}
    )


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
