-- Units table for unit checkin and tracking
CREATE TABLE IF NOT EXISTS units (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id) ON DELETE CASCADE,
    unit_id VARCHAR(100) NOT NULL,
    company_officer VARCHAR(255) NOT NULL,
    number_of_personnel INTEGER NOT NULL,
    bsar_tech BOOLEAN DEFAULT FALSE,
    current_location GEOMETRY(POINT, 4326),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    status VARCHAR(50) DEFAULT 'checked_in',
    checked_in_at TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    UNIQUE(incident_id, unit_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_units_incident ON units(incident_id);
CREATE INDEX IF NOT EXISTS idx_units_unit_id ON units(unit_id);
CREATE INDEX IF NOT EXISTS idx_units_status ON units(status);
CREATE INDEX IF NOT EXISTS idx_units_location ON units USING GIST(current_location);

-- Create trigger for automatic geometry updates
CREATE OR REPLACE FUNCTION update_unit_geometry()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.latitude IS NOT NULL AND NEW.longitude IS NOT NULL THEN
        NEW.current_location = ST_SetSRID(ST_MakePoint(NEW.longitude, NEW.latitude), 4326);
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_unit_geometry_trigger
    BEFORE INSERT OR UPDATE ON units
    FOR EACH ROW EXECUTE FUNCTION update_unit_geometry();

-- Create trigger for last_updated timestamp
CREATE TRIGGER update_units_updated_at 
    BEFORE UPDATE ON units 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Grant permissions
GRANT SELECT, INSERT, UPDATE ON units TO incident_api;
GRANT USAGE, SELECT ON SEQUENCE units_id_seq TO incident_api;

COMMENT ON TABLE units IS 'Units checked into incidents with location and status tracking';
