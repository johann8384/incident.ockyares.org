-- Units table for tracking responding resources
CREATE TABLE units (
    id SERIAL PRIMARY KEY,
    unit_id VARCHAR(50) UNIQUE NOT NULL,
    unit_name VARCHAR(255) NOT NULL,
    unit_type VARCHAR(100) NOT NULL, -- Engine, Truck, Rescue, Command, etc.
    unit_leader VARCHAR(255),
    contact_info VARCHAR(255),
    current_status VARCHAR(50) DEFAULT 'quarters',
    current_incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    current_division_id VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Unit status history for tracking all status changes
CREATE TABLE unit_status_history (
    id SERIAL PRIMARY KEY,
    unit_id VARCHAR(50) REFERENCES units(unit_id),
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    division_id VARCHAR(50),
    status VARCHAR(50) NOT NULL,
    percentage_complete INTEGER DEFAULT 0,
    location GEOMETRY(POINT, 4326),
    notes TEXT,
    timestamp TIMESTAMP DEFAULT NOW(),
    user_name VARCHAR(255)
);

-- Add assigned unit to search divisions
ALTER TABLE search_divisions 
ADD COLUMN assigned_unit_id VARCHAR(50) REFERENCES units(unit_id);

-- Create indexes
CREATE INDEX idx_units_unit_id ON units(unit_id);
CREATE INDEX idx_units_incident ON units(current_incident_id);
CREATE INDEX idx_unit_status_unit ON unit_status_history(unit_id);
CREATE INDEX idx_unit_status_incident ON unit_status_history(incident_id);
CREATE INDEX idx_unit_status_timestamp ON unit_status_history(timestamp);
CREATE INDEX idx_search_divisions_unit ON search_divisions(assigned_unit_id);

-- Create spatial index for unit locations
CREATE INDEX idx_unit_status_location ON unit_status_history USING GIST(location);
