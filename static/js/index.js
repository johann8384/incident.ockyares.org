// Index page specific JavaScript
let map, incidentMarker, searchAreaLayer, divisionsGroup;
let isLocationMode = false;
let isDrawMode = false;
let drawControl = null;
let hasSearchArea = false;
let hasDivisions = false;
let incidentLocation = null;
let pendingLocation = null; // Store the pin location before saving
let drawingPoints = [];
let currentDrawingLine = null;
let searchAreaPolygon = null;
let hospitalData = null;
let generatedDivisions = null; // Store divisions from preview

// Initialize map
function initMap() {
    map = L.map('map').setView(MAP_DEFAULTS.defaultCenter, MAP_DEFAULTS.defaultZoom);
    
    L.tileLayer(MAP_DEFAULTS.tileLayer, {
        attribution: MAP_DEFAULTS.attribution
    }).addTo(map);
    
    // Initialize feature groups
    searchAreaLayer = new L.FeatureGroup();
    divisionsGroup = new L.FeatureGroup();
    map.addLayer(searchAreaLayer);
    map.addLayer(divisionsGroup);

    // Setup common map features
    setupMapCoordinateDisplay(map);
}

// Check if form is valid and location is set
function checkFormReadiness() {
    const name = document.getElementById('incidentName').value.trim();
    const type = document.getElementById('incidentType').value;
    const hasLocation = incidentLocation !== null;
    
    const isReady = name && type && hasLocation;
    document.getElementById('createIncidentBtn').disabled = !isReady;
    
    return isReady;
}

// Check if incident location is within search area polygon
function isIncidentLocationInSearchArea() {
    if (!incidentLocation || !searchAreaPolygon) {
        return true; // If no location or search area, don't check
    }
    
    const incidentPoint = L.latLng(incidentLocation.latitude, incidentLocation.longitude);
    const searchAreaBounds = searchAreaPolygon.getBounds();
    
    // First do a quick bounds check
    if (!searchAreaBounds.contains(incidentPoint)) {
        return false;
    }
    
    // More precise point-in-polygon check using Leaflet's geometry
    const searchAreaLatLngs = searchAreaPolygon.getLatLngs()[0];
    
    // Convert to simple coordinate arrays for point-in-polygon calculation
    const polygon = searchAreaLatLngs.map(point => [point.lat, point.lng]);
    const point = [incidentLocation.latitude, incidentLocation.longitude];
    
    return pointInPolygon(point, polygon);
}

// Point-in-polygon algorithm (ray casting)
function pointInPolygon(point, polygon) {
    const [x, y] = point;
    let inside = false;
    
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const [xi, yi] = polygon[i];
        const [xj, yj] = polygon[j];
        
        if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi) + xi)) {
            inside = !inside;
        }
    }
    
    return inside;
}

// Fetch hospital data from server
async function fetchHospitalData(lat, lng) {
    return await apiCall('/api/hospitals/search', {
        method: 'POST',
        body: JSON.stringify({
            latitude: lat,
            longitude: lng
        })
    });
}

// Reverse geocode coordinates to address using backend
async function reverseGeocode(lat, lng) {
    try {
        const data = await apiCall('/api/geocode/reverse', {
            method: 'POST',
            body: JSON.stringify({
                latitude: lat,
                longitude: lng
            })
        });
        return data.address;
    } catch (error) {
        console.warn('Reverse geocoding failed:', error);
        return null;
    }
}

// Generate divisions preview using API
async function generateDivisionsPreview(coordinates) {
    const data = await apiCall('/api/divisions/generate', {
        method: 'POST',
        body: JSON.stringify({
            coordinates: coordinates.map(coord => [coord.lng, coord.lat]), // Convert to lng,lat
            area_size_m2: 40000
        })
    });
    return data.divisions;
}

// Start location placement mode
function startLocationMode() {
    // Check if there's a search area or divisions defined
    if (hasSearchArea || hasDivisions) {
        const confirmed = confirm('Setting a new Incident Location will remove the defined search area and divisions. Do you want to continue?');
        if (!confirmed) {
            return; // User cancelled, abort the operation
        }
        // User confirmed, clear search area and divisions
        clearSearchAreaAndDivisions();
    }
    
    isLocationMode = true;
    const btn = document.getElementById('setLocationBtn');
    btn.innerHTML = '<i class="bi bi-crosshair me-2"></i>Click map to place pin';
    btn.classList.remove('btn-primary');
    btn.classList.add('btn-warning');
    btn.disabled = true; // Disable until pin is placed
    showStatus('Click on the map to place incident location pin', 'success');
}

