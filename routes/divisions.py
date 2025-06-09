"""Division management API routes"""

import logging
from flask import Blueprint, request, jsonify

from routes.common import log_request_data
from models.database import DatabaseManager
from models.incident import Incident

logger = logging.getLogger(__name__)
divisions_bp = Blueprint('divisions', __name__, url_prefix='/api')

# Initialize database manager
db_manager = DatabaseManager()


@divisions_bp.route("/divisions/generate", methods=["POST"])
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


@divisions_bp.route("/incident/<incident_id>/assign-division", methods=["POST"])
@log_request_data
def assign_division_to_unit(incident_id):
    """Assign a division to a unit"""
    from models.unit import Unit
    
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


@divisions_bp.route("/incident/<incident_id>/division/<division_id>/assign-unit", methods=["POST"])
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


@divisions_bp.route("/incident/<incident_id>/division/<division_id>/priority", methods=["POST"])
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


@divisions_bp.route("/incident/<incident_id>/available-units", methods=["GET"])
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
