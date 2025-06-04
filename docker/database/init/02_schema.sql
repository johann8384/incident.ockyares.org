-- Create main incident management tables
CREATE SCHEMA IF NOT EXISTS public;

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

-- Create indexes
CREATE INDEX idx_incidents_id ON incidents(incident_id);
CREATE INDEX idx_search_divisions_incident ON search_divisions(incident_id);
CREATE INDEX idx_search_progress_incident ON search_progress(incident_id);
CREATE INDEX idx_search_progress_division ON search_progress(division_id);

-- Create spatial indexes
CREATE INDEX idx_incidents_location ON incidents USING GIST(incident_location);
CREATE INDEX idx_incidents_search_area ON incidents USING GIST(search_area);
CREATE INDEX idx_search_divisions_geom ON search_divisions USING GIST(area_geometry);
CREATE INDEX idx_search_progress_geom ON search_progress USING GIST(location);
