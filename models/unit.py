"""
Unit Model - Represents emergency response units and their management
Enhanced with comprehensive status tracking
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import os
import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)

# Database config for status functionality (fallback to environment)
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgis'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'emergency_ops'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'emergency_password')
}


class Unit:
    """Represents an emergency response unit with enhanced status tracking"""

    # Unit status constants (NEW)
    STATUS_STAGING = 'staging'
    STATUS_ASSIGNED = 'assigned' 
    STATUS_OPERATING = 'operating'
    STATUS_RECOVERING = 'recovering'
    STATUS_OUT_OF_SERVICE = 'out_of_service'
    STATUS_QUARTERS = 'quarters'
    
    VALID_STATUSES = [
        STATUS_STAGING, STATUS_ASSIGNED, STATUS_OPERATING,
        STATUS_RECOVERING, STATUS_OUT_OF_SERVICE, STATUS_QUARTERS
    ]

    def __init__(self, db_manager=None, unit_data: Optional[Dict[str, Any]] = None):
        self.db_manager = db_manager

        # Initialize from data if provided
        if unit_data:
            self.id = unit_data.get("id")
            self.incident_id = unit_data.get("incident_id")
            self.unit_id = unit_data.get("unit_id")
            self.company_officer = unit_data.get("company_officer")
            self.number_of_personnel = unit_data.get("number_of_personnel")
            self.bsar_tech = unit_data.get("bsar_tech", False)
            self.latitude = unit_data.get("latitude")
            self.longitude = unit_data.get("longitude")
            self.status = unit_data.get("status", "active")
            self.checked_in_at = unit_data.get("checked_in_at")
            self.last_updated = unit_data.get("last_updated")
            self.notes = unit_data.get("notes", "")
            
            # NEW: Enhanced status fields
            self.unit_name = unit_data.get("unit_name")
            self.unit_type = unit_data.get("unit_type")
            self.unit_leader = unit_data.get("unit_leader")
            self.current_status = unit_data.get("current_status", self.STATUS_QUARTERS)
            self.current_division_id = unit_data.get("current_division_id")
        else:
            # Initialize empty unit
            self.id = None
            self.incident_id = None
            self.unit_id = None
            self.company_officer = None
            self.number_of_personnel = None
            self.bsar_tech = False
            self.latitude = None
            self.longitude = None
            self.status = "active"
            self.checked_in_at = None
            self.last_updated = None
            self.notes = ""
            
            # NEW: Enhanced status fields
            self.unit_name = None
            self.unit_type = None
            self.unit_leader = None
            self.current_status = self.STATUS_QUARTERS
            self.current_division_id = None

    def validate_checkin_data(self, data: Dict[str, Any]) -> Dict[str, str]:
        """
        Validate unit check-in data

        Args:
            data: Dictionary containing unit check-in data

        Returns:
            Dictionary with validation results {'valid': bool, 'errors': list}
        """
        errors = []

        # Required fields
        required_fields = [
            "incident_id",
            "unit_id",
            "company_officer",
            "number_of_personnel",
            "latitude",
            "longitude",
        ]

        for field in required_fields:
            if not data.get(field):
                field_name = field.replace("_", " ").title()
                errors.append(f"{field_name} is required")

        # Validate numeric fields
        try:
            personnel_count = int(data.get("number_of_personnel", 0))
            if personnel_count < 1:
                errors.append("Personnel count must be at least 1")
        except (ValueError, TypeError):
            errors.append("Invalid personnel count format")

        try:
            latitude = float(data.get("latitude", 0))
            longitude = float(data.get("longitude", 0))

            # Basic coordinate validation
            if not (-90 <= latitude <= 90):
                errors.append("Latitude must be between -90 and 90")
            if not (-180 <= longitude <= 180):
                errors.append("Longitude must be between -180 and 180")

        except (ValueError, TypeError):
            errors.append("Invalid coordinate format")

        return {"valid": len(errors) == 0, "errors": errors}

    def is_already_checked_in(self, incident_id: str, unit_id: str) -> bool:
        """
        Check if unit is already checked into the incident

        Args:
            incident_id: Incident ID
            unit_id: Unit ID

        Returns:
            True if unit is already checked in
        """
        try:
            conn = self.db_manager.connect()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id FROM units 
                WHERE incident_id = %s AND unit_id = %s
            """,
                (incident_id, unit_id),
            )

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return result is not None

        except Exception as e:
            logger.error(f"Error checking unit status: {e}")
            return False

    def checkin_to_incident(self, checkin_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check in unit to an incident

        Args:
            checkin_data: Dictionary containing all check-in information

        Returns:
            Dictionary with result {'success': bool, 'unit_id': str, 'message': str, 'error': str}
        """
        try:
            # Validate data
            validation = self.validate_checkin_data(checkin_data)
            if not validation["valid"]:
                return {"success": False, "error": "; ".join(validation["errors"])}

            # Check if unit already checked in
            if self.is_already_checked_in(
                checkin_data["incident_id"], checkin_data["unit_id"]
            ):
                return {
                    "success": False,
                    "error": f"Unit {checkin_data['unit_id']} is already checked in to this incident",
                }

            # Insert unit into database
            conn = self.db_manager.connect()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO units (
                    incident_id, unit_id, company_officer, number_of_personnel, 
                    bsar_tech, latitude, longitude, notes, status, checked_in_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """,
                (
                    checkin_data["incident_id"],
                    checkin_data["unit_id"],
                    checkin_data["company_officer"],
                    int(checkin_data["number_of_personnel"]),
                    checkin_data.get("bsar_tech", False),
                    float(checkin_data["latitude"]),
                    float(checkin_data["longitude"]),
                    checkin_data.get("notes", ""),
                    "active",
                    datetime.now(),
                ),
            )

            unit_db_id = cursor.fetchone()[0]
            
            # NEW: Also insert into new units table if it exists
            try:
                # Check if new units table exists and create entry there
                cursor.execute("""
                    INSERT INTO units (unit_id, unit_name, unit_type, unit_leader, 
                                     current_status, current_incident_id)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (unit_id) DO UPDATE SET
                        current_status = %s,
                        current_incident_id = %s
                """, (
                    checkin_data["unit_id"],
                    checkin_data.get("unit_name", checkin_data["unit_id"]),
                    checkin_data.get("unit_type", "Unknown"),
                    checkin_data["company_officer"],
                    self.STATUS_STAGING,
                    checkin_data["incident_id"],
                    self.STATUS_STAGING,
                    checkin_data["incident_id"]
                ))
                
                # Log initial status
                cursor.execute("""
                    INSERT INTO unit_status_history 
                    (unit_id, incident_id, status, notes, user_name,
                     location)
                    VALUES (%s, %s, %s, %s, %s, 
                            ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                """, (
                    checkin_data["unit_id"],
                    checkin_data["incident_id"],
                    self.STATUS_STAGING,
                    "Unit checked in",
                    checkin_data["company_officer"],
                    float(checkin_data["longitude"]),
                    float(checkin_data["latitude"])
                ))
                
            except Exception as status_error:
                # If status tables don't exist yet, that's okay
                logger.info(f"Status tracking not available yet: {status_error}")

            conn.commit()
            cursor.close()
            conn.close()

            # Update instance with new data
            self.id = unit_db_id
            self.incident_id = checkin_data["incident_id"]
            self.unit_id = checkin_data["unit_id"]
            self.company_officer = checkin_data["company_officer"]
            self.number_of_personnel = int(checkin_data["number_of_personnel"])
            self.bsar_tech = checkin_data.get("bsar_tech", False)
            self.latitude = float(checkin_data["latitude"])
            self.longitude = float(checkin_data["longitude"])
            self.notes = checkin_data.get("notes", "")
            self.status = "active"
            self.checked_in_at = datetime.now()
            self.current_status = self.STATUS_STAGING

            logger.info(
                f"Unit {self.unit_id} checked in to incident {self.incident_id}"
            )

            return {
                "success": True,
                "unit_id": self.unit_id,
                "message": f"Unit {self.unit_id} checked in successfully",
            }

        except Exception as e:
            logger.error(f"Error checking in unit: {e}")
            return {"success": False, "error": str(e)}

    def update_status(self, new_status: str) -> bool:
        """
        Update unit status (original method - keeping for backward compatibility)

        Args:
            new_status: New status value

        Returns:
            True if successful
        """
        try:
            if not self.id:
                return False

            conn = self.db_manager.connect()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE units 
                SET status = %s, last_updated = %s
                WHERE id = %s
            """,
                (new_status, datetime.now(), self.id),
            )

            conn.commit()
            cursor.close()
            conn.close()

            self.status = new_status
            self.last_updated = datetime.now()

            return True

        except Exception as e:
            logger.error(f"Error updating unit status: {e}")
            return False

    def update_location(self, latitude: float, longitude: float) -> bool:
        """
        Update unit location

        Args:
            latitude: New latitude
            longitude: New longitude

        Returns:
            True if successful
        """
        try:
            if not self.id:
                return False

            conn = self.db_manager.connect()
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE units 
                SET latitude = %s, longitude = %s, last_updated = %s
                WHERE id = %s
            """,
                (latitude, longitude, datetime.now(), self.id),
            )

            conn.commit()
            cursor.close()
            conn.close()

            self.latitude = latitude
            self.longitude = longitude
            self.last_updated = datetime.now()

            return True

        except Exception as e:
            logger.error(f"Error updating unit location: {e}")
            return False

    # NEW STATUS MANAGEMENT METHODS

    def connect_status_db(self):
        """Get database connection for status functionality"""
        try:
            return psycopg2.connect(**DB_CONFIG)
        except Exception as e:
            logger.error(f"Status database connection failed: {e}")
            raise

    def create_unit_record(self, unit_id, unit_name, unit_type, unit_leader, contact_info=None):
        """Create new unit record in status tracking system"""
        conn = self.connect_status_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO units (unit_id, unit_name, unit_type, unit_leader, contact_info)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (unit_id) DO UPDATE SET
                    unit_name = EXCLUDED.unit_name,
                    unit_type = EXCLUDED.unit_type,
                    unit_leader = EXCLUDED.unit_leader,
                    contact_info = EXCLUDED.contact_info
                RETURNING id
            """, (unit_id, unit_name, unit_type, unit_leader, contact_info))
            
            unit_db_id = cursor.fetchone()[0]
            conn.commit()
            logger.info(f"Created/updated unit record: {unit_id}")
            return unit_db_id
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to create unit record: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def update_enhanced_status(self, incident_id, new_status, division_id=None, 
                             percentage_complete=0, latitude=None, longitude=None, 
                             notes=None, user_name=None):
        """Update unit status with enhanced tracking"""
        
        if new_status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")
            
        conn = self.connect_status_db()
        cursor = conn.cursor()
        
        try:
            # Update current status in units table
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
                     location, notes, user_name)
                    VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s)
                """, (self.unit_id, incident_id, division_id, new_status, percentage_complete,
                      float(longitude), float(latitude), notes, user_name))
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
            logger.info(f"Updated unit {self.unit_id} status to {new_status}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to update unit status: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def assign_to_division(self, incident_id, division_id):
        """Assign unit to a search division"""
        conn = self.connect_status_db()
        cursor = conn.cursor()
        
        try:
            # Update division assignment
            cursor.execute("""
                UPDATE search_divisions 
                SET assigned_unit_id = %s 
                WHERE division_id = %s AND incident_id = %s
            """, (self.unit_id, division_id, incident_id))
            
            # Update unit status to assigned
            self.update_enhanced_status(incident_id, self.STATUS_ASSIGNED, division_id)
            
            conn.commit()
            logger.info(f"Assigned unit {self.unit_id} to division {division_id}")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Failed to assign unit to division: {e}")
            raise
        finally:
            cursor.close()
            conn.close()

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert unit to dictionary representation

        Returns:
            Dictionary representation of unit
        """
        base_dict = {
            "id": self.id,
            "incident_id": self.incident_id,
            "unit_id": self.unit_id,
            "company_officer": self.company_officer,
            "number_of_personnel": self.number_of_personnel,
            "bsar_tech": self.bsar_tech,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "status": self.status,
            "checked_in_at": (
                self.checked_in_at.isoformat() if self.checked_in_at else None
            ),
            "last_updated": (
                self.last_updated.isoformat() if self.last_updated else None
            ),
            "notes": self.notes,
        }
        
        # Add enhanced status fields if available
        if hasattr(self, 'current_status'):
            base_dict.update({
                "unit_name": self.unit_name,
                "unit_type": self.unit_type, 
                "unit_leader": self.unit_leader,
                "current_status": self.current_status,
                "current_division_id": self.current_division_id
            })
            
        return base_dict

    @staticmethod
    def get_units_for_incident(incident_id: str, db_manager) -> List[Dict[str, Any]]:
        """
        Get all units for a specific incident

        Args:
            incident_id: Incident ID
            db_manager: Database manager instance

        Returns:
            List of unit dictionaries
        """
        try:
            conn = db_manager.connect()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    id, incident_id, unit_id, company_officer, number_of_personnel, 
                    bsar_tech, latitude, longitude, status, checked_in_at, 
                    last_updated, notes
                FROM units 
                WHERE incident_id = %s 
                ORDER BY checked_in_at DESC
            """,
                (incident_id,),
            )

            units = []
            for row in cursor.fetchall():
                unit_data = {
                    "id": row[0],
                    "incident_id": row[1],
                    "unit_id": row[2],
                    "company_officer": row[3],
                    "number_of_personnel": row[4],
                    "bsar_tech": row[5],
                    "latitude": float(row[6]) if row[6] else None,
                    "longitude": float(row[7]) if row[7] else None,
                    "status": row[8],
                    "checked_in_at": row[9],
                    "last_updated": row[10],
                    "notes": row[11],
                }

                # Create Unit instance and convert to dict
                unit = Unit(db_manager, unit_data)
                units.append(unit.to_dict())

            cursor.close()
            conn.close()

            return units

        except Exception as e:
            logger.error(f"Error retrieving units for incident {incident_id}: {e}")
            return []

    @staticmethod
    def get_units_by_incident(incident_id):
        """Get all units for an incident using enhanced status tracking"""
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            cursor.execute("""
                SELECT u.*, sd.division_name 
                FROM units u
                LEFT JOIN search_divisions sd ON u.current_division_id = sd.division_id
                WHERE u.current_incident_id = %s
                ORDER BY u.unit_name
            """, (incident_id,))
            
            return cursor.fetchall()
            
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_unit_status_history(unit_id, incident_id=None):
        """Get status history for a unit"""
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
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
            
        finally:
            cursor.close()
            conn.close()

    @staticmethod
    def get_unit_by_id(unit_id: str, incident_id: str, db_manager) -> Optional["Unit"]:
        """
        Get specific unit by ID and incident

        Args:
            unit_id: Unit ID
            incident_id: Incident ID
            db_manager: Database manager instance

        Returns:
            Unit instance or None
        """
        try:
            conn = db_manager.connect()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT 
                    id, incident_id, unit_id, company_officer, number_of_personnel, 
                    bsar_tech, latitude, longitude, status, checked_in_at, 
                    last_updated, notes
                FROM units 
                WHERE unit_id = %s AND incident_id = %s
            """,
                (unit_id, incident_id),
            )

            row = cursor.fetchone()
            cursor.close()
            conn.close()

            if row:
                unit_data = {
                    "id": row[0],
                    "incident_id": row[1],
                    "unit_id": row[2],
                    "company_officer": row[3],
                    "number_of_personnel": row[4],
                    "bsar_tech": row[5],
                    "latitude": row[6],
                    "longitude": row[7],
                    "status": row[8],
                    "checked_in_at": row[9],
                    "last_updated": row[10],
                    "notes": row[11],
                }

                return Unit(db_manager, unit_data)

            return None

        except Exception as e:
            logger.error(f"Error retrieving unit {unit_id}: {e}")
            return None

    @staticmethod
    def get_unit_count_for_incident(incident_id: str, db_manager) -> int:
        """
        Get count of units for incident

        Args:
            incident_id: Incident ID
            db_manager: Database manager instance

        Returns:
            Number of units checked in
        """
        try:
            conn = db_manager.connect()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT COUNT(*) FROM units WHERE incident_id = %s
            """,
                (incident_id,),
            )

            count = cursor.fetchone()[0]
            cursor.close()
            conn.close()

            return count

        except Exception as e:
            logger.error(f"Error getting unit count for incident {incident_id}: {e}")
            return 0
