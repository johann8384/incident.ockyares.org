// Unit Checkin specific JavaScript
const incidentId = window.location.pathname.split('/').slice(-2)[0]; // Get incident ID from URL
let map;
let currentMarker;
let incidentMarker;
let incidentData = null;

// Initialize map
function initMap() {
    // Default to Louisville area
    map = L.map('locationMap').setView(MAP_DEFAULTS.defaultCenter, MAP_DEFAULTS.defaultZoom);
    
    L.tileLayer(MAP_DEFAULTS.tileLayer, {
        attribution: MAP_DEFAULTS.attribution
    }).addTo(map);

    // Add click handler for map
    map.on('click', function(e) {
        setLocation(e.latlng.lat, e.latlng.lng);
    });

    // Load incident data and add incident marker
    loadIncidentData();
}

// Load incident data
async function loadIncidentData() {
    try {
        const data = await apiCall(`/api/incident/${incidentId}`);
        
        if (data.incident) {
            incidentData = data.incident;
            
            // Update incident location display
            if (incidentData.address) {
                document.getElementById('incidentLocation').textContent = incidentData.address;
            } else if (incidentData.incident_location) {
                const coords = incidentData.incident_location.coordinates;
                document.getElementById('incidentLocation').textContent = 
                    formatCoordinates(coords[1], coords[0]);
            }
            
            // Add incident marker if location exists
            if (incidentData.incident_location) {
                const coords = incidentData.incident_location.coordinates;
                const lat = coords[1];
                const lng = coords[0];
                
                // Create custom green icon for incident
                const incidentIcon = L.divIcon({
                    html: '<div style="background-color: #28a745; width: 25px; height: 25px; border-radius: 50%; border: 2px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>',
                    iconSize: [25, 25],
                    iconAnchor: [12, 12],
                    className: 'incident-marker'
                });
                
                incidentMarker = L.marker([lat, lng], { icon: incidentIcon })
                    .addTo(map)
                    .bindPopup(`<strong>Incident Location</strong><br>${incidentData.name}`);
                
                // Center map on incident location
                map.setView([lat, lng], 14);
            }
        }
    } catch (error) {
        console.error('Error loading incident data:', error);
        document.getElementById('incidentLocation').textContent = 'Unable to load';
    }
}

// Set location on map and form
function setLocation(lat, lng) {
    document.getElementById('latitude').value = lat;
    document.getElementById('longitude').value = lng;
    
    // Remove existing unit marker
    if (currentMarker) {
        map.removeLayer(currentMarker);
    }
    
    // Add new unit marker (default blue)
    currentMarker = createUnitMarker(lat, lng, 'Unit Location')
        .addTo(map);
    
    // Update display
    document.getElementById('locationDisplay').textContent = 
        `Unit Location: ${formatCoordinates(lat, lng)}`;
    
    // Center map on location if incident marker doesn't exist
    if (!incidentMarker) {
        map.setView([lat, lng], Math.max(map.getZoom(), 15));
    }
}

// Get device location
function handleGetCurrentLocation() {
    const button = document.getElementById('getCurrentLocation');
    const originalText = button.textContent;
    
    button.textContent = 'Getting location...';
    button.disabled = true;
    
    getCurrentLocation(
        (lat, lng) => {
            setLocation(lat, lng);
            button.textContent = originalText;
            button.disabled = false;
        },
        (error) => {
            showAlert(error, 'danger');
            button.textContent = originalText;
            button.disabled = false;
        }
    );
}

// Clear location
function handleClearLocation() {
    document.getElementById('latitude').value = '';
    document.getElementById('longitude').value = '';
    document.getElementById('locationDisplay').textContent = 
        'Click "Get Device Location" or click on the map to set location';
    
    if (currentMarker) {
        map.removeLayer(currentMarker);
        currentMarker = null;
    }
}

// Handle form submission
async function handleFormSubmission(e) {
    e.preventDefault();
    
    const formData = new FormData(e.target);
    const data = Object.fromEntries(formData.entries());
    data.incident_id = incidentId;
    data.bsar_tech = document.getElementById('bsarTech').checked;
    
    // Validate location
    if (!data.latitude || !data.longitude) {
        showAlert('Please set the unit location on the map.', 'danger');
        return;
    }
    
    try {
        // Submit form using new unified endpoint
        const response = await apiCall(`/api/unit/${data.unit_id}/status`, {
            method: 'POST',
            body: JSON.stringify({
                incident_id: data.incident_id,
                status: 'staging', // Check-in is staging status
                unit_name: data.unit_id, // Use unit_id as name
                unit_type: 'Unknown', // Default type
                unit_leader: data.company_officer,
                number_of_personnel: parseInt(data.number_of_personnel),
                bsar_tech: data.bsar_tech,
                latitude: parseFloat(data.latitude),
                longitude: parseFloat(data.longitude),
                notes: data.notes || 'Unit checked in',
                user_name: data.company_officer
            })
        });
        
        document.getElementById('checkedInUnitId').textContent = data.unit_id;
        new bootstrap.Modal(document.getElementById('successModal')).show();
        
    } catch (error) {
        showAlert('Error checking in unit: ' + error.message, 'danger');
    }
}

// Reset form for another checkin
function resetForm() {
    document.getElementById('checkinForm').reset();
    handleClearLocation();
    bootstrap.Modal.getInstance(document.getElementById('successModal')).hide();
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    initCommonFeatures();
    
    // Event listeners
    document.getElementById('getCurrentLocation').addEventListener('click', handleGetCurrentLocation);
    document.getElementById('clearLocation').addEventListener('click', handleClearLocation);
    document.getElementById('checkinForm').addEventListener('submit', handleFormSubmission);
    
    // Make resetForm available globally for modal
    window.resetForm = resetForm;
});