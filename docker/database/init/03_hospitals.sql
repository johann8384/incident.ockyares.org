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

-- Create indexes
CREATE INDEX idx_hospitals_facility_id ON hospitals(facility_id);
CREATE INDEX idx_hospitals_geom ON hospitals USING GIST(hospital_location);
CREATE INDEX idx_incident_hospitals_incident ON incident_hospitals(incident_id);
