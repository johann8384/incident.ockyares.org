-- Emergency Incident Management System Database Schema
-- Initialize with PostGIS for spatial data support

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Drop existing tables if they exist (for clean initialization)
DROP TABLE IF EXISTS search_progress CASCADE;
DROP TABLE IF EXISTS search_divisions CASCADE;
DROP TABLE IF EXISTS incident_hospitals CASCADE;
DROP TABLE IF EXISTS hospitals CASCADE;
DROP TABLE IF EXISTS incidents CASCADE;

-- Drop existing functions and triggers
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- Create main incidents table
CREATE TABLE incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    incident_type VARCHAR(100) NOT NULL,
    description TEXT,
    incident_location GEOMETRY(POINT, 4326),
    address TEXT,
    search_area GEOMETRY(POLYGON, 4326),
    search_area_coordinates JSONB, -- Store original coordinates for frontend
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'active'
);

-- Create hospitals table (structure based on Kentucky hospital data)
CREATE TABLE hospitals (
    id SERIAL PRIMARY KEY,
    facility_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    city VARCHAR(100),
    county VARCHAR(100),
    state VARCHAR(50) DEFAULT 'KY',
    zip_code VARCHAR(20),
    phone VARCHAR(50),
    license_type VARCHAR(100),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    hospital_location GEOMETRY(POINT, 4326),
    distance_km DECIMAL(8, 3),
    trauma_level VARCHAR(20), -- Level 1, Level 2, etc.
    pediatric_capable BOOLEAN DEFAULT FALSE,
    emergency_services BOOLEAN DEFAULT TRUE,
    bed_count INTEGER,
    specialty_services TEXT[], -- Array of specialty services
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create incident-hospital relationship table
CREATE TABLE incident_hospitals (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id) ON DELETE CASCADE,
    hospital_data JSONB NOT NULL, -- Store complete hospital data as JSON
    closest_hospital_id INTEGER REFERENCES hospitals(id),
    level1_trauma_id INTEGER REFERENCES hospitals(id),
    level1_pediatric_id INTEGER REFERENCES hospitals(id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(incident_id)
);

-- Create search divisions table
CREATE TABLE search_divisions (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id) ON DELETE CASCADE,
    division_name VARCHAR(100) NOT NULL,
    division_id VARCHAR(50) NOT NULL,
    area_geometry GEOMETRY(POLYGON, 4326),
    area_coordinates JSONB, -- Store original coordinates for frontend
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

-- Create search progress/reports table for field updates
CREATE TABLE search_progress (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id) ON DELETE CASCADE,
    division_id VARCHAR(50),
    user_name VARCHAR(255),
    team_name VARCHAR(255),
    report_type VARCHAR(100),
    description TEXT,
    photo_path TEXT,
    report_location GEOMETRY(POINT, 4326),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    timestamp TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50),
    metadata JSONB -- Additional field data
);

-- Create indexes for performance

-- Basic indexes
CREATE INDEX idx_incidents_id ON incidents(incident_id);
CREATE INDEX idx_incidents_status ON incidents(status);
CREATE INDEX idx_incidents_type ON incidents(incident_type);

CREATE INDEX idx_hospitals_facility_id ON hospitals(facility_id);
CREATE INDEX idx_hospitals_license_type ON hospitals(license_type);
CREATE INDEX idx_hospitals_trauma_level ON hospitals(trauma_level);
CREATE INDEX idx_hospitals_city ON hospitals(city);
CREATE INDEX idx_hospitals_county ON hospitals(county);

CREATE INDEX idx_incident_hospitals_incident ON incident_hospitals(incident_id);

CREATE INDEX idx_divisions_incident ON search_divisions(incident_id);
CREATE INDEX idx_divisions_id ON search_divisions(division_id);
CREATE INDEX idx_divisions_status ON search_divisions(status);
CREATE INDEX idx_divisions_team ON search_divisions(assigned_team);

CREATE INDEX idx_progress_incident ON search_progress(incident_id);
CREATE INDEX idx_progress_division ON search_progress(division_id);
CREATE INDEX idx_progress_team ON search_progress(team_name);
CREATE INDEX idx_progress_timestamp ON search_progress(timestamp);

-- Spatial indexes for geographic queries
CREATE INDEX idx_incidents_location ON incidents USING GIST(incident_location);
CREATE INDEX idx_incidents_search_area ON incidents USING GIST(search_area);
CREATE INDEX idx_hospitals_location ON hospitals USING GIST(hospital_location);
CREATE INDEX idx_divisions_geometry ON search_divisions USING GIST(area_geometry);
CREATE INDEX idx_progress_location ON search_progress USING GIST(report_location);

-- JSON indexes for hospital data
CREATE INDEX idx_incident_hospitals_data ON incident_hospitals USING GIN(hospital_data);
CREATE INDEX idx_divisions_coordinates ON search_divisions USING GIN(area_coordinates);
CREATE INDEX idx_progress_metadata ON search_progress USING GIN(metadata);

-- Create function for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at timestamps
CREATE TRIGGER update_incidents_updated_at 
    BEFORE UPDATE ON incidents 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_hospitals_updated_at 
    BEFORE UPDATE ON hospitals 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_incident_hospitals_updated_at 
    BEFORE UPDATE ON incident_hospitals 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_divisions_updated_at 
    BEFORE UPDATE ON search_divisions 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create function to automatically update geometry from coordinates
CREATE OR REPLACE FUNCTION update_hospital_geometry()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.hospital_location = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for hospital geometry updates
CREATE TRIGGER update_hospital_geometry_trigger
    BEFORE INSERT OR UPDATE ON hospitals
    FOR EACH ROW EXECUTE FUNCTION update_hospital_geometry();

