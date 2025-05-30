-- Complete migration script to bring existing database up to current schema
-- This addresses all missing tables and columns

-- Enable PostGIS extension if not already enabled
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Create the trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- 1. Add missing updated_at columns to existing tables

-- Add updated_at to incidents table
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='incidents' AND column_name='updated_at'
    ) THEN
        ALTER TABLE incidents ADD COLUMN updated_at TIMESTAMP DEFAULT NOW();
        UPDATE incidents SET updated_at = created_at WHERE updated_at IS NULL;
        RAISE NOTICE 'Added updated_at column to incidents table';
    END IF;
END $$;

-- Add updated_at to search_areas table
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='search_areas' AND column_name='updated_at'
    ) THEN
        ALTER TABLE search_areas ADD COLUMN updated_at TIMESTAMP DEFAULT NOW();
        UPDATE search_areas SET updated_at = created_at WHERE updated_at IS NULL;
        RAISE NOTICE 'Added updated_at column to search_areas table';
    END IF;
END $$;

-- Add updated_at to search_divisions table
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='search_divisions' AND column_name='updated_at'
    ) THEN
        ALTER TABLE search_divisions ADD COLUMN updated_at TIMESTAMP DEFAULT NOW();
        UPDATE search_divisions SET updated_at = created_at WHERE updated_at IS NULL;
        RAISE NOTICE 'Added updated_at column to search_divisions table';
    END IF;
END $$;

-- Add created_at and updated_at to search_progress table if missing
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='search_progress' AND column_name='created_at'
    ) THEN
        ALTER TABLE search_progress ADD COLUMN created_at TIMESTAMP DEFAULT NOW();
        UPDATE search_progress SET created_at = timestamp WHERE created_at IS NULL;
        RAISE NOTICE 'Added created_at column to search_progress table';
    END IF;
    
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='search_progress' AND column_name='updated_at'
    ) THEN
        ALTER TABLE search_progress ADD COLUMN updated_at TIMESTAMP DEFAULT NOW();
        UPDATE search_progress SET updated_at = timestamp WHERE updated_at IS NULL;
        RAISE NOTICE 'Added updated_at column to search_progress table';
    END IF;
END $$;

-- 2. Create unit_checkins table if it doesn't exist
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

-- 3. Create indexes if they don't exist
CREATE INDEX IF NOT EXISTS idx_unit_checkins_incident ON unit_checkins(incident_id);
CREATE INDEX IF NOT EXISTS idx_unit_checkins_unit ON unit_checkins(unit_id);
CREATE INDEX IF NOT EXISTS idx_unit_checkins_geom ON unit_checkins USING GIST(location_point);

-- 4. Create triggers for all tables

-- Incidents trigger
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'update_incidents_updated_at'
    ) THEN
        CREATE TRIGGER update_incidents_updated_at 
        BEFORE UPDATE ON incidents
        FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
        RAISE NOTICE 'Added trigger for incidents table';
    END IF;
END $$;

-- Search areas trigger
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'update_search_areas_updated_at'
    ) THEN
        CREATE TRIGGER update_search_areas_updated_at 
        BEFORE UPDATE ON search_areas
        FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
        RAISE NOTICE 'Added trigger for search_areas table';
    END IF;
END $$;

-- Search divisions trigger
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'update_search_divisions_updated_at'
    ) THEN
        CREATE TRIGGER update_search_divisions_updated_at 
        BEFORE UPDATE ON search_divisions
        FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
        RAISE NOTICE 'Added trigger for search_divisions table';
    END IF;
END $$;

-- Search progress trigger
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'update_search_progress_updated_at'
    ) THEN
        CREATE TRIGGER update_search_progress_updated_at 
        BEFORE UPDATE ON search_progress
        FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
        RAISE NOTICE 'Added trigger for search_progress table';
    END IF;
END $$;

-- Unit checkins trigger
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'update_unit_checkins_updated_at'
    ) THEN
        CREATE TRIGGER update_unit_checkins_updated_at 
        BEFORE UPDATE ON unit_checkins
        FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
        RAISE NOTICE 'Added trigger for unit_checkins table';
    END IF;
END $$;

-- 5. Verification - show what we have now
DO $$
BEGIN
    RAISE NOTICE 'Migration complete! Verifying database schema...';
END $$;

-- Show all tables
SELECT table_name, 
       CASE WHEN table_name = 'unit_checkins' THEN 'CREATED' ELSE 'EXISTING' END as status
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_type = 'BASE TABLE'
  AND table_name IN ('incidents', 'search_areas', 'search_divisions', 'search_progress', 'unit_checkins')
ORDER BY table_name;

-- Show updated_at columns
SELECT 
    table_name,
    column_name,
    data_type,
    column_default
FROM information_schema.columns 
WHERE table_name IN ('incidents', 'search_areas', 'search_divisions', 'search_progress', 'unit_checkins')
  AND column_name IN ('created_at', 'updated_at')
ORDER BY table_name, column_name;

-- Show triggers
SELECT 
    trigger_name,
    event_object_table
FROM information_schema.triggers 
WHERE trigger_name LIKE '%updated_at%'
ORDER BY event_object_table;
