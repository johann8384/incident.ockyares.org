import psycopg2
import psycopg2.extras
import os
from typing import Optional

class DatabaseManager:
    """Handle database connections and operations"""
    
    def __init__(self):
        self.conn = None
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'emergency_ops'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'emergency_password')
        }
    
    def connect(self) -> psycopg2.extensions.connection:
        """Create database connection"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            return self.conn
        except Exception as e:
            print(f"Database connection failed: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = False):
        """Execute a query with optional parameters"""
        cursor = None
        try:
            if not self.conn:
                self.connect()
            
            cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute(query, params)
            
            if fetch:
                result = cursor.fetchall()
                return result
            else:
                self.conn.commit()
                return cursor.rowcount
                
        except Exception as e:
            if self.conn:
                self.conn.rollback()
            print(f"Query execution failed: {e}")
            raise
        finally:
            if cursor:
                cursor.close()
    
    def create_tables(self):
        """Create initial database schema"""
        schema_sql = """
        -- Enable PostGIS extension
        CREATE EXTENSION IF NOT EXISTS postgis;
        
        -- Incidents table
        CREATE TABLE IF NOT EXISTS incidents (
            id SERIAL PRIMARY KEY,
            incident_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            incident_type VARCHAR(100) NOT NULL,
            description TEXT,
            incident_location GEOMETRY(POINT, 4326),
            address TEXT,
            search_area GEOMETRY(POLYGON, 4326),
            created_at TIMESTAMP DEFAULT NOW(),
            status VARCHAR(50) DEFAULT 'active'
        );
        
        -- Search divisions table
        CREATE TABLE IF NOT EXISTS search_divisions (
            id SERIAL PRIMARY KEY,
            incident_id VARCHAR(50) REFERENCES incidents(incident_id),
            division_name VARCHAR(100) NOT NULL,
            area_geometry GEOMETRY(POLYGON, 4326),
            estimated_area_m2 FLOAT,
            assigned_team VARCHAR(255),
            status VARCHAR(50) DEFAULT 'unassigned',
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        -- Create spatial indexes
        CREATE INDEX IF NOT EXISTS idx_incidents_location ON incidents USING GIST(incident_location);
        CREATE INDEX IF NOT EXISTS idx_incidents_search_area ON incidents USING GIST(search_area);
        CREATE INDEX IF NOT EXISTS idx_divisions_geometry ON search_divisions USING GIST(area_geometry);
        """
        
        self.execute_query(schema_sql)