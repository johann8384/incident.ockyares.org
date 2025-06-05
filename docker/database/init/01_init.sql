-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE emergency_ops TO postgres;

-- Create application user (optional, for production)
-- CREATE USER incident_app WITH PASSWORD 'app_password';
-- GRANT CONNECT ON DATABASE emergency_ops TO incident_app;
-- GRANT USAGE ON SCHEMA public TO incident_app;
-- GRANT CREATE ON SCHEMA public TO incident_app;

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Incidents table
CREATE TABLE incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    incident_type VARCHAR(100) NOT NULL,
    description TEXT,
    incident_location GEOMETRY(POINT, 4326),
    address TEXT,
    search_area GEOMETRY(POLYGON, 4326),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Search divisions table
CREATE TABLE search_divisions (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    division_id VARCHAR(50) NOT NULL,
    division_name VARCHAR(255) NOT NULL,
    area_geometry GEOMETRY(POLYGON, 4326),
    estimated_area_m2 DECIMAL(12,2),
    assigned_team VARCHAR(255),
    team_leader VARCHAR(255),
    assigned_unit_id VARCHAR(50),
    priority INTEGER DEFAULT 1,
    search_type VARCHAR(50) DEFAULT 'primary',
    estimated_duration VARCHAR(50),
    status VARCHAR(50) DEFAULT 'unassigned',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Search progress table (for field reports)
CREATE TABLE search_progress (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    division_id VARCHAR(50),
    user_name VARCHAR(255),
    report_type VARCHAR(100),
    description TEXT,
    photo_path TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50),
    location GEOMETRY(POINT, 4326)
);

-- Hospitals and incident-hospital relationship tables
CREATE TABLE hospitals (
    id SERIAL PRIMARY KEY,
    facility_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    city VARCHAR(100),
    county VARCHAR(100),
    zip_code VARCHAR(10),
    phone VARCHAR(20),
    license_type VARCHAR(50),
    latitude DECIMAL(10,7),
    longitude DECIMAL(10,7),
    hospital_location GEOMETRY(POINT, 4326),
    distance_km DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE incident_hospitals (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id) UNIQUE,
    closest_hospital_id INTEGER REFERENCES hospitals(id),
    level1_hospital_id INTEGER REFERENCES hospitals(id),
    pediatric_hospital_id INTEGER REFERENCES hospitals(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Units table for tracking responding resources (SINGLE TABLE)
CREATE TABLE units (
    id SERIAL PRIMARY KEY,
    unit_id VARCHAR(50) UNIQUE NOT NULL,
    unit_name VARCHAR(255) NOT NULL,
    unit_type VARCHAR(100) NOT NULL, -- Engine, Truck, Rescue, Command, etc.
    unit_leader VARCHAR(255),
    contact_info VARCHAR(255),
    number_of_personnel INTEGER,
    bsar_tech BOOLEAN DEFAULT FALSE,
    current_status VARCHAR(50) DEFAULT 'quarters',
    current_incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    current_division_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Unit status history for tracking all status changes (including checkins)
CREATE TABLE unit_status_history (
    id SERIAL PRIMARY KEY,
    unit_id VARCHAR(50) REFERENCES units(unit_id),
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    division_id VARCHAR(50),
    status VARCHAR(50) NOT NULL,
    percentage_complete INTEGER DEFAULT 0,
    location GEOMETRY(POINT, 4326),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    notes TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),
    user_name VARCHAR(255)
);

-- Add foreign key references
ALTER TABLE search_divisions 
ADD CONSTRAINT fk_search_divisions_unit 
FOREIGN KEY (assigned_unit_id) REFERENCES units(unit_id);

-- Create indexes
CREATE INDEX idx_incidents_id ON incidents(incident_id);
CREATE INDEX idx_search_divisions_incident ON search_divisions(incident_id);
CREATE INDEX idx_search_progress_incident ON search_progress(incident_id);
CREATE INDEX idx_search_progress_division ON search_progress(division_id);
CREATE INDEX idx_hospitals_facility_id ON hospitals(facility_id);
CREATE INDEX idx_incident_hospitals_incident ON incident_hospitals(incident_id);
CREATE INDEX idx_units_unit_id ON units(unit_id);
CREATE INDEX idx_units_incident ON units(current_incident_id);
CREATE INDEX idx_unit_status_unit ON unit_status_history(unit_id);
CREATE INDEX idx_unit_status_incident ON unit_status_history(incident_id);
CREATE INDEX idx_unit_status_timestamp ON unit_status_history(timestamp);
CREATE INDEX idx_search_divisions_unit ON search_divisions(assigned_unit_id);

-- Create spatial indexes
CREATE INDEX idx_incidents_location ON incidents USING GIST(incident_location);
CREATE INDEX idx_incidents_search_area ON incidents USING GIST(search_area);
CREATE INDEX idx_search_divisions_geom ON search_divisions USING GIST(area_geometry);
CREATE INDEX idx_search_progress_geom ON search_progress USING GIST(location);
CREATE INDEX idx_hospitals_geom ON hospitals USING GIST(hospital_location);
CREATE INDEX idx_unit_status_location ON unit_status_history USING GIST(location);

-- Create trigger for automatic geometry updates in status history
CREATE OR REPLACE FUNCTION update_status_geometry()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.location = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_status_geometry_trigger
    BEFORE INSERT OR UPDATE ON unit_status_history
    FOR EACH ROW EXECUTE FUNCTION update_status_geometry();

-- Create triggers for updated_at columns
CREATE TRIGGER update_incidents_updated_at 
    BEFORE UPDATE ON incidents 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_search_divisions_updated_at 
    BEFORE UPDATE ON search_divisions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_hospitals_updated_at 
    BEFORE UPDATE ON hospitals 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_incident_hospitals_updated_at 
    BEFORE UPDATE ON incident_hospitals 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
