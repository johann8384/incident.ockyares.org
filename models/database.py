import psycopg2
import psycopg2.extras
import os
from typing import Optional


class DatabaseManager:
    """Handle database connections and operations"""

    def __init__(self):
        self.conn = None
        self.db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
            "database": os.getenv("DB_NAME", "emergency_ops"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "emergency_password"),
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
            updated_at TIMESTAMP DEFAULT NOW(),
            status VARCHAR(50) DEFAULT 'active'
        );
        
        -- Hospitals table
        CREATE TABLE IF NOT EXISTS hospitals (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            trauma_level VARCHAR(100),
            address TEXT,
            city VARCHAR(100),
            state VARCHAR(50),
            telephone VARCHAR(50),
            latitude DECIMAL(10, 8),
            longitude DECIMAL(11, 8),
            hospital_location GEOMETRY(POINT, 4326),
            distance_km DECIMAL(8, 3),
            source_id INTEGER UNIQUE,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        
        -- Incident-Hospital relationship table
        CREATE TABLE IF NOT EXISTS incident_hospitals (
            id SERIAL PRIMARY KEY,
            incident_id VARCHAR(50) REFERENCES incidents(incident_id) ON DELETE CASCADE,
            closest_hospital_id INTEGER REFERENCES hospitals(id),
            level1_hospital_id INTEGER REFERENCES hospitals(id),
            pediatric_hospital_id INTEGER REFERENCES hospitals(id),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(incident_id)
        );
        
        -- Search divisions table
        CREATE TABLE IF NOT EXISTS search_divisions (
            id SERIAL PRIMARY KEY,
            incident_id VARCHAR(50) REFERENCES incidents(incident_id) ON DELETE CASCADE,
            division_name VARCHAR(100) NOT NULL,
            division_id VARCHAR(50),
            area_geometry GEOMETRY(POLYGON, 4326),
            estimated_area_m2 FLOAT,
            assigned_team VARCHAR(255),
            team_leader VARCHAR(255),
            priority INTEGER DEFAULT 1,
            search_type VARCHAR(50) DEFAULT 'primary',
            estimated_duration VARCHAR(50),
            status VARCHAR(50) DEFAULT 'unassigned',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );
        
        -- Search progress/reports table
        CREATE TABLE IF NOT EXISTS search_progress (
            id SERIAL PRIMARY KEY,
            incident_id VARCHAR(50) REFERENCES incidents(incident_id) ON DELETE CASCADE,
            division_id VARCHAR(50),
            user_name VARCHAR(255),
            report_type VARCHAR(100),
            description TEXT,
            photo_path TEXT,
            report_location GEOMETRY(POINT, 4326),
            timestamp TIMESTAMP DEFAULT NOW(),
            status VARCHAR(50)
        );
        
        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_incidents_id ON incidents(incident_id);
        CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
        CREATE INDEX IF NOT EXISTS idx_hospitals_source_id ON hospitals(source_id);
        CREATE INDEX IF NOT EXISTS idx_hospitals_trauma ON hospitals(trauma_level);
        CREATE INDEX IF NOT EXISTS idx_incident_hospitals_incident ON incident_hospitals(incident_id);
        CREATE INDEX IF NOT EXISTS idx_divisions_incident ON search_divisions(incident_id);
        CREATE INDEX IF NOT EXISTS idx_divisions_status ON search_divisions(status);
        CREATE INDEX IF NOT EXISTS idx_progress_incident ON search_progress(incident_id);
        CREATE INDEX IF NOT EXISTS idx_progress_division ON search_progress(division_id);
        
        -- Create spatial indexes
        CREATE INDEX IF NOT EXISTS idx_incidents_location ON incidents USING GIST(incident_location);
        CREATE INDEX IF NOT EXISTS idx_incidents_search_area ON incidents USING GIST(search_area);
        CREATE INDEX IF NOT EXISTS idx_hospitals_location ON hospitals USING GIST(hospital_location);
        CREATE INDEX IF NOT EXISTS idx_divisions_geometry ON search_divisions USING GIST(area_geometry);
        CREATE INDEX IF NOT EXISTS idx_progress_location ON search_progress USING GIST(report_location);
        
        -- Create triggers for updated_at timestamps
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        
        DROP TRIGGER IF EXISTS update_incidents_updated_at ON incidents;
        CREATE TRIGGER update_incidents_updated_at 
            BEFORE UPDATE ON incidents 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            
        DROP TRIGGER IF EXISTS update_hospitals_updated_at ON hospitals;
        CREATE TRIGGER update_hospitals_updated_at 
            BEFORE UPDATE ON hospitals 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            
        DROP TRIGGER IF EXISTS update_incident_hospitals_updated_at ON incident_hospitals;
        CREATE TRIGGER update_incident_hospitals_updated_at 
            BEFORE UPDATE ON incident_hospitals 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
            
        DROP TRIGGER IF EXISTS update_divisions_updated_at ON search_divisions;
        CREATE TRIGGER update_divisions_updated_at 
            BEFORE UPDATE ON search_divisions 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """

        self.execute_query(schema_sql)
