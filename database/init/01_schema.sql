-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Create role for PostgREST
CREATE ROLE web_anon NOLOGIN;
CREATE ROLE authenticator NOINHERIT LOGIN PASSWORD 'auth_password';
GRANT web_anon TO authenticator;

-- Basic incidents table
CREATE TABLE incidents (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    location GEOMETRY(POINT, 4326),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Grant permissions
GRANT USAGE ON SCHEMA public TO web_anon;
GRANT SELECT, INSERT, UPDATE, DELETE ON incidents TO web_anon;
GRANT USAGE, SELECT ON SEQUENCE incidents_id_seq TO web_anon;

-- Create indexes
CREATE INDEX idx_incidents_location ON incidents USING GIST(location);
CREATE INDEX idx_incidents_created_at ON incidents(created_at);

-- Insert sample data
INSERT INTO incidents (name, description, location) VALUES 
('Sample Incident', 'This is a test incident', ST_SetSRID(ST_MakePoint(-84.27277, 37.839333), 4326)),
('Emergency Response', 'Test emergency response', ST_SetSRID(ST_MakePoint(-84.50018, 38.197274), 4326));
