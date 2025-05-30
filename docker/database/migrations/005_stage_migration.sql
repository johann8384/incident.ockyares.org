-- Migration to change incident status to stage system
-- This migration updates the incidents table to use stages instead of status

DO $$
BEGIN
    -- First, check if the stage column already exists
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='incidents' AND column_name='stage'
    ) THEN
        -- Add the new stage column
        ALTER TABLE incidents ADD COLUMN stage VARCHAR(50) DEFAULT 'New';
        
        -- Migrate existing status values to appropriate stages
        UPDATE incidents 
        SET stage = CASE 
            WHEN status = 'active' THEN 'Response'
            WHEN status = 'closed' THEN 'Closed'
            WHEN status = 'archived' THEN 'Closed'
            ELSE 'New'
        END;
        
        -- Add constraint to ensure only valid stages
        ALTER TABLE incidents 
        ADD CONSTRAINT incidents_stage_check 
        CHECK (stage IN ('New', 'Response', 'Recovery', 'Closed'));
        
        -- Drop the old status column after migration
        ALTER TABLE incidents DROP COLUMN IF EXISTS status;
        
        RAISE NOTICE 'Successfully migrated incidents.status to incidents.stage';
    ELSE
        RAISE NOTICE 'Stage column already exists, skipping migration';
    END IF;
END $$;

-- Update any existing default values and constraints
DO $$
BEGIN
    -- Ensure the default value is set correctly
    ALTER TABLE incidents ALTER COLUMN stage SET DEFAULT 'New';
    
    -- Drop old constraint if it exists and recreate
    IF EXISTS (
        SELECT 1 FROM information_schema.constraint_column_usage 
        WHERE constraint_name = 'incidents_stage_check'
    ) THEN
        ALTER TABLE incidents DROP CONSTRAINT incidents_stage_check;
    END IF;
    
    ALTER TABLE incidents 
    ADD CONSTRAINT incidents_stage_check 
    CHECK (stage IN ('New', 'Response', 'Recovery', 'Closed'));
    
    RAISE NOTICE 'Stage constraints updated';
END $$;