-- Create function to automatically update progress report geometry
CREATE OR REPLACE FUNCTION update_progress_geometry()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.report_location = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for progress report geometry updates
CREATE TRIGGER update_progress_geometry_trigger
    BEFORE INSERT OR UPDATE ON search_progress
    FOR EACH ROW EXECUTE FUNCTION update_progress_geometry();

-- Insert sample data for testing (optional - remove in production)
-- Sample hospitals data for Louisville area
INSERT INTO hospitals (facility_id, name, address, city, county, state, zip_code, phone, license_type, latitude, longitude, trauma_level, pediatric_capable, emergency_services, bed_count) VALUES
('KY001', 'University of Louisville Hospital', '530 S Jackson St', 'Louisville', 'Jefferson', 'KY', '40202', '(502) 562-3000', 'Hospital', 38.2341, -85.7547, 'Level 1', true, true, 404),
('KY002', 'Norton Hospital', '200 E Chestnut St', 'Louisville', 'Jefferson', 'KY', '40202', '(502) 629-8000', 'Hospital', 38.2498, -85.7547, 'Level 2', false, true, 382),
('KY003', 'Baptist Health Louisville', '4000 Kresge Way', 'Louisville', 'Jefferson', 'KY', '40207', '(502) 897-8100', 'Hospital', 38.2416, -85.6758, 'Level 2', false, true, 519),
('KY004', 'Jewish Hospital', '200 Abraham Flexner Way', 'Louisville', 'Jefferson', 'KY', '40202', '(502) 587-4011', 'Hospital', 38.2498, -85.7547, 'Level 2', false, true, 267),
('KY005', 'Kosair Childrens Hospital', '231 E Chestnut St', 'Louisville', 'Jefferson', 'KY', '40202', '(502) 629-6000', 'Hospital', 38.2498, -85.7547, 'Level 1 Pediatric', true, true, 267)
ON CONFLICT (facility_id) DO NOTHING;

-- Create views for common queries

-- View for active incidents with location data
CREATE OR REPLACE VIEW active_incidents AS
SELECT 
    incident_id,
    name,
    incident_type,
    description,
    address,
    ST_X(incident_location) as longitude,
    ST_Y(incident_location) as latitude,
    ST_AsGeoJSON(search_area) as search_area_geojson,
    search_area_coordinates,
    created_at,
    updated_at,
    status
FROM incidents
WHERE status = 'active';

-- View for incident divisions with geometry
CREATE OR REPLACE VIEW incident_divisions AS
SELECT 
    sd.incident_id,
    sd.division_name,
    sd.division_id,
    sd.estimated_area_m2,
    sd.assigned_team,
    sd.team_leader,
    sd.priority,
    sd.search_type,
    sd.estimated_duration,
    sd.status,
    ST_AsGeoJSON(sd.area_geometry) as geometry_geojson,
    sd.area_coordinates,
    sd.created_at,
    sd.updated_at,
    i.name as incident_name
FROM search_divisions sd
JOIN incidents i ON sd.incident_id = i.incident_id;

-- View for nearby hospitals
CREATE OR REPLACE VIEW hospital_summary AS
SELECT 
    facility_id,
    name,
    address,
    city,
    county,
    phone,
    license_type,
    latitude,
    longitude,
    trauma_level,
    pediatric_capable,
    emergency_services,
    bed_count
FROM hospitals
ORDER BY name;

-- Grant permissions (adjust as needed for your security requirements)
-- For development - in production, create specific roles with limited permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO postgres;

-- Create a read-only role for reporting/API access
CREATE ROLE incident_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO incident_reader;
GRANT USAGE ON SCHEMA public TO incident_reader;

-- Create an API role with insert/update permissions
CREATE ROLE incident_api;
GRANT SELECT, INSERT, UPDATE ON incidents, hospitals, incident_hospitals, search_divisions, search_progress TO incident_api;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO incident_api;
GRANT USAGE ON SCHEMA public TO incident_api;

-- Comments for documentation
COMMENT ON TABLE incidents IS 'Primary incidents table storing emergency incident information';
COMMENT ON TABLE hospitals IS 'Hospital facilities with location and capability data';
COMMENT ON TABLE incident_hospitals IS 'Links incidents to relevant hospital data';
COMMENT ON TABLE search_divisions IS 'Search area divisions for team assignment';
COMMENT ON TABLE search_progress IS 'Field reports and progress updates from search teams';

COMMENT ON COLUMN incidents.incident_location IS 'PostGIS point geometry for incident location';
COMMENT ON COLUMN incidents.search_area IS 'PostGIS polygon geometry for search area';
COMMENT ON COLUMN incidents.search_area_coordinates IS 'Original coordinate array for frontend use';
COMMENT ON COLUMN hospitals.hospital_location IS 'PostGIS point geometry for hospital location';
COMMENT ON COLUMN incident_hospitals.hospital_data IS 'Complete hospital data as JSON for incident context';
COMMENT ON COLUMN search_divisions.area_geometry IS 'PostGIS polygon geometry for division area';
COMMENT ON COLUMN search_divisions.area_coordinates IS 'Original coordinate array for frontend use';

-- Show completion message
DO $$
BEGIN
    RAISE NOTICE 'Emergency Incident Management System database schema created successfully';
    RAISE NOTICE 'Tables created: incidents, hospitals, incident_hospitals, search_divisions, search_progress';
    RAISE NOTICE 'Indexes, triggers, and views created';
    RAISE NOTICE 'Sample hospital data inserted for Louisville area';
END $$;
