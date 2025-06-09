"""Incident management API routes"""

import logging
from flask import Blueprint, request, jsonify

from routes.common import log_request_data, validate_coordinates, validate_required_fields
from models.database import DatabaseManager
from models.incident import Incident

logger = logging.getLogger(__name__)
incidents_bp = Blueprint('incidents', __name__, url_prefix='/api')

# Initialize database manager
db_manager = DatabaseManager()


@incidents_bp.route("/incident/<incident_id>/location", methods=["POST"])
@log_request_data
def set_incident_location(incident_id):
    """Set incident location"""
    data = request.get_json()
    
    coords, error = validate_coordinates(data, required=True)
    if error:
        logger.warning(f"Invalid location data for incident {incident_id}")
        return jsonify({"error": error}), 400
    
    latitude, longitude = coords
    
    incident = Incident(db_manager)
    incident.incident_id = incident_id

    success = incident.set_location(latitude=latitude, longitude=longitude)

    if success:
        logger.info(f"Location set for incident {incident_id}: {latitude},{longitude}")
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


@incidents_bp.route("/incident/<incident_id>/search-area", methods=["POST"])
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


@incidents_bp.route("/incident/<incident_id>/hospitals", methods=["POST"])
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


@incidents_bp.route("/incident/<incident_id>/divisions", methods=["POST"])
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


@incidents_bp.route("/incident/<incident_id>/divisions", methods=["GET"])
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


@incidents_bp.route("/incident", methods=["POST"])
@log_request_data
def create_incident():
    """Create new incident with full data including location, hospitals, and divisions"""
    data = request.get_json()

    # Validate required fields
    valid, error = validate_required_fields(data, ["name", "incident_type"])
    if not valid:
        logger.warning("Incident creation attempted without required fields")
        return jsonify({"error": error}), 400

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


@incidents_bp.route("/incident/<incident_id>", methods=["GET"])
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


@incidents_bp.route("/incidents/active", methods=["GET"])
@log_request_data
def get_active_incidents():
    """Get all incidents with status 'active'"""
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT incident_id, name, incident_type, description, 
                       ST_X(incident_location) as latitude, 
                       ST_Y(incident_location) as longitude, 
                       address, status, created_at
                FROM incidents 
                WHERE status = 'active'
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
