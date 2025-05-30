-- Migration: Add unit status tracking
-- Description: Adds units table and updates schema for unit status management
-- Date: 2025-05-30
-- Version: 001_add_unit_status_tracking

BEGIN;

-- Add updated_at column to incidents table if it doesn't exist
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'incidents' AND column_name = 'updated_at') THEN
        ALTER TABLE incidents ADD COLUMN updated_at TIMESTAMP DEFAULT NOW();
    END IF;
END $$;

-- Update incidents table: change 'status' column to 'stage' if it exists
DO $$ 
BEGIN 
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'incidents' AND column_name = 'status') THEN
        ALTER TABLE incidents RENAME COLUMN status TO stage;
    END IF;
END $$;

-- Create units table for tracking unit status
CREATE TABLE IF NOT EXISTS units (
    id SERIAL PRIMARY KEY,
    unit_id VARCHAR(50) NOT NULL,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    officer_name VARCHAR(255) NOT NULL,
    personnel_count INTEGER DEFAULT 1,
    equipment_status VARCHAR(50) DEFAULT 'Operational',
    unit_status VARCHAR(50) DEFAULT 'staging',
    assigned_division VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(unit_id, incident_id)
);

-- Create unit_checkins table if it doesn't exist (rename from existing if needed)
CREATE TABLE IF NOT EXISTS unit_checkins (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    unit_id VARCHAR(50) NOT NULL,
    officer_name VARCHAR(255),
    personnel_count INTEGER,
    equipment_status VARCHAR(50),
    location_point GEOMETRY(POINT, 4326),
    photo_path TEXT,
    checkin_time TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add triggers for updated_at columns
DROP TRIGGER IF EXISTS update_incidents_updated_at ON incidents;
CREATE TRIGGER update_incidents_updated_at 
    BEFORE UPDATE ON incidents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_units_updated_at ON units;
CREATE TRIGGER update_units_updated_at 
    BEFORE UPDATE ON units
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_unit_checkins_updated_at ON unit_checkins;
CREATE TRIGGER update_unit_checkins_updated_at 
    BEFORE UPDATE ON unit_checkins
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create indexes for new tables
CREATE INDEX IF NOT EXISTS idx_units_incident ON units(incident_id);
CREATE INDEX IF NOT EXISTS idx_units_unit_id ON units(unit_id);
CREATE INDEX IF NOT EXISTS idx_unit_checkins_incident ON unit_checkins(incident_id);
CREATE INDEX IF NOT EXISTS idx_unit_checkins_unit ON unit_checkins(unit_id);
CREATE INDEX IF NOT EXISTS idx_unit_checkins_geom ON unit_checkins USING GIST(location_point);

-- Migrate existing data if needed
-- If there are existing unit check-ins, create corresponding unit records
INSERT INTO units (unit_id, incident_id, officer_name, personnel_count, equipment_status, unit_status, created_at)
SELECT DISTINCT 
    uc.unit_id,
    uc.incident_id,
    uc.officer_name,
    uc.personnel_count,
    uc.equipment_status,
    'staging' as unit_status,
    MIN(uc.checkin_time) as created_at
FROM unit_checkins uc
WHERE NOT EXISTS (
    SELECT 1 FROM units u 
    WHERE u.unit_id = uc.unit_id AND u.incident_id = uc.incident_id
)
GROUP BY uc.unit_id, uc.incident_id, uc.officer_name, uc.personnel_count, uc.equipment_status
ON CONFLICT (unit_id, incident_id) DO NOTHING;

-- Update units that are assigned to divisions
UPDATE units 
SET unit_status = 'assigned', assigned_division = sd.division_id
FROM search_divisions sd
WHERE sd.assigned_team = units.unit_id 
  AND sd.incident_id = units.incident_id
  AND units.unit_status = 'staging';

COMMIT;

-- Verify migration
DO $$
DECLARE
    table_count INTEGER;
    trigger_count INTEGER;
BEGIN
    -- Check if all tables exist
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables 
    WHERE table_name IN ('units', 'unit_checkins', 'incidents', 'search_divisions', 'search_areas', 'search_progress');
    
    -- Check if triggers exist
    SELECT COUNT(*) INTO trigger_count
    FROM information_schema.triggers 
    WHERE trigger_name IN ('update_incidents_updated_at', 'update_units_updated_at', 'update_unit_checkins_updated_at');
    
    RAISE NOTICE 'Migration completed successfully!';
    RAISE NOTICE 'Tables found: %', table_count;
    RAISE NOTICE 'Triggers created: %', trigger_count;
    
    -- Show unit status distribution
    RAISE NOTICE 'Unit status distribution:';
    FOR rec IN 
        SELECT unit_status, COUNT(*) as count 
        FROM units 
        GROUP BY unit_status 
        ORDER BY unit_status
    LOOP
        RAISE NOTICE '  %: %', rec.unit_status, rec.count;
    END LOOP;
END $$;
