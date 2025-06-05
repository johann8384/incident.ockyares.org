"""
Unit Model - Unified status tracking system
All unit interactions are status updates, including initial check-in
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import os
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# Database config
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgis'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'emergency_ops'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'emergency_password')
}


class Unit:
    """Represents an emergency response unit with unified status tracking"""

    # Unit status constants
    STATUS_QUARTERS = 'quarters'
    STATUS_STAGING = 'staging'  # Initial check-in status
    STATUS_ASSIGNED = 'assigned' 
    STATUS_OPERATING = 'operating'
    STATUS_RECOVERING = 'recovering'
    STATUS_OUT_OF_SERVICE = 'out_of_service'
    
    VALID_STATUSES = [
        STATUS_QUARTERS, STATUS_STAGING, STATUS_ASSIGNED, 
        STATUS_OPERATING, STATUS_RECOVERING, STATUS_OUT_OF_SERVICE
    ]

    def __init__(self, unit_data: Optional[Dict[str, Any]] = None):
        # Initialize from data if provided
        if unit_data:
            self.id = unit_data.get("id")
            self.unit_id = unit_data.get("unit_id")
            self.unit_name = unit_data.get("unit_name")
            self.unit_type = unit_data.get("unit_type")
            self.unit_leader = unit_data.get("unit_leader")
            self.contact_info = unit_data.get("contact_info")
            self.number_of_personnel = unit_data.get("number_of_personnel")
            self.bsar_tech = unit_data.get("bsar_tech", False)
            self.current_status = unit_data.get("current_status", self.STATUS_QUARTERS)
            self.current_incident_id = unit_data.get("current_incident_id")
            self.current_division_id = unit_data.get("current_division_id")
            self.created_at = unit_data.get("created_at")
        else:
            # Initialize empty unit
            self.id = None
            self.unit_id = None
            self.unit_name = None
            self.unit_type = None
            self.unit_leader = None
            self.contact_info = None
            self.number_of_personnel = None
            self.bsar_tech = False
            self.current_status = self.STATUS_QUARTERS
            self.current_incident_id = None
            self.current_division_id = None
            self.created_at = None

    def validate_status_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate unit status update data"""
        errors = []

        # Required fields
        required_fields = ["incident_id", "status", "unit_id"]
        for field in required_fields:
            if not data.get(field):
                field_name = field.replace("_", " ").title()
                errors.append(f"{field_name} is required")

        # Validate status
        if data.get("status") and data["status"] not in self.VALID_STATUSES:
            errors.append(f"Invalid status. Must be one of: {', '.join(self.VALID_STATUSES)}")

        # For staging (check-in), require additional fields
        if data.get("status") == self.STATUS_STAGING:
            checkin_fields = ["unit_name", "unit_type", "unit_leader", "latitude", "longitude"]
            for field in checkin_fields:
                if not data.get(field):
                    field_name = field.replace("_", " ").title()
                    errors.append(f"{field_name} is required for check-in")

            # Validate coordinates for staging
            try:
                if data.get("latitude") is not None and data.get("longitude") is not None:
                    latitude = float(data["latitude"])
                    longitude = float(data["longitude"])
                    if not (-90 <= latitude <= 90):
                        errors.append("Latitude must be between -90 and 90")
                    if not (-180 <= longitude <= 180):
                        errors.append("Longitude must be between -180 and 180")
            except (ValueError, TypeError):
                errors.append("Invalid coordinate format")

            # Validate personnel count
            try:
                if data.get("number_of_personnel"):
                    personnel_count = int(data["number_of_personnel"])
                    if personnel_count < 1:
                        errors.append("Personnel count must be at least 1")
            except (ValueError, TypeError):
                errors.append("Invalid personnel count format")

        return {"valid": len(errors) == 0, "errors": errors}

    def update_status(self, incident_id: str, new_status: str, division_id: str = None, 
                     percentage_complete: int = 0, latitude: float = None, 
                     longitude: float = None, notes: str = None, user_name: str = None,
                     unit_name: str = None, unit_type: str = None, unit_leader: str = None,
                     contact_info: str = None, number_of_personnel: int = None, 
                     bsar_tech: bool = False) -> Dict[str, Any]:
        """
        Universal status update method that handles both check-ins and status changes
        
        Args:
            incident_id: Incident ID
            new_status: New status value
            division_id: Division assignment (optional)
            percentage_complete: Progress percentage (optional)
            latitude: Location latitude (optional)
            longitude: Location longitude (optional) 
            notes: Status notes (optional)
            user_name: User making the update (optional)
            unit_name: Unit name (required for staging/check-in)
            unit_type: Unit type (required for staging/check-in)
            unit_leader: Unit leader (required for staging/check-in)
            contact_info: Contact information (optional)
            number_of_personnel: Personnel count (optional)
            bsar_tech: BSAR tech availability (optional)
            
        Returns:
            Dictionary with result
        """
        
        # Validate status
        if new_status not in self.VALID_STATUSES:
            return {"success": False, "error": f"Invalid status: {new_status}"}
            
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # For staging (check-in), create or update unit record
            if new_status == self.STATUS_STAGING:
                if not all([unit_name, unit_type, unit_leader]):
                    return {"success": False, "error": "Unit name, type, and leader required for check-in"}
                
                # Create/update unit record
                cursor.execute("""
                    INSERT INTO units (unit_id, unit_name, unit_type, unit_leader, 
                                     contact_info, number_of_personnel, bsar_tech,
                                     current_status, current_incident_id, current_division_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (unit_id) DO UPDATE SET
                        unit_name = EXCLUDED.unit_name,
                        unit_type = EXCLUDED.unit_type,
                        unit_leader = EXCLUDED.unit_leader,
                        contact_info = EXCLUDED.contact_info,
                        number_of_personnel = EXCLUDED.number_of_personnel,
                        bsar_tech = EXCLUDED.bsar_tech,
                        current_status = EXCLUDED.current_status,
                        current_incident_id = EXCLUDED.current_incident_id,
                        current_division_id = EXCLUDED.current_division_id
                """, (
                    self.unit_id, unit_name, unit_type, unit_leader,
                    contact_info, number_of_personnel, bsar_tech,
                    new_status, incident_id, division_id
                ))
                
            else:
                # For other status updates, just update current status
                cursor.execute("""
                    UPDATE units 
                    SET current_status = %s, current_incident_id = %s, current_division_id = %s
                    WHERE unit_id = %s
                """, (new_status, incident_id, division_id, self.unit_id))
            
            # Log to status history
            if latitude is not None and longitude is not None:
                cursor.execute("""
                    INSERT INTO unit_status_history 
                    (unit_id, incident_id, division_id, status, percentage_complete, 
                     latitude, longitude, notes, user_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (self.unit_id, incident_id, division_id, new_status, percentage_complete,
                      float(latitude), float(longitude), notes, user_name))
            else:
                cursor.execute("""
                    INSERT INTO unit_status_history 
                    (unit_id, incident_id, division_id, status, percentage_complete, 
                     notes, user_name)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (self.unit_id, incident_id, division_id, new_status, percentage_complete,
                      notes, user_name))
            
            # If status is out_of_service, unassign from divisions
            if new_status == self.STATUS_OUT_OF_SERVICE:
                cursor.execute("""
                    UPDATE search_divisions 
                    SET assigned_unit_id = NULL 
                    WHERE assigned_unit_id = %s AND incident_id = %s
                """, (self.unit_id, incident_id))
            
            conn.commit()
            self.current_status = new_status
            self.current_incident_id = incident_id
            self.current_division_id = division_id
            
            action = "checked in" if new_status == self.STATUS_STAGING else "status updated"
            logger.info(f"Unit {self.unit_id} {action} to {new_status}")
            
            return {
                "success": True,
                "message": f"Unit {self.unit_id} {action} successfully",
                "status": new_status
            }
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to update unit status: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def assign_to_division(self, incident_id: str, division_id: str) -> Dict[str, Any]:
        """Assign unit to a search division"""
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()
            
            # Update division assignment
            cursor.execute("""
                UPDATE search_divisions 
                SET assigned_unit_id = %s 
                WHERE division_id = %s AND incident_id = %s
            """, (self.unit_id, division_id, incident_id))
            
            conn.commit()
            
            # Update unit status to assigned
            return self.update_status(incident_id, self.STATUS_ASSIGNED, division_id)
            
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Failed to assign unit to division: {e}")
            return {"success": False, "error": str(e)}
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def to_dict(self) -> Dict[str, Any]:
        """Convert unit to dictionary representation"""
        return {
            "id": self.id,
            "unit_id": self.unit_id,
            "unit_name": self.unit_name,
            "unit_type": self.unit_type,
            "unit_leader": self.unit_leader,
            "contact_info": self.contact_info,
            "number_of_personnel": self.number_of_personnel,
            "bsar_tech": self.bsar_tech,
            "current_status": self.current_status,
            "current_incident_id": self.current_incident_id,
            "current_division_id": self.current_division_id,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    @staticmethod
    def get_units_by_incident(incident_id: str) -> List[Dict[str, Any]]:
        """Get all units for an incident"""
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            cursor.execute("""
                SELECT u.*, sd.division_name 
                FROM units u
                LEFT JOIN search_divisions sd ON u.current_division_id = sd.division_id
                WHERE u.current_incident_id = %s
                ORDER BY u.unit_name
            """, (incident_id,))
            
            return cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Error getting units by incident: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_unit_status_history(unit_id: str, incident_id: str = None) -> List[Dict[str, Any]]:
        """Get status history for a unit"""
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            
            if incident_id:
                cursor.execute("""
                    SELECT ush.*, sd.division_name
                    FROM unit_status_history ush
                    LEFT JOIN search_divisions sd ON ush.division_id = sd.division_id
                    WHERE ush.unit_id = %s AND ush.incident_id = %s
                    ORDER BY ush.timestamp DESC
                """, (unit_id, incident_id))
            else:
                cursor.execute("""
                    SELECT ush.*, sd.division_name
                    FROM unit_status_history ush
                    LEFT JOIN search_divisions sd ON ush.division_id = sd.division_id
                    WHERE ush.unit_id = %s
                    ORDER BY ush.timestamp DESC
                """, (unit_id,))
            
            return cursor.fetchall()
            
        except Exception as e:
            logger.error(f"Error getting unit status history: {e}")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_unit_by_id(unit_id: str) -> Optional["Unit"]:
        """Get specific unit by ID"""
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            cursor.execute("""
                SELECT * FROM units WHERE unit_id = %s
            """, (unit_id,))

            row = cursor.fetchone()
            if row:
                return Unit(dict(row))
            return None

        except Exception as e:
            logger.error(f"Error retrieving unit {unit_id}: {e}")
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @staticmethod
    def get_unit_count_for_incident(incident_id: str) -> int:
        """Get count of units for incident"""
        conn = None
        cursor = None
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT COUNT(*) FROM units WHERE current_incident_id = %s
            """, (incident_id,))

            count = cursor.fetchone()[0]
            return count

        except Exception as e:
            logger.error(f"Error getting unit count for incident {incident_id}: {e}")
            return 0
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
