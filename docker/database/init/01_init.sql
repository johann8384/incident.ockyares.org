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