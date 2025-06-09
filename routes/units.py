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
    - Division completion and unit recovery (100% complete -> recovering + division completed)
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
    requested_status = data['status']
    division_id = data.get('division_id')
    percentage_complete = int(data.get('percentage_complete', 0))
    
    logger.info(f"Unit {unit_id} requesting status {requested_status} for incident {incident_id}, progress: {percentage_complete}%")
    
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
            
            # Start with the requested status
            new_status = requested_status
            auto_transitioned = False
            
            # Apply business logic for status transitions
            
            # 1. 100% completion triggers automatic division completion and recovery
            if percentage_complete == 100:
                new_status = 'recovering'
                auto_transitioned = True
                logger.info(f"100% completion reported - auto-transitioning unit {unit_id} to recovering")
                
                # Determine which division to mark as completed
                completed_division = division_id or current_division
                
                if completed_division:
                    cursor.execute("""
                        UPDATE search_divisions 
                        SET status = 'completed', assigned_unit_id = NULL
                        WHERE incident_id = %s AND division_id = %s
                    """, (incident_id, completed_division))
                    
                    if cursor.rowcount > 0:
                        logger.info(f"Marked division {completed_division} as completed and unassigned unit {unit_id}")
                    else:
                        logger.warning(f"No division found to mark as completed: {completed_division}")
                    
                    # Clear division assignment since it's now completed
                    division_id = None
                else:
                    logger.warning(f"No division specified for completion by unit {unit_id}")
            
            # 2. Assigned->Operating automatically when % > 0 (but not 100% which is handled above)
            elif current_status == 'assigned' and percentage_complete > 0:
                new_status = 'operating'
                logger.info(f"Auto-transitioning unit {unit_id} from assigned to operating due to progress > 0%")
            
            # 3. Handle division unassignment for certain status changes (only if not completing)
            elif new_status in ['staging', 'out of service', 'quarters'] and current_division:
                # Unassign division from unit (but don't mark as completed)
                cursor.execute("""
                    UPDATE search_divisions 
                    SET assigned_unit_id = NULL, status = 'unassigned'
                    WHERE incident_id = %s AND assigned_unit_id = %s
                """, (incident_id, unit_id))
                
                logger.info(f"Unassigned unit {unit_id} from division {current_division}")
                division_id = None  # Clear division assignment
            
            # 4. If recovering->operating, require division selection
            elif current_status == 'recovering' and new_status == 'operating':
                if not division_id:
                    return jsonify({"error": "Division selection required when returning to operating status"}), 400
                
                # Assign to new division
                cursor.execute("""
                    UPDATE search_divisions 
                    SET assigned_unit_id = %s, status = 'assigned'
                    WHERE incident_id = %s AND division_id = %s
                """, (unit_id, incident_id, division_id))
                logger.info(f"Assigned unit {unit_id} to new division {division_id} when returning to operating")
            
            # Update unit status
            cursor.execute("""
                UPDATE units 
                SET current_status = %s, current_division_id = %s
                WHERE unit_id = %s AND current_incident_id = %s
            """, (new_status, division_id, unit_id, incident_id))
            
            # Record status history - use the division that was completed if 100%
            history_division_id = current_division if percentage_complete == 100 else (division_id or current_division)
            cursor.execute("""
                INSERT INTO unit_status_history 
                (unit_id, incident_id, division_id, status, percentage_complete, latitude, longitude, notes, user_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                unit_id, incident_id, history_division_id, 
                new_status, percentage_complete,
                data.get('latitude'), data.get('longitude'), data.get('notes'), data.get('user_name')
            ))
            
            conn.commit()
            
            # Prepare response message
            if auto_transitioned:
                message = f"Division completed! Unit {unit_id} status updated to {new_status}"
            else:
                message = f"Unit {unit_id} status updated to {new_status}"
            
            logger.info(f"Status update complete: {message}")
            return jsonify({
                "success": True,
                "message": message,
                "new_status": new_status,
                "division_id": division_id,
                "auto_transitioned": auto_transitioned
            })
            
    except Exception as e:
        logger.error(f"Error updating unit status: {str(e)}")
        return jsonify({"error": str(e)}), 500


@units_bp.route("/unit/<unit_id>/divisions", methods=["GET"])
@log_request_data
def get_unit_divisions(unit_id):
    """Get divisions available for a specific unit (currently assigned + unassigned divisions)"""
    incident_id = request.args.get('incident_id')
    if not incident_id:
        return jsonify({"error": "incident_id parameter is required"}), 400
    
    try:
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get divisions that are either:
            # 1. Currently assigned to this unit
            # 2. Unassigned (available for assignment)
            # Exclude completed divisions from selection
            cursor.execute("""
                SELECT division_id, division_name, status, assigned_unit_id, priority,
                       ST_AsGeoJSON(division_polygon) as polygon_geojson
                FROM search_divisions 
                WHERE incident_id = %s 
                AND (assigned_unit_id = %s OR assigned_unit_id IS NULL)
                AND status != 'completed'
                ORDER BY 
                    CASE WHEN assigned_unit_id = %s THEN 0 ELSE 1 END,  -- Show assigned divisions first
                    priority DESC,
                    division_name
            """, (incident_id, unit_id, unit_id))
            
            divisions = []
            for row in cursor.fetchall():
                divisions.append({
                    'division_id': row[0],
                    'division_name': row[1],
                    'status': row[2],
                    'assigned_unit_id': row[3],
                    'priority': row[4],
                    'polygon_geojson': row[5],
                    'is_assigned_to_unit': row[3] == unit_id
                })
            
            logger.info(f"Retrieved {len(divisions)} available divisions for unit {unit_id} in incident {incident_id}")
            return jsonify({
                "success": True,
                "divisions": divisions,
                "count": len(divisions)
            })
            
    except Exception as e:
        logger.error(f"Error getting divisions for unit {unit_id}: {str(e)}")
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
