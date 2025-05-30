-- Migration script to add missing updated_at columns to all tables
-- Run this if you have an existing database that's missing updated_at columns

-- Create the trigger function first
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add updated_at column to incidents table if it doesn't exist
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

-- Add updated_at column to search_areas table if it doesn't exist
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

-- Add updated_at column to search_divisions table if it doesn't exist
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

-- Add updated_at column to search_progress table if it doesn't exist
DO $$ 
BEGIN
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

-- Add updated_at column to unit_checkins table if it doesn't exist
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='unit_checkins' AND column_name='updated_at'
    ) THEN
        ALTER TABLE unit_checkins ADD COLUMN updated_at TIMESTAMP DEFAULT NOW();
        UPDATE unit_checkins SET updated_at = created_at WHERE updated_at IS NULL;
        RAISE NOTICE 'Added updated_at column to unit_checkins table';
    END IF;
END $$;

-- Add triggers for all tables if they don't exist

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

-- Verify all columns exist
SELECT 
    table_name,
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name IN ('incidents', 'search_areas', 'search_divisions', 'search_progress', 'unit_checkins')
  AND column_name = 'updated_at'
ORDER BY table_name;

-- Show triggers that were created
SELECT 
    trigger_name,
    event_object_table,
    action_timing,
    event_manipulation
FROM information_schema.triggers 
WHERE trigger_name LIKE '%updated_at%'
ORDER BY event_object_table;
