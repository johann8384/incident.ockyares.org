import psycopg2
import psycopg2.extras
from datetime import datetime
import logging
import os

# Use same DB config as main app
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'postgis'),
    'port': os.getenv('DB_PORT', '5432'),
    'database': os.getenv('DB_NAME', 'emergency_ops'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'emergency_password')
}

class Unit:
    """Unit model for tracking responding resources"""
    
    # Unit status constants
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
    
    def __init__(self, unit_id=None, unit_name=None, unit_type=None, unit_leader=None):
        self.unit_id = unit_id
        self.unit_name = unit_name
        self.unit_type = unit_type
        self.unit_leader = unit_leader
        self.current_status = self.STATUS_QUARTERS
        self.current_incident_id = None
        self.current_division_id = None
        
    def connect_db(self):
        """Get database connection"""
        try:
            return psycopg2.connect(**DB_CONFIG)
        except Exception as e:
            logging.error(f"Database connection failed: {e}")
            raise
    
    def create_unit(self, contact_info=None):
        """Create new unit in database"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO units (unit_id, unit_name, unit_type, unit_leader, contact_info)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
            """, (self.unit_id, self.unit_name, self.unit_type, self.unit_leader, contact_info))
            
            unit_db_id = cursor.fetchone()[0]
            conn.commit()
            logging.info(f"Created unit: {self.unit_id}")
            return unit_db_id
            
        except Exception as e:
            conn.rollback()
            logging.error(f"Failed to create unit: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def update_status(self, incident_id, new_status, division_id=None, percentage_complete=0, 
                     latitude=None, longitude=None, notes=None, user_name=None):
        """Update unit status and log to history"""
        
        if new_status not in self.VALID_STATUSES:
            raise ValueError(f"Invalid status: {new_status}")
            
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            # Update current status in units table
            cursor.execute("""
                UPDATE units 
                SET current_status = %s, current_incident_id = %s, current_division_id = %s
                WHERE unit_id = %s
            """, (new_status, incident_id, division_id, self.unit_id))
            
            # Log to status history
            location_wkt = None
            if latitude is not None and longitude is not None:
                location_wkt = f"POINT({longitude} {latitude})"
            
            cursor.execute("""
                INSERT INTO unit_status_history 
                (unit_id, incident_id, division_id, status, percentage_complete, 
                 location, notes, user_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (self.unit_id, incident_id, division_id, new_status, percentage_complete,
                  f"ST_GeomFromText('{location_wkt}', 4326)" if location_wkt else None,
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
            logging.info(f"Updated unit {self.unit_id} status to {new_status}")
            
        except Exception as e:
            conn.rollback()
            logging.error(f"Failed to update unit status: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    def assign_to_division(self, incident_id, division_id):
        """Assign unit to a search division"""
        conn = self.connect_db()
        cursor = conn.cursor()
        
        try:
            # Update division assignment
            cursor.execute("""
                UPDATE search_divisions 
                SET assigned_unit_id = %s 
                WHERE division_id = %s AND incident_id = %s
            """, (self.unit_id, division_id, incident_id))
            
            # Update unit status to assigned
            self.update_status(incident_id, self.STATUS_ASSIGNED, division_id)
            
            conn.commit()
            logging.info(f"Assigned unit {self.unit_id} to division {division_id}")
            
        except Exception as e:
            conn.rollback()
            logging.error(f"Failed to assign unit to division: {e}")
            raise
        finally:
            cursor.close()
            conn.close()
    
    @staticmethod
    def get_units_by_incident(incident_id):
        """Get all units for an incident"""
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
