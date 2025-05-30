-- Migration script to add missing updated_at column to incidents table
-- Run this if you have an existing database that's missing the updated_at column

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
    END IF;
END $$;

-- Ensure the trigger function exists
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add trigger for incidents table if it doesn't exist
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger 
        WHERE tgname = 'update_incidents_updated_at'
    ) THEN
        CREATE TRIGGER update_incidents_updated_at 
        BEFORE UPDATE ON incidents
        FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();
    END IF;
END $$;

-- Verify the column exists
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns 
WHERE table_name = 'incidents' AND column_name = 'updated_at';
