-- Migration to add missing tables and progress tracking

-- Add stage column to incidents if not exists
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS stage VARCHAR(50) DEFAULT 'New';
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS address TEXT;

-- Create units table
CREATE TABLE IF NOT EXISTS units (
    id SERIAL PRIMARY KEY,
    unit_id VARCHAR(100) NOT NULL,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    officer_name VARCHAR(255) NOT NULL,
    personnel_count INTEGER NOT NULL,
    equipment_status VARCHAR(100) NOT NULL,
    unit_status VARCHAR(50) DEFAULT 'staging',
    assigned_division VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(unit_id, incident_id)
);

-- Create unit status updates table
CREATE TABLE IF NOT EXISTS unit_status_updates (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    unit_id VARCHAR(100) NOT NULL,
    officer_name VARCHAR(255) NOT NULL,
    status_change VARCHAR(50) NOT NULL,
    progress_percentage INTEGER,
    need_assistance BOOLEAN DEFAULT FALSE,
    comment TEXT,
    location_point GEOMETRY(POINT, 4326),
    location_source VARCHAR(50),
    update_timestamp TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Add progress percentage to search_divisions
ALTER TABLE search_divisions ADD COLUMN IF NOT EXISTS progress_percentage INTEGER DEFAULT 0;

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_units_incident ON units(incident_id);
CREATE INDEX IF NOT EXISTS idx_units_unit_id ON units(unit_id);
CREATE INDEX IF NOT EXISTS idx_unit_status_updates_incident ON unit_status_updates(incident_id);
CREATE INDEX IF NOT EXISTS idx_unit_status_updates_unit ON unit_status_updates(unit_id);
CREATE INDEX IF NOT EXISTS idx_unit_status_updates_geom ON unit_status_updates USING GIST(location_point);

-- Add triggers for updated_at (drop first if exists)
DROP TRIGGER IF EXISTS update_units_updated_at ON units;
CREATE TRIGGER update_units_updated_at BEFORE UPDATE ON units
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

DROP TRIGGER IF EXISTS update_unit_status_updates_updated_at ON unit_status_updates;
CREATE TRIGGER update_unit_status_updates_updated_at BEFORE UPDATE ON unit_status_updates
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
