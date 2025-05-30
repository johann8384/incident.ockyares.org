-- Migration: Add address field to incidents table
-- Description: Adds address column to store geocoded addresses for incident locations
-- Date: 2025-05-30
-- Version: 007_add_incident_address

BEGIN;

-- Add address column to incidents table
ALTER TABLE incidents ADD COLUMN IF NOT EXISTS address TEXT;

-- Add index for address searches
CREATE INDEX IF NOT EXISTS idx_incidents_address ON incidents(address);

-- Add comment to document the column
COMMENT ON COLUMN incidents.address IS 'Geocoded address of the incident location';

COMMIT;

-- Verify migration
DO $$
DECLARE
    address_column_exists BOOLEAN;
BEGIN
    -- Check if address column exists
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'incidents' AND column_name = 'address'
    ) INTO address_column_exists;
    
    IF address_column_exists THEN
        RAISE NOTICE 'Migration 007 completed successfully!';
        RAISE NOTICE 'Address column added to incidents table';
    ELSE
        RAISE EXCEPTION 'Migration 007 failed - address column not found';
    END IF;
END $$;
