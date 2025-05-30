-- Migration: Add unit status updates table
-- Description: Adds table to track unit status updates with location, progress, and assistance needs
-- Date: 2025-05-30
-- Version: 008_add_unit_status_updates

BEGIN;

-- Create unit_status_updates table
CREATE TABLE IF NOT EXISTS unit_status_updates (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    unit_id VARCHAR(50) NOT NULL,
    officer_name VARCHAR(255) NOT NULL,
    status_change VARCHAR(50) NOT NULL,
    progress_percentage INTEGER DEFAULT NULL CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    need_assistance BOOLEAN DEFAULT FALSE,
    comment TEXT,
    location_point GEOMETRY(POINT, 4326),
    location_source VARCHAR(20) DEFAULT 'manual' CHECK (location_source IN ('manual', 'gps', 'map_click')),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (unit_id, incident_id) REFERENCES units(unit_id, incident_id)
);

-- Add trigger for unit_status_updates updated_at column
DROP TRIGGER IF EXISTS update_unit_status_updates_updated_at ON unit_status_updates;
CREATE TRIGGER update_unit_status_updates_updated_at 
    BEFORE UPDATE ON unit_status_updates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create indexes for new table
CREATE INDEX IF NOT EXISTS idx_unit_status_updates_incident ON unit_status_updates(incident_id);
CREATE INDEX IF NOT EXISTS idx_unit_status_updates_unit ON unit_status_updates(unit_id);
CREATE INDEX IF NOT EXISTS idx_unit_status_updates_created_at ON unit_status_updates(created_at);
CREATE INDEX IF NOT EXISTS idx_unit_status_updates_need_assistance ON unit_status_updates(need_assistance);
CREATE INDEX IF NOT EXISTS idx_unit_status_updates_geom ON unit_status_updates USING GIST(location_point);

-- Add columns to units table for tracking latest update info
ALTER TABLE units 
ADD COLUMN IF NOT EXISTS latest_progress_percentage INTEGER DEFAULT NULL CHECK (latest_progress_percentage >= 0 AND latest_progress_percentage <= 100),
ADD COLUMN IF NOT EXISTS need_assistance BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS latest_comment TEXT,
ADD COLUMN IF NOT EXISTS latest_update_time TIMESTAMP DEFAULT NULL;

COMMIT;

-- Verify migration
DO $$
DECLARE
    table_exists BOOLEAN;
    columns_added BOOLEAN;
BEGIN
    -- Check if unit_status_updates table exists
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'unit_status_updates'
    ) INTO table_exists;
    
    -- Check if new columns were added to units table
    SELECT EXISTS (
        SELECT FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'units' 
        AND column_name = 'latest_progress_percentage'
    ) INTO columns_added;
    
    RAISE NOTICE 'Migration 008 completed successfully!';
    RAISE NOTICE 'unit_status_updates table exists: %', table_exists;
    RAISE NOTICE 'New columns added to units table: %', columns_added;
    
    IF table_exists AND columns_added THEN
        RAISE NOTICE 'All migration components created successfully.';
    ELSE
        RAISE WARNING 'Some migration components may have failed to create.';
    END IF;
END $$;
