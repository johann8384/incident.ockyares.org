"""Unit management API routes"""

import logging
from flask import Blueprint, request, jsonify

from routes.common import log_request_data, validate_required_fields
from models.database import DatabaseManager
from models.unit import Unit
from models.incident import Incident

logger = logging.getLogger(__name__)
units_bp = Blueprint('units', __name__, url_prefix='/api')

# Initialize database manager
db_manager = DatabaseManager()


@units_bp.route("/unit/<unit_id>/status", methods=["POST"])
@log_request_data
def update_unit_status_unified(unit_id):
    """
    Enhanced unified status update endpoint with business logic for:
    - Automatic status transitions (assigned->operating when % > 0)
    - Division unassignment when going to staging/out of service/quarters
    - Division status updates when units are unassigned
    """
    data = request.get_json()
    
    # Validate required fields
    valid, error = validate_required_fields(data, ['incident_id', 'status'])
    if not valid:
        logger.warning(f"Missing required fields for unit {unit_id}: {error}")
        return jsonify({"error": error}), 400
    
    incident_id = data['incident_id']
    new_status = data['status']
    division_id = data.get('division_id')
    percentage_complete = data.get('percentage_complete', 0)
    
    logger.info(f"Updating unit {unit_id} status to {new_status} for incident {incident_id}")
    
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get current unit status and division
            cursor.execute("""
                SELECT current_status, current_division_id 
                FROM units 
                WHERE unit_id = %s AND current_incident_id = %s
            """, (unit_id, incident_id))
            
            current_unit = cursor.fetchone()
            if not current_unit:
                return jsonify({"error": "Unit not found for this incident"}), 404
                
            current_status = current_unit[0]
            current_division = current_unit[1]
            
            # Apply business logic for status transitions
            
            # 1. Assigned->Operating automatically when % > 0
            if current_status == 'assigned' and percentage_complete > 0:
                new_status = 'operating'
            
            # 2. Handle division unassignment for certain status changes
            units_to_unassign_divisions = ['staging', 'out of service', 'quarters']
            if new_status in units_to_unassign_divisions and current_division:
                # Unassign division from unit
                cursor.execute("""
                    UPDATE search_divisions 
                    SET assigned_unit_id = NULL, status = 'unassigned'
                    WHERE incident_id = %s AND assigned_unit_id = %s
                """, (incident_id, unit_id))
                
                logger.info(f"Unassigned unit {unit_id} from division {current_division}")
                division_id = None  # Clear division assignment
            
            # 3. Handle "out of service" status - unassign from division
            if new_status == 'out of service' and current_division:
                cursor.execute("""
                    UPDATE search_divisions 
                    SET assigned_unit_id = NULL, status = 'unassigned'
                    WHERE incident_id = %s AND assigned_unit_id = %s
                """, (incident_id, unit_id))
                
                logger.info(f"Unit {unit_id} going out of service - unassigned from division {current_division}")
                division_id = None
            
            # 4. If recovering->operating, require division selection
            if current_status == 'recovering' and new_status == 'operating':
                if not division_id:
                    return jsonify({"error": "Division selection required when returning to operating status"}), 400
                
                # Assign to new division
                cursor.execute("""
                    UPDATE search_divisions 
                    SET assigned_unit_id = %s, status = 'assigned'
                    WHERE incident_id = %s AND division_id = %s
                """, (unit_id, incident_id, division_id))
            
            # Update unit status
            cursor.execute("""
                UPDATE units 
                SET current_status = %s, current_division_id = %s
                WHERE unit_id = %s AND current_incident_id = %s
            """, (new_status, division_id, unit_id, incident_id))
            
            # Record status history
            cursor.execute("""
                INSERT INTO unit_status_history 
                (unit_id, incident_id, division_id, status, percentage_complete, latitude, longitude, notes, user_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                unit_id, incident_id, division_id, new_status, percentage_complete,
                data.get('latitude'), data.get('longitude'), data.get('notes'), data.get('user_name')
            ))
            
            conn.commit()
            
            logger.info(f"Unit {unit_id} status updated to {new_status}")
            return jsonify({
                "success": True,
                "message": f"Unit {unit_id} status updated to {new_status}",
                "new_status": new_status,
                "division_id": division_id
            })
            
    except Exception as e:
        logger.error(f"Error updating unit status: {str(e)}")
        return jsonify({"error": str(e)}), 500


@units_bp.route("/incident/<incident_id>/units", methods=["GET"])
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


@units_bp.route("/unit/<unit_id>/history", methods=["GET"])
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


@units_bp.route("/unit/checkin", methods=["POST"])
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
