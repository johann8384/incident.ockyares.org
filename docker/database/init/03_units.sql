-- Units and personnel tables
CREATE TABLE units (
    id SERIAL PRIMARY KEY,
    unit_id VARCHAR(50) UNIQUE NOT NULL,
    unit_name VARCHAR(255) NOT NULL,
    unit_type VARCHAR(100) NOT NULL, -- Fire, Police, EMS, SAR, etc.
    status VARCHAR(50) DEFAULT 'available', -- available, en_route, on_scene, out_of_service
    officer_name VARCHAR(255) NOT NULL,
    current_location GEOMETRY(POINT, 4326),
    current_address TEXT,
    unit_photo_url TEXT,
    contact_info JSONB, -- phone, radio, etc.
    capabilities JSONB, -- equipment, specialties, etc.
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE unit_personnel (
    id SERIAL PRIMARY KEY,
    unit_id VARCHAR(50) REFERENCES units(unit_id),
    person_name VARCHAR(255) NOT NULL,
    role VARCHAR(100), -- Paramedic, Driver, etc.
    certification_level VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE unit_check_ins (
    id SERIAL PRIMARY KEY,
    unit_id VARCHAR(50) REFERENCES units(unit_id),
    incident_id VARCHAR(50) REFERENCES incidents(incident_id),
    check_in_time TIMESTAMP DEFAULT NOW(),
    location GEOMETRY(POINT, 4326),
    address TEXT,
    status VARCHAR(50),
    notes TEXT,
    photo_url TEXT
);

-- View for unit check-in interface
CREATE VIEW unit_checkin_view AS
SELECT 
    u.unit_id,
    u.unit_name,
    u.unit_type,
    u.officer_name,
    u.status,
    u.current_location,
    u.current_address,
    u.unit_photo_url,
    u.contact_info,
    u.capabilities,
    u.incident_id,
    ARRAY_AGG(
        CASE 
            WHEN up.person_name IS NOT NULL 
            THEN jsonb_build_object(
                'name', up.person_name,
                'role', up.role,
                'certification', up.certification_level
            )
        END
    ) FILTER (WHERE up.person_name IS NOT NULL) as personnel,
    u.updated_at,
    ST_X(u.current_location) as longitude,
    ST_Y(u.current_location) as latitude
FROM units u
LEFT JOIN unit_personnel up ON u.unit_id = up.unit_id
GROUP BY u.id, u.unit_id, u.unit_name, u.unit_type, u.officer_name, 
         u.status, u.current_location, u.current_address, u.unit_photo_url,
         u.contact_info, u.capabilities, u.incident_id, u.updated_at;

-- View for incident command to see all units
CREATE VIEW incident_units_view AS
SELECT 
    i.incident_id,
    i.incident_name,
    u.unit_id,
    u.unit_name,
    u.unit_type,
    u.officer_name,
    u.status,
    u.current_address,
    ST_X(u.current_location) as longitude,
    ST_Y(u.current_location) as latitude,
    ARRAY_AGG(
        CASE 
            WHEN up.person_name IS NOT NULL 
            THEN jsonb_build_object(
                'name', up.person_name,
                'role', up.role
            )
        END
    ) FILTER (WHERE up.person_name IS NOT NULL) as personnel_count,
    u.updated_at as last_update
FROM incidents i
LEFT JOIN units u ON i.incident_id = u.incident_id
LEFT JOIN unit_personnel up ON u.unit_id = up.unit_id
GROUP BY i.incident_id, i.incident_name, u.unit_id, u.unit_name, 
         u.unit_type, u.officer_name, u.status, u.current_address,
         u.current_location, u.updated_at
ORDER BY u.updated_at DESC;

-- Indexes
CREATE INDEX idx_units_unit_id ON units(unit_id);
CREATE INDEX idx_units_incident_id ON units(incident_id);
CREATE INDEX idx_units_status ON units(status);
CREATE INDEX idx_units_location ON units USING GIST(current_location);
CREATE INDEX idx_unit_personnel_unit_id ON unit_personnel(unit_id);
CREATE INDEX idx_unit_checkins_unit_id ON unit_check_ins(unit_id);
CREATE INDEX idx_unit_checkins_incident_id ON unit_check_ins(incident_id);

-- Function to update unit location and trigger check-in
CREATE OR REPLACE FUNCTION update_unit_location(
    p_unit_id VARCHAR(50),
    p_latitude DECIMAL,
    p_longitude DECIMAL,
    p_address TEXT DEFAULT NULL,
    p_status VARCHAR(50) DEFAULT NULL,
    p_incident_id VARCHAR(50) DEFAULT NULL,
    p_notes TEXT DEFAULT NULL
) RETURNS JSONB AS $$
DECLARE
    result JSONB;
BEGIN
    -- Update unit location
    UPDATE units 
    SET 
        current_location = ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326),
        current_address = COALESCE(p_address, current_address),
        status = COALESCE(p_status, status),
        incident_id = COALESCE(p_incident_id, incident_id),
        updated_at = NOW()
    WHERE unit_id = p_unit_id;
    
    -- Insert check-in record
    INSERT INTO unit_check_ins (
        unit_id, incident_id, location, address, status, notes
    ) VALUES (
        p_unit_id,
        p_incident_id,
        ST_SetSRID(ST_MakePoint(p_longitude, p_latitude), 4326),
        p_address,
        p_status,
        p_notes
    );
    
    -- Return updated unit info
    SELECT jsonb_build_object(
        'unit_id', unit_id,
        'status', status,
        'location', jsonb_build_object(
            'latitude', ST_Y(current_location),
            'longitude', ST_X(current_location),
            'address', current_address
        ),
        'updated_at', updated_at
    ) INTO result
    FROM units 
    WHERE unit_id = p_unit_id;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;
