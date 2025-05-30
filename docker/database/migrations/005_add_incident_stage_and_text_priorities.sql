-- Migration to add incident stage and update priority system
-- This adds the new incident_stage column and updates priority defaults

-- 1. Add incident_stage column to incidents table
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='incidents' AND column_name='incident_stage'
    ) THEN
        ALTER TABLE incidents ADD COLUMN incident_stage VARCHAR(50) DEFAULT 'New';
        UPDATE incidents SET incident_stage = 'New' WHERE incident_stage IS NULL;
        RAISE NOTICE 'Added incident_stage column to incidents table';
    END IF;
END $$;

-- 2. Update search_divisions priority default to be text-based
-- First, let's see what we're working with
DO $$
DECLARE
    priority_type text;
BEGIN
    SELECT data_type INTO priority_type 
    FROM information_schema.columns 
    WHERE table_name = 'search_divisions' AND column_name = 'priority';
    
    IF priority_type = 'integer' THEN
        -- Add new text-based priority column
        ALTER TABLE search_divisions ADD COLUMN priority_text VARCHAR(50) DEFAULT 'Medium';
        
        -- Convert existing integer priorities to text
        UPDATE search_divisions 
        SET priority_text = CASE 
            WHEN priority = 1 THEN 'High'
            WHEN priority = 2 THEN 'Medium' 
            WHEN priority = 3 THEN 'Low'
            WHEN priority >= 4 THEN 'Urgent'
            ELSE 'Medium'
        END;
        
        -- Drop the old integer column and rename the new one
        ALTER TABLE search_divisions DROP COLUMN priority;
        ALTER TABLE search_divisions RENAME COLUMN priority_text TO priority;
        
        RAISE NOTICE 'Updated search_divisions priority to text-based system';
    ELSE
        -- Priority is already text, just update any existing values
        UPDATE search_divisions SET priority = 'Medium' WHERE priority IS NULL;
        RAISE NOTICE 'Priority column already text-based, updated defaults';
    END IF;
END $$;

-- 3. Update search_areas priority to text-based as well
DO $$
DECLARE
    priority_type text;
BEGIN
    SELECT data_type INTO priority_type 
    FROM information_schema.columns 
    WHERE table_name = 'search_areas' AND column_name = 'priority';
    
    IF priority_type = 'integer' THEN
        -- Add new text-based priority column
        ALTER TABLE search_areas ADD COLUMN priority_text VARCHAR(50) DEFAULT 'Medium';
        
        -- Convert existing integer priorities to text
        UPDATE search_areas 
        SET priority_text = CASE 
            WHEN priority = 1 THEN 'High'
            WHEN priority = 2 THEN 'Medium' 
            WHEN priority = 3 THEN 'Low'
            WHEN priority >= 4 THEN 'Urgent'
            ELSE 'Medium'
        END;
        
        -- Drop the old integer column and rename the new one
        ALTER TABLE search_areas DROP COLUMN priority;
        ALTER TABLE search_areas RENAME COLUMN priority_text TO priority;
        
        RAISE NOTICE 'Updated search_areas priority to text-based system';
    ELSE
        -- Priority is already text, just update any existing values
        UPDATE search_areas SET priority = 'Medium' WHERE priority IS NULL;
        RAISE NOTICE 'Priority column already text-based, updated defaults';
    END IF;
END $$;

-- 4. Create index on incident_stage for performance
CREATE INDEX IF NOT EXISTS idx_incidents_stage ON incidents(incident_stage);

-- 5. Verification queries
SELECT 'Incident Stages' as info, incident_stage, COUNT(*) as count
FROM incidents 
GROUP BY incident_stage
UNION ALL
SELECT 'Search Division Priorities', priority, COUNT(*)
FROM search_divisions 
GROUP BY priority
UNION ALL
SELECT 'Search Area Priorities', priority, COUNT(*)
FROM search_areas 
GROUP BY priority
ORDER BY info, count DESC;

-- Show the new schema
SELECT 
    table_name,
    column_name,
    data_type,
    column_default
FROM information_schema.columns 
WHERE table_name IN ('incidents', 'search_divisions', 'search_areas')
  AND column_name IN ('incident_stage', 'priority')
ORDER BY table_name, column_name;
