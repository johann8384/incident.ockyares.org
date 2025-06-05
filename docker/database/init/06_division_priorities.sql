-- Add priority field to search_divisions table
ALTER TABLE search_divisions 
ADD COLUMN IF NOT EXISTS priority VARCHAR(10) DEFAULT 'Low';

-- Create index for priority
CREATE INDEX IF NOT EXISTS idx_search_divisions_priority ON search_divisions(priority);

-- Update existing divisions to have Low priority by default
UPDATE search_divisions SET priority = 'Low' WHERE priority IS NULL;

COMMENT ON COLUMN search_divisions.priority IS 'Division priority: High, Medium, or Low';
