-- Add priority field to search_divisions table and fix data type
ALTER TABLE search_divisions 
ADD COLUMN IF NOT EXISTS priority VARCHAR(10) DEFAULT 'Low';

-- Update existing priority column if it exists as integer
DO $$ 
BEGIN
    -- Check if priority column exists as integer and convert it
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'search_divisions' 
               AND column_name = 'priority' 
               AND data_type = 'integer') THEN
        -- Convert existing integer priorities to text
        UPDATE search_divisions SET priority = 'Low';
        ALTER TABLE search_divisions ALTER COLUMN priority TYPE VARCHAR(10);
    END IF;
END $$;

-- Create index for priority
CREATE INDEX IF NOT EXISTS idx_search_divisions_priority ON search_divisions(priority);

-- Update existing divisions to have Low priority by default
UPDATE search_divisions SET priority = 'Low' WHERE priority IS NULL;

COMMENT ON COLUMN search_divisions.priority IS 'Division priority: High, Medium, or Low';
