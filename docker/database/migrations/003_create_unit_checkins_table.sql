-- Migration script to create the missing unit_checkins table
-- Run this if your database doesn't have the unit_checkins table

-- Create unit_checkins table if it doesn't exist
CREATE TABLE IF NOT EXISTS unit_checkins (
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

-- Create indexes for unit_checkins table
CREATE INDEX IF NOT EXISTS idx_unit_checkins_incident ON unit_checkins(incident_id);
CREATE INDEX IF NOT EXISTS idx_unit_checkins_unit ON unit_checkins(unit_id);
CREATE INDEX IF NOT EXISTS idx_unit_checkins_geom ON unit_checkins USING GIST(location_point);

-- Create the trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add trigger for unit_checkins table
DROP TRIGGER IF EXISTS update_unit_checkins_updated_at ON unit_checkins;
CREATE TRIGGER update_unit_checkins_updated_at 
    BEFORE UPDATE ON unit_checkins
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();

-- Verify table was created
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns 
WHERE table_name = 'unit_checkins'
ORDER BY ordinal_position;

-- Show the trigger
SELECT 
    trigger_name,
    event_object_table,
    action_timing,
    event_manipulation
FROM information_schema.triggers 
WHERE event_object_table = 'unit_checkins';

-- Confirm table exists with a simple count
SELECT 'unit_checkins table created successfully' as status, COUNT(*) as row_count FROM unit_checkins;
