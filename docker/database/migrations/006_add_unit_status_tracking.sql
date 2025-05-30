-- Migration: Add unit status tracking
-- Description: Adds units table and updates schema for unit status management
-- Date: 2025-05-30
-- Version: 006_add_unit_status_tracking

BEGIN;

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

-- Add trigger for units updated_at column
DROP TRIGGER IF EXISTS update_units_updated_at ON units;
CREATE TRIGGER update_units_updated_at 
    BEFORE UPDATE ON units
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create indexes for new units table
CREATE INDEX IF NOT EXISTS idx_units_incident ON units(incident_id);
CREATE INDEX IF NOT EXISTS idx_units_unit_id ON units(unit_id);
CREATE INDEX IF NOT EXISTS idx_units_status ON units(unit_status);
CREATE INDEX IF NOT EXISTS idx_units_assigned_division ON units(assigned_division);

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
    units_count INTEGER;
    units_with_status INTEGER;
BEGIN
    -- Check if units table exists and has data
    SELECT COUNT(*) INTO units_count FROM units;
    SELECT COUNT(*) INTO units_with_status FROM units WHERE unit_status IN ('staging', 'assigned', 'operating', 'recovering', 'returned');
    
    RAISE NOTICE 'Migration 006 completed successfully!';
    RAISE NOTICE 'Total units: %', units_count;
    RAISE NOTICE 'Units with valid status: %', units_with_status;
    
    -- Show unit status distribution
    IF units_count > 0 THEN
        RAISE NOTICE 'Unit status distribution:';
        FOR rec IN 
            SELECT unit_status, COUNT(*) as count 
            FROM units 
            GROUP BY unit_status 
            ORDER BY unit_status
        LOOP
            RAISE NOTICE '  %: %', rec.unit_status, rec.count;
        END LOOP;
    END IF;
END $$;