// Clear search area and divisions
function clearSearchAreaAndDivisions() {
    searchAreaLayer.clearLayers();
    divisionsGroup.clearLayers();
    hasSearchArea = false;
    hasDivisions = false;
    isDrawMode = false;
    drawingPoints = [];
    currentDrawingLine = null;
    searchAreaPolygon = null;
    generatedDivisions = null;
    
    // Reset search area button
    const drawBtn = document.getElementById('drawAreaBtn');
    drawBtn.innerHTML = '<i class="bi bi-bounding-box me-2"></i>Draw Search Area';
    drawBtn.classList.remove('btn-success');
    drawBtn.classList.add('btn-warning');
    drawBtn.disabled = true; // Will be enabled when location is set
    
    // Disable search area controls
    document.getElementById('clearAreaBtn').disabled = true;
    document.getElementById('generateDivisionsBtn').disabled = true;
    document.getElementById('divisionsInfo').classList.add('d-none');
    
    showStatus('Search area and divisions cleared', 'success');
}

// Place incident marker without saving
function placeIncidentPin(lat, lng) {
    // Remove existing marker
    if (incidentMarker) {
        map.removeLayer(incidentMarker);
    }
    
    // Add new marker (temporary - different style to show it's not saved)
    incidentMarker = L.marker([lat, lng], {
        opacity: 0.7 // Make it slightly transparent to show it's temporary
    }).addTo(map);
    
    incidentMarker.bindPopup('<b>Proposed Incident Location</b><br>Click "Save Incident Location" to confirm');
    
    // Store pending location
    pendingLocation = { latitude: lat, longitude: lng };
    
    // Update button to allow saving
    const btn = document.getElementById('setLocationBtn');
    btn.innerHTML = '<i class="bi bi-floppy me-2"></i>Save Incident Location';
    btn.classList.remove('btn-warning');
    btn.classList.add('btn-success');
    btn.disabled = false;
    
    showStatus('Pin placed! Click "Save Incident Location" to confirm and look up details.', 'success');
}

// Save incident location and perform lookups
async function saveIncidentLocation() {
    if (!pendingLocation) {
        showStatus('No location to save', 'error');
        return;
    }
    
    try {
        const lat = pendingLocation.latitude;
        const lng = pendingLocation.longitude;
        
        // Update button to show loading
        const btn = document.getElementById('setLocationBtn');
        btn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Saving location...';
        btn.disabled = true;
        
        // Show loading message
        showStatus('Saving location, looking up address and nearby hospitals...', 'success');
        
        // Show hospital info panel with loading state
        document.getElementById('hospitalInfo').classList.remove('d-none');
        
        // Make marker permanent (full opacity)
        if (incidentMarker) {
            incidentMarker.setOpacity(1.0);
        }
        
        // Attempt reverse geocoding and hospital lookup in parallel
        const [address, hospitalResponse] = await Promise.all([
            reverseGeocode(lat, lng),
            fetchHospitalData(lat, lng)
        ]);
        
        // Store the final location
        incidentLocation = { latitude: lat, longitude: lng };
        
        if (address) {
            incidentLocation.address = address;
            incidentMarker.bindPopup(`<b>Incident Location</b><br>${address}`);
        } else {
            incidentMarker.bindPopup(`<b>Incident Location</b><br>Lat: ${lat.toFixed(6)}, Lng: ${lng.toFixed(6)}`);
        }
        
        // Process hospital data
        hospitalData = hospitalResponse.hospitals;
        displayHospitalInfo(hospitalData);
        
        // Update incident info display
        updateIncidentLocationDisplay();
        
        // Reset button and state
        btn.innerHTML = '<i class="bi bi-geo-alt-fill me-2"></i>Set Incident Location';
        btn.classList.remove('btn-success');
        btn.classList.add('btn-primary');
        btn.disabled = false;
        isLocationMode = false;
        pendingLocation = null;
        
        // Enable location-dependent controls
        document.getElementById('drawAreaBtn').disabled = false;
        
        // Check if form is ready
        checkFormReadiness();
        
        showStatus(`Location saved with hospital data loaded`, 'success');
        
    } catch (error) {
        showStatus('Error saving location: ' + error.message, 'error');
        
        // Reset button on error
        const btn = document.getElementById('setLocationBtn');
        btn.innerHTML = '<i class="bi bi-floppy me-2"></i>Save Incident Location';
        btn.classList.remove('btn-success');
        btn.classList.add('btn-success');
        btn.disabled = false;
        
        // Hide hospital info on error
        document.getElementById('hospitalInfo').classList.add('d-none');
    }
}

