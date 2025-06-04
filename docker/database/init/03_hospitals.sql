-- Hospitals and incident-hospital relationship tables
CREATE TABLE hospitals (
    id SERIAL PRIMARY KEY,
    facility_id VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    phone VARCHAR(20),
    location GEOMETRY(POINT, 4326),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE incident_hospitals (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    facility_id VARCHAR(50) REFERENCES hospitals(facility_id),
    distance_km DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(incident_id, facility_id)
);

-- Create indexes
CREATE INDEX idx_hospitals_facility_id ON hospitals(facility_id);
CREATE INDEX idx_hospitals_geom ON hospitals USING GIST(location);
CREATE INDEX idx_incident_hospitals_incident ON incident_hospitals(incident_id);
CREATE INDEX idx_incident_hospitals_facility ON incident_hospitals(facility_id);
