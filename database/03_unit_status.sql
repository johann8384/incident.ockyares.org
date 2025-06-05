-- Add unit status enum type
CREATE TYPE unit_status_enum AS ENUM (
    'Staging',
    'Assigned', 
    'Operating',
    'Recovering',
    'Out of Service',
    'Quarters'
);

-- Add current_status to units table
ALTER TABLE units 
ADD COLUMN IF NOT EXISTS current_status unit_status_enum