// Display hospital information
function displayHospitalInfo(hospitals) {
    const details = document.getElementById('hospitalDetails');
    
    let html = '<div class="row g-3">';
    
    // Closest Hospital
    if (hospitals.closest) {
        const h = hospitals.closest.attributes;
        html += `
            <div class="col-md-4">
                <div class="card border-primary">
                    <div class="card-header bg-primary text-white">
                        <h6 class="card-title mb-0">
                            <i class="bi bi-geo-alt me-2"></i>Closest Hospital
                        </h6>
                    </div>
                    <div class="card-body">
                        <h6 class="card-title">${h.FACILITY || 'Unknown'}</h6>
                        <p class="card-text small">
                            <strong>Distance:</strong> ${hospitals.closest.distance.toFixed(1)} km<br>
                            <strong>Type:</strong> ${h.LIC_TYPE || 'Not specified'}<br>
                            <strong>Address:</strong> ${h.ADDRESS || 'Not available'}<br>
                            <strong>City:</strong> ${h.CITY || 'Not available'}<br>
                            <strong>Phone:</strong> ${h.PHONE || 'Not available'}
                        </p>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Closest Level 1 Trauma
    if (hospitals.level1_trauma) {
        const h = hospitals.level1_trauma.attributes;
        html += `
            <div class="col-md-4">
                <div class="card border-success">
                    <div class="card-header bg-success text-white">
                        <h6 class="card-title mb-0">
                            <i class="bi bi-heart-pulse me-2"></i>Closest Level 1 Trauma
                        </h6>
                    </div>
                    <div class="card-body">
                        <h6 class="card-title">${h.FACILITY || 'Unknown'}</h6>
                        <p class="card-text small">
                            <strong>Distance:</strong> ${hospitals.level1_trauma.distance.toFixed(1)} km<br>
                            <strong>Type:</strong> ${h.LIC_TYPE || 'Not specified'}<br>
                            <strong>Address:</strong> ${h.ADDRESS || 'Not available'}<br>
                            <strong>City:</strong> ${h.CITY || 'Not available'}<br>
                            <strong>Phone:</strong> ${h.PHONE || 'Not available'}
                        </p>
                    </div>
                </div>
            </div>
        `;
    } else {
        html += `
            <div class="col-md-4">
                <div class="card border-warning">
                    <div class="card-header bg-warning">
                        <h6 class="card-title mb-0">
                            <i class="bi bi-heart-pulse me-2"></i>Closest Level 1 Trauma
                        </h6>
                    </div>
                    <div class="card-body">
                        <p class="card-text text-muted">No Level 1 trauma center found in the area.</p>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Closest Level 1 Pediatric
    if (hospitals.level1_pediatric) {
        const h = hospitals.level1_pediatric.attributes;
        html += `
            <div class="col-md-4">
                <div class="card border-info">
                    <div class="card-header bg-info text-white">
                        <h6 class="card-title mb-0">
                            <i class="bi bi-heart me-2"></i>Closest Level 1 Pediatric
                        </h6>
                    </div>
                    <div class="card-body">
                        <h6 class="card-title">${h.FACILITY || 'Unknown'}</h6>
                        <p class="card-text small">
                            <strong>Distance:</strong> ${hospitals.level1_pediatric.distance.toFixed(1)} km<br>
                            <strong>Type:</strong> ${h.LIC_TYPE || 'Not specified'}<br>
                            <strong>Address:</strong> ${h.ADDRESS || 'Not available'}<br>
                            <strong>City:</strong> ${h.CITY || 'Not available'}<br>
                            <strong>Phone:</strong> ${h.PHONE || 'Not available'}
                        </p>
                    </div>
                </div>
            </div>
        `;
    } else {
        html += `
            <div class="col-md-4">
                <div class="card border-warning">
                    <div class="card-header bg-warning">
                        <h6 class="card-title mb-0">
                            <i class="bi bi-heart me-2"></i>Closest Level 1 Pediatric
                        </h6>
                    </div>
                    <div class="card-body">
                        <p class="card-text text-muted">No Level 1 pediatric trauma center found in the area.</p>
                    </div>
                </div>
            </div>
        `;
    }
    
    html += '</div>';
    details.innerHTML = html;
}

// Update incident location display
function updateIncidentLocationDisplay() {
    const info = document.getElementById('incidentInfo');
    const details = document.getElementById('incidentDetails');
    
    details.innerHTML = `
        <div class="row g-2">
            <div class="col-12">
                <strong>Coordinates:</strong> <code class="bg-light px-2 py-1 rounded">${formatCoordinates(incidentLocation.latitude, incidentLocation.longitude)}</code>
            </div>
            ${incidentLocation.address ? `
                <div class="col-12">
                    <strong>Address:</strong> ${incidentLocation.address}
                </div>
            ` : ''}
        </div>
    `;
    info.classList.remove('d-none');
}

// Enable drawing mode
function enableDrawMode() {
    isDrawMode = true;
    drawingPoints = [];
    
    const btn = document.getElementById('drawAreaBtn');
    btn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Save Search Area';
    btn.classList.remove('btn-warning');
    btn.classList.add('btn-success');
    
    // Clear any existing search area
    searchAreaLayer.clearLayers();
    
    showStatus('Click points on the map to draw search area polygon. Click "Save Search Area" when done.', 'success');
}

// Handle map clicks for drawing
function handleMapClick(e) {
    if (isLocationMode) {
        placeIncidentPin(e.latlng.lat, e.latlng.lng);
        return;
    }
    
    if (isDrawMode) {
        addPointToDrawing(e.latlng);
    }
}

// Add point to drawing
function addPointToDrawing(latlng) {
    drawingPoints.push(latlng);
    
    // Add a marker for the point
    const marker = L.circleMarker(latlng, {
        radius: 5,
        fillColor: '#dc3545',
        color: '#dc3545',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.8
    }).addTo(searchAreaLayer);
    
    // Draw lines between points
    if (drawingPoints.length > 1) {
        if (currentDrawingLine) {
            searchAreaLayer.removeLayer(currentDrawingLine);
        }
        
        currentDrawingLine = L.polyline(drawingPoints, {
            color: '#dc3545',
            weight: 3,
            opacity: 0.8
        }).addTo(searchAreaLayer);
    }
    
    showStatus(`Added point ${drawingPoints.length}. Click "Save Search Area" when finished.`, 'success');
}

// Save search area
function saveSearchArea() {
    if (drawingPoints.length < 3) {
        showStatus('Please add at least 3 points to create a search area', 'error');
        return;
    }
    
    // Create temporary polygon to check if incident location is inside
    const tempPolygon = L.polygon(drawingPoints);
    
    // Check if incident location is within the search area
    if (incidentLocation && !isIncidentLocationInSearchArea()) {
        const confirmed = confirm('The search area does not include the incident location. Are you sure this is the search area you want to use?');
        if (!confirmed) {
            // User said no, clear the search area
            clearDrawingState();
            showStatus('Search area cleared. Please redraw to include the incident location.', 'success');
            return;
        }
    }
    
    // Clear the temporary drawing elements
    searchAreaLayer.clearLayers();
    
    // Create the final polygon
    searchAreaPolygon = L.polygon(drawingPoints, {
        color: '#dc3545',
        weight: 3,
        fillOpacity: 0.2,
        fillColor: '#dc3545'
    }).addTo(searchAreaLayer);
    
    searchAreaPolygon.bindPopup('<b>Search Area</b><br>Primary search zone');
    
    // Reset drawing state
    isDrawMode = false;
    hasSearchArea = true;
    const savedPoints = [...drawingPoints]; // Save points for division generation
    drawingPoints = [];
    currentDrawingLine = null;
    
    // Reset button
    const btn = document.getElementById('drawAreaBtn');
    btn.innerHTML = '<i class="bi bi-bounding-box me-2"></i>Draw Search Area';
    btn.classList.remove('btn-success');
    btn.classList.add('btn-warning');
    
    // Enable search area controls
    document.getElementById('clearAreaBtn').disabled = false;
    document.getElementById('generateDivisionsBtn').disabled = false;
    
    showStatus('Search area saved successfully', 'success');
}

// Clear drawing state without saving
function clearDrawingState() {
    searchAreaLayer.clearLayers();
    isDrawMode = false;
    drawingPoints = [];
    currentDrawingLine = null;
    
    // Reset button
    const btn = document.getElementById('drawAreaBtn');
    btn.innerHTML = '<i class="bi bi-bounding-box me-2"></i>Draw Search Area';
    btn.classList.remove('btn-success');
    btn.classList.add('btn-warning');
}

// Clear search area
function clearSearchArea() {
    clearSearchAreaAndDivisions();
}

// Generate divisions and display on map
async function generateDivisions() {
    if (!searchAreaPolygon) {
        showStatus('Please create a search area first', 'error');
        return;
    }
    
    try {
        // Clear existing divisions
        divisionsGroup.clearLayers();
        
        // Get search area coordinates
        const searchAreaCoords = searchAreaPolygon.getLatLngs()[0];
        
        // Generate divisions using API
        const btn = document.getElementById('generateDivisionsBtn');
        btn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Generating...';
        btn.disabled = true;
        
        showStatus('Generating search divisions...', 'success');
        
        generatedDivisions = await generateDivisionsPreview(searchAreaCoords);
        
        // Display divisions on map
        generatedDivisions.forEach((division, index) => {
            const colors = [
                '#198754', // success - assigned
                '#198754', // success - assigned  
                '#ffc107', // warning - unassigned
                '#17a2b8'  // info - completed
            ];
            const color = colors[index % colors.length];
            
            // Convert coordinates back to lat,lng
            const coordinates = division.coordinates ? 
                division.coordinates.map(coord => [coord[1], coord[0]]) : // lng,lat to lat,lng
                division.geom ? JSON.parse(division.geom).coordinates[0].map(coord => [coord[1], coord[0]]) : null;
            
            if (coordinates) {
                const divisionPolygon = L.polygon(coordinates, {
                    color: color,
                    weight: 2,
                    fillOpacity: 0.4,
                    fillColor: color
                }).addTo(divisionsGroup);
                
                // Add label in center of division
                const center = divisionPolygon.getBounds().getCenter();
                const label = L.marker(center, {
                    icon: L.divIcon({
                        className: 'division-label',
                        html: `<div style="background: white; border: 2px solid ${color}; border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px;">${division.division_id || division.name}</div>`,
                        iconSize: [30, 30],
                        iconAnchor: [15, 15]
                    })
                }).addTo(divisionsGroup);
                
                divisionPolygon.bindPopup(`
                    <b>${division.division_name || division.name}</b><br>
                    <strong>ID:</strong> ${division.division_id}<br>
                    <strong>Status:</strong> ${division.status || 'unassigned'}<br>
                    <strong>Team:</strong> ${division.assigned_team || 'Not assigned'}<br>
                    <strong>Priority:</strong> ${division.priority || 'Medium'}
                `);
                
                label.bindPopup(`
                    <b>${division.division_name || division.name}</b><br>
                    <strong>ID:</strong> ${division.division_id}<br>
                    <strong>Status:</strong> ${division.status || 'unassigned'}<br>
                    <strong>Team:</strong> ${division.assigned_team || 'Not assigned'}<br>
                    <strong>Priority:</strong> ${division.priority || 'Medium'}
                `);
            }
        });
        
        // Mark that we have divisions
        hasDivisions = true;
        
        // Reset button
        btn.innerHTML = '<i class="bi bi-lightning-fill me-2"></i>Generate Divisions';
        btn.disabled = false;
        
        showStatus(`Generated ${generatedDivisions.length} search divisions and displayed on map`, 'success');
        
        // Display divisions info
        const info = document.getElementById('divisionsInfo');
        const details = document.getElementById('divisionsDetails');
        
        details.innerHTML = `
            <div class="row g-2">
                <div class="col-sm-4"><strong>Divisions Created:</strong> ${generatedDivisions.length}</div>
                <div class="col-sm-8"><strong>Coverage:</strong> Optimized for teams (~40,000 m² per division)</div>
                <div class="col-12"><strong>Strategy:</strong> Grid-based divisions within search area polygon</div>
                <div class="col-12">
                    <small class="text-muted">
                        <i class="bi bi-info-circle me-1"></i>
                        Divisions are displayed on the map with different colors: 
                        <span class="badge bg-success">Assigned</span>
                        <span class="badge bg-warning text-dark">Unassigned</span>
                        <span class="badge bg-info">Completed</span>
                    </small>
                </div>
            </div>
        `;
        info.classList.remove('d-none');
        
    } catch (error) {
        showStatus('Error generating divisions: ' + error.message, 'error');
        
        // Reset button
        const btn = document.getElementById('generateDivisionsBtn');
        btn.innerHTML = '<i class="bi bi-lightning-fill me-2"></i>Generate Divisions';
        btn.disabled = false;
    }
}

// Create incident
async function createIncident() {
    if (!checkFormReadiness()) {
        showStatus('Please fill in all required fields and set incident location', 'error');
        return;
    }
    
    const formData = new FormData(document.getElementById('incidentForm'));
    
    try {
        const btn = document.getElementById('createIncidentBtn');
        btn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Creating Incident...';
        btn.disabled = true;
        
        const incidentPayload = {
            name: formData.get('name'),
            incident_type: formData.get('incident_type'),
            description: formData.get('description'),
            latitude: incidentLocation.latitude,
            longitude: incidentLocation.longitude,
            address: incidentLocation.address,
            hospital_data: hospitalData
        };
        
        // Add search area if defined
        if (searchAreaPolygon) {
            const coords = searchAreaPolygon.getLatLngs()[0];
            incidentPayload.search_area_coordinates = coords.map(coord => [coord.lng, coord.lat]);
        }
        
        // Add divisions if generated
        if (generatedDivisions) {
            incidentPayload.divisions = generatedDivisions;
        }
        
        const data = await apiCall('/api/incident', {
            method: 'POST',
            body: JSON.stringify(incidentPayload)
        });
        
        showStatus(`Incident created successfully: ${data.incident_id}`, 'success');
        
        // Disable form and redirect or show success state
        document.getElementById('incidentForm').querySelectorAll('input, select, textarea').forEach(el => el.disabled = true);
        btn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Incident Created';
        
        // Optional: redirect to incident view
        setTimeout(() => {
            window.location.href = `/incident/${data.incident_id}`;
        }, 2000);
        
    } catch (error) {
        showStatus('Error creating incident: ' + error.message, 'error');
        
        const btn = document.getElementById('createIncidentBtn');
        btn.innerHTML = '<i class="bi bi-plus-circle me-2"></i>Create Incident';
        btn.disabled = false;
    }
}

// Handle location button click
function handleLocationButtonClick() {
    if (pendingLocation && !incidentLocation) {
        // There's a pending location to save (first time setting location)
        saveIncidentLocation();
    } else if (pendingLocation && incidentLocation) {
        // There's a pending location to save (updating existing location)
        saveIncidentLocation();
    } else {
        // Start location placement mode
        startLocationMode();
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    initCommonFeatures();
    
    // Form change events
    document.getElementById('incidentName').addEventListener('input', checkFormReadiness);
    document.getElementById('incidentType').addEventListener('change', checkFormReadiness);
    
    // Map controls
    document.getElementById('setLocationBtn').addEventListener('click', handleLocationButtonClick);
    document.getElementById('drawAreaBtn').addEventListener('click', () => {
        if (isDrawMode) {
            saveSearchArea();
        } else {
            enableDrawMode();
        }
    });
    document.getElementById('clearAreaBtn').addEventListener('click', clearSearchArea);
    document.getElementById('generateDivisionsBtn').addEventListener('click', generateDivisions);
    document.getElementById('createIncidentBtn').addEventListener('click', createIncident);
    
    // Map click handler
    map.on('click', handleMapClick);
});