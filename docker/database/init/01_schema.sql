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
    created_at TIMESTAMP DEFAULT NOW()
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
    created_at TIMESTAMP DEFAULT NOW()
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

-- Create indexes
CREATE INDEX idx_incidents_id ON incidents(incident_id);
CREATE INDEX idx_search_areas_incident ON search_areas(incident_id);
CREATE INDEX idx_search_divisions_incident ON search_divisions(incident_id);
CREATE INDEX idx_search_progress_incident ON search_progress(incident_id);
CREATE INDEX idx_search_progress_division ON search_progress(division_id);

-- Create spatial indexes
CREATE INDEX idx_incidents_geom ON incidents USING GIST(center_point);
CREATE INDEX idx_search_areas_geom ON search_areas USING GIST(geom);
CREATE INDEX idx_search_divisions_geom ON search_divisions USING GIST(geom);
CREATE INDEX idx_search_progress_geom ON search_progress USING GIST(geom);
