-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Create schemas
CREATE SCHEMA IF NOT EXISTS public;

-- Incidents table
CREATE TABLE incidents (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) UNIQUE NOT NULL,
    incident_name VARCHAR(255) NOT NULL,
    incident_type VARCHAR(100) NOT NULL,
    ic_name VARCHAR(255) NOT NULL,
    start_time TIMESTAMP DEFAULT NOW(),
    end_time TIMESTAMP,
    status VARCHAR(50) DEFAULT 'active',
    center_point GEOMETRY(POINT, 4326),
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Search areas table
CREATE TABLE search_areas (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    area_name VARCHAR(255) NOT NULL,
    area_type VARCHAR(50) NOT NULL,
    priority INTEGER DEFAULT 1,
    geom GEOMETRY(POLYGON, 4326),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Search divisions table
CREATE TABLE search_divisions (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    division_id VARCHAR(50) NOT NULL,
    division_name VARCHAR(255) NOT NULL,
    assigned_team VARCHAR(255),
    team_leader VARCHAR(255),
    priority INTEGER DEFAULT 1,
    search_type VARCHAR(50) DEFAULT 'primary',
    estimated_duration VARCHAR(50),
    status VARCHAR(50) DEFAULT 'unassigned',
    geom GEOMETRY(POLYGON, 4326),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Search progress table
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
    geom GEOMETRY(POINT, 4326)
);

-- Unit check-ins table
CREATE TABLE unit_checkins (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    unit_id VARCHAR(100) NOT NULL,
    officer_name VARCHAR(255) NOT NULL,
    personnel_count INTEGER NOT NULL,
    equipment_status VARCHAR(100) NOT NULL,
    location_point GEOMETRY(POINT, 4326),
    photo_path TEXT,
    checkin_time TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_incidents_id ON incidents(incident_id);
CREATE INDEX idx_search_areas_incident ON search_areas(incident_id);
CREATE INDEX idx_search_divisions_incident ON search_divisions(incident_id);
CREATE INDEX idx_search_progress_incident ON search_progress(incident_id);
CREATE INDEX idx_search_progress_division ON search_progress(division_id);
CREATE INDEX idx_unit_checkins_incident ON unit_checkins(incident_id);
CREATE INDEX idx_unit_checkins_unit ON unit_checkins(unit_id);

-- Create spatial indexes
CREATE INDEX idx_incidents_geom ON incidents USING GIST(center_point);
CREATE INDEX idx_search_areas_geom ON search_areas USING GIST(geom);
CREATE INDEX idx_search_divisions_geom ON search_divisions USING GIST(geom);
CREATE INDEX idx_search_progress_geom ON search_progress USING GIST(geom);
CREATE INDEX idx_unit_checkins_geom ON unit_checkins USING GIST(location_point);

-- Add updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at
CREATE TRIGGER update_incidents_updated_at BEFORE UPDATE ON incidents
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_search_divisions_updated_at BEFORE UPDATE ON search_divisions
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

CREATE TRIGGER update_unit_checkins_updated_at BEFORE UPDATE ON unit_checkins
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
