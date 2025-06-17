// Incident View JavaScript
let map, incidentMarker, searchAreaLayer, divisionsGroup, unitsGroup;
let incidentData = null;
let divisionsVisible = true;
let unitsData = [];
let divisionsData = [];

// Get incident ID from URL path
const incidentId = window.location.pathname.split('/').pop();

// Set up unit checkin URLs once we have the incident ID
document.addEventListener('DOMContentLoaded', function() {
    const unitCheckinUrl = `/incident/${incidentId}/unit-checkin`;
    document.getElementById('unitCheckinBtn').href = unitCheckinUrl;
    document.getElementById('checkinFirstUnitBtn').href = unitCheckinUrl;
});

// Helper function to get status badge class
function getStatusBadgeClass(status) {
    switch (status) {
        case 'staging': return 'secondary';
        case 'assigned': return 'primary';
        case 'operating': return 'success';
        case 'recovering': return 'warning';
        case 'out of service': return 'danger';
        case 'quarters': return 'dark';
        default: return 'secondary';
    }
}

// Helper function to get progress bar color based on percentage
function getProgressBarClass(percentage) {
    if (percentage >= 80) return 'bg-success';
    if (percentage >= 50) return 'bg-warning';
    if (percentage >= 25) return 'bg-info';
    return 'bg-danger';
}

// Initialize map
function initMap() {
    map = L.map('map').setView([38.3960874, -85.4425145], 13); // Default to Louisville, KY
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors'
    }).addTo(map);
    
    // Initialize feature groups
    searchAreaLayer = new L.FeatureGroup();
    divisionsGroup = new L.FeatureGroup();
    unitsGroup = new L.FeatureGroup();
    map.addLayer(searchAreaLayer);
    map.addLayer(divisionsGroup);
    map.addLayer(unitsGroup);

    // Update zoom level display
    function updateMapInfo() {
        const zoomElement = document.getElementById('mapZoom');
        if (zoomElement) {
            zoomElement.innerHTML = `<i class="bi bi-zoom-in me-1"></i>Zoom: ${map.getZoom()}`;
        }
    }

    // Add mouse move event to show coordinates
    map.on('mousemove', function(e) {
        const coords = document.getElementById('mapCoordinates');
        if (coords) {
            coords.innerHTML = `<i class="bi bi-crosshair me-1"></i>Lat: ${e.latlng.lat.toFixed(6)}, Lng: ${e.latlng.lng.toFixed(6)}`;
        }
    });

    // Add zoom events to update zoom level
    map.on('zoomend', updateMapInfo);
    
    // Initial zoom level display
    updateMapInfo();
    
    // Force map resize after a short delay to ensure proper rendering
    setTimeout(function() {
        map.invalidateSize();
    }, 100);
}

// Show status message using Bootstrap alerts
function showStatus(message, type = 'success') {
    const status = document.getElementById('status');
    const alertClass = type === 'error' ? 'alert-danger' : 'alert-success';
    const icon = type === 'error' ? 'bi-exclamation-triangle' : 'bi-check-circle';
    
    status.className = `alert ${alertClass} d-flex align-items-center`;
    status.innerHTML = `<i class="bi ${icon} me-2"></i>${message}`;
    status.classList.remove('d-none');
    
    setTimeout(() => {
        status.classList.add('d-none');
    }, 5000);
}

// Load incident data from API
async function loadIncidentData() {
    try {
        const response = await fetch(`/api/incident/${incidentId}`);
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        
        if (!data.success) {
            throw new Error(data.error || 'Failed to load incident data');
        }
        
        incidentData = data.incident;
        console.log('Incident data loaded:', incidentData); // Debug
        displayIncidentData();
        updateMap();
        loadUnits(); // Load units after incident data
        loadDivisions(); // Load divisions after incident data
        
    } catch (error) {
        console.error('Error loading incident data:', error); // Debug
        showStatus('Error loading incident data: ' + error.message, 'error');
        document.getElementById('loadingDiv').innerHTML = `
            <div class="alert alert-danger">
                <i class="bi bi-exclamation-triangle me-2"></i>Error loading incident data: ${error.message}
            </div>
        `;
    }
}

// Load units data
async function loadUnits() {
    try {
        const response = await fetch(`/api/incident/${incidentId}/units`);
        const data = await response.json();
        
        if (data.success && data.units) {
            unitsData = data.units;
            displayUnits(data.units);
            displayUnitsOnMap(data.units);
        } else {
            // No units yet
            document.getElementById('unitCount').textContent = '0';
        }
    } catch (error) {
        console.error('Error loading units:', error);
    }
}

// Display units list
function displayUnits(units) {
    const unitsList = document.getElementById('unitsList');
    const unitCount = document.getElementById('unitCount');
    
    if (!units || units.length === 0) {
        unitCount.textContent = '0';
        unitsList.innerHTML = `
            <div class="text-muted text-center py-4">
                <i class="bi bi-person-plus fs-1 text-muted mb-2"></i>
                <p>No units checked in yet.</p>
                <a href="/incident/${incidentId}/unit-checkin" class="btn btn-outline-primary">
                    Check In First Unit
                </a>
            </div>
        `;
        return;
    }
    
    unitCount.textContent = units.length;
    
    // Calculate total personnel
    const totalPersonnel = units.reduce((sum, unit) => sum + (unit.number_of_personnel || 0), 0);
    const bsarTechCount = units.filter(unit => unit.bsar_tech).length;
    
    unitsList.innerHTML = `
        <div class="row g-2 mb-3">
            <div class="col-4 text-center">
                <div class="fw-bold text-primary">${units.length}</div>
                <small class="text-muted">Units</small>
            </div>
            <div class="col-4 text-center">
                <div class="fw-bold text-success">${totalPersonnel}</div>
                <small class="text-muted">Personnel</small>
            </div>
            <div class="col-4 text-center">
                <div class="fw-bold text-info">${bsarTechCount}</div>
                <small class="text-muted">BSAR Tech</small>
            </div>
        </div>
        <div class="list-group list-group-flush">
            ${units.map(unit => `
                <div class="list-group-item px-0">
                    <div class="d-flex justify-content-between align-items-start">
                        <div class="flex-grow-1">
                            <div class="d-flex align-items-center mb-1">
                                <h6 class="mb-0 me-2">Unit ${unit.unit_id}</h6>
                                ${unit.bsar_tech ? '<span class="badge bg-info">BSAR Tech</span>' : ''}
                            </div>
                            <p class="mb-1 text-muted">
                                <strong>Officer:</strong> ${unit.unit_leader || 'Not specified'}<br>
                                <strong>Personnel:</strong> ${unit.number_of_personnel || 'Not specified'}<br>
                                ${unit.current_division_id ? `<strong>Division:</strong> ${unit.current_division_id}` : ''}
                            </p>
                            <small class="text-muted">
                                Checked in: ${unit.created_at ? new Date(unit.created_at).toLocaleString() : 'Unknown'}
                            </small>
                        </div>
                        <div class="text-end">
                            <button class="btn btn-sm btn-outline-primary me-1" 
                                    onclick="openUnitStatusModal('${unit.unit_id}')" 
                                    title="Update Status">
                                <i class="bi bi-pencil-square"></i>
                            </button>
                            <span class="badge bg-${getStatusBadgeClass(unit.current_status)}">${unit.current_status || 'staging'}</span>
                            <br>
                            <i class="bi bi-geo-alt-fill unit-status-online" title="Location available"></i>
                        </div>
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

// Open unit status update modal
async function openUnitStatusModal(unitId) {
    try {
        // Get current unit data
        const unit = unitsData.find(u => u.unit_id === unitId);
        if (!unit) {
            showStatus('Unit not found', 'error');
            return;
        }

        // Populate modal with current unit info
        document.getElementById('statusUnitId').textContent = unit.unit_id;
        document.getElementById('statusUnitName').textContent = unit.unit_name || unit.unit_id;
        document.getElementById('statusCurrentStatus').textContent = unit.current_status || 'staging';
        document.getElementById('statusCurrentDivision').textContent = unit.current_division_id || 'None';
        
        // Set current values
        document.getElementById('newStatus').value = unit.current_status || 'staging';
        document.getElementById('percentComplete').value = 0;
        document.getElementById('statusNotes').value = '';
        
        // Load available status options based on current status
        updateStatusOptions(unit.current_status || 'staging');
        
        // Load divisions for dropdown
        await loadDivisionsForStatusModal();
        
        // Set current division if assigned
        if (unit.current_division_id) {
            document.getElementById('divisionSelect').value = unit.current_division_id;
        }
        
        // Show modal
        const modal = new bootstrap.Modal(document.getElementById('unitStatusModal'));
        modal.show();
        
        // Store unit ID for form submission
        document.getElementById('unitStatusForm').dataset.unitId = unitId;
        
    } catch (error) {
        console.error('Error opening status modal:', error);
        showStatus('Error opening status modal', 'error');
    }
}

// Update status options based on current status
function updateStatusOptions(currentStatus) {
    const statusSelect = document.getElementById('newStatus');
    const divisionGroup = document.getElementById('divisionGroup');
    const percentGroup = document.getElementById('percentGroup');
    
    // Clear existing options
    statusSelect.innerHTML = '';
    
    let options = [];
    
    switch (currentStatus) {
        case 'assigned':
            options = [
                { value: 'assigned', text: 'Assigned', selected: true },
                { value: 'operating', text: 'Operating' },
                { value: 'recovering', text: 'Recovering' },
                { value: 'out of service', text: 'Out of Service' }
            ];
            divisionGroup.style.display = 'block';
            percentGroup.style.display = 'block';
            break;
            
        case 'operating':
            options = [
                { value: 'operating', text: 'Operating', selected: true },
                { value: 'recovering', text: 'Recovering' },
                { value: 'out of service', text: 'Out of Service' }
            ];
            divisionGroup.style.display = 'block';
            percentGroup.style.display = 'block';
            break;
            
        case 'recovering':
            options = [
                { value: 'recovering', text: 'Recovering', selected: true },
                { value: 'operating', text: 'Operating' },
                { value: 'staging', text: 'Staging' },
                { value: 'out of service', text: 'Out of Service' }
            ];
            divisionGroup.style.display = 'block';
            percentGroup.style.display = 'none';
            break;
            
        case 'out of service':
            options = [
                { value: 'out of service', text: 'Out of Service', selected: true },
                { value: 'staging', text: 'Staging' },
                { value: 'quarters', text: 'Quarters' }
            ];
            divisionGroup.style.display = 'none';
            percentGroup.style.display = 'none';
            break;
            
        case 'staging':
        default:
            options = [
                { value: 'staging', text: 'Staging', selected: true },
                { value: 'out of service', text: 'Out of Service' },
                { value: 'quarters', text: 'Quarters' }
            ];
            divisionGroup.style.display = 'none';
            percentGroup.style.display = 'none';
            break;
    }
    
    // Add options to select
    options.forEach(option => {
        const optionElement = document.createElement('option');
        optionElement.value = option.value;
        optionElement.textContent = option.text;
        if (option.selected) optionElement.selected = true;
        statusSelect.appendChild(optionElement);
    });
    
    // Update form visibility when status changes
    statusSelect.addEventListener('change', function() {
        const selectedStatus = this.value;
        if (['assigned', 'operating'].includes(selectedStatus)) {
            divisionGroup.style.display = 'block';
            percentGroup.style.display = 'block';
        } else if (selectedStatus === 'recovering') {
            divisionGroup.style.display = 'block';
            percentGroup.style.display = 'none';
        } else {
            divisionGroup.style.display = 'none';
            percentGroup.style.display = 'none';
        }
    });
}

// Load divisions for status modal
async function loadDivisionsForStatusModal() {
    try {
        const response = await fetch(`/api/incident/${incidentId}/divisions`);
        const data = await response.json();
        
        const divisionSelect = document.getElementById('divisionSelect');
        divisionSelect.innerHTML = '<option value="">Select Division...</option>';
        
        if (data.success && data.divisions) {
            data.divisions.forEach(division => {
                const option = document.createElement('option');
                option.value = division.division_id;
                option.textContent = `${division.division_name} (${division.status || 'unassigned'})`;
                divisionSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading divisions for status modal:', error);
    }
}

// Submit unit status update
async function submitUnitStatusUpdate() {
    try {
        const form = document.getElementById('unitStatusForm');
        const unitId = form.dataset.unitId;
        
        const formData = {
            incident_id: incidentId,
            status: document.getElementById('newStatus').value,
            division_id: document.getElementById('divisionSelect').value || null,
            percentage_complete: parseInt(document.getElementById('percentComplete').value) || 0,
            notes: document.getElementById('statusNotes').value || null,
            latitude: null, // TODO: Add location capture
            longitude: null
        };
        
        const response = await fetch(`/api/unit/${unitId}/status`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showStatus(`Unit ${unitId} status updated successfully`, 'success');
            
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('unitStatusModal'));
            modal.hide();
            
            // Refresh data
            loadUnits();
            loadDivisions();
        } else {
            showStatus(`Error updating status: ${data.error}`, 'error');
        }
        
    } catch (error) {
        console.error('Error submitting status update:', error);
        showStatus('Error submitting status update', 'error');
    }
}

// Display units on map
function displayUnitsOnMap(units) {
    if (!units || units.length === 0) return;
    
    unitsGroup.clearLayers();
    
    units.forEach((unit, index) => {
        if (unit.latitude && unit.longitude) {
            const unitMarker = L.marker([unit.latitude, unit.longitude], {
                icon: L.icon({
                    iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#0d6efd" width="32" height="32">
                            <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
                        </svg>
                    `),
                    iconSize: [32, 32],
                    iconAnchor: [16, 32]
                })
            }).addTo(unitsGroup);
            
            const popupContent = `
                <b>Unit ${unit.unit_id}</b><br>
                <strong>Officer:</strong> ${unit.unit_leader || 'Not specified'}<br>
                <strong>Personnel:</strong> ${unit.number_of_personnel || 'Not specified'}<br>
                <strong>BSAR Tech:</strong> ${unit.bsar_tech ? 'Yes' : 'No'}<br>
                <strong>Status:</strong> ${unit.current_status || 'staging'}<br>
                <strong>Checked in:</strong> ${unit.created_at ? new Date(unit.created_at).toLocaleString() : 'Unknown'}
            `;
            
            unitMarker.bindPopup(popupContent);
        }
    });
}

// Load hospital data
async function loadHospitalData() {
    if (!incidentData || !incidentData.latitude || !incidentData.longitude) {
        showStatus('Location data required for hospital search', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/hospitals/search', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                latitude: incidentData.latitude,
                longitude: incidentData.longitude
            })
        });
        
        const data = await response.json();
        
        if (data.success && data.hospitals) {
            displayHospitalData(data.hospitals);
        } else {
            document.getElementById('hospitalList').innerHTML = 'No hospital data available for this location.';
        }
        
        // Show the hospital alert
        document.getElementById('hospitalAlert').classList.remove('d-none');
        
    } catch (error) {
        document.getElementById('hospitalList').innerHTML = 'Error loading hospital data: ' + error.message;
        document.getElementById('hospitalAlert').classList.remove('d-none');
    }
}

// Display hospital data - FIXED VERSION
function displayHospitalData(hospitals) {
    const hospitalList = document.getElementById('hospitalList');
    
    if (!hospitals || Object.keys(hospitals).length === 0) {
        hospitalList.innerHTML = 'No hospitals found near this location.';
        return;
    }
    
    let hospitalsHtml = '<div class="row g-2">';
    
    // Handle the actual API response format
    Object.entries(hospitals).forEach(([level, hospitalData]) => {
        if (hospitalData && hospitalData.attributes) {
            const attrs = hospitalData.attributes;
            const distance = hospitalData.distance ? `${hospitalData.distance.toFixed(1)} km` : 'Distance unknown';
            
            let levelTitle = level.replace('_', ' ').toUpperCase();
            if (level === 'closest') levelTitle = 'CLOSEST HOSPITAL';
            
            hospitalsHtml += `
                <div class="col-md-6">
                    <h6 class="text-primary mb-2">${levelTitle}</h6>
                    <div class="card">
                        <div class="card-body">
                            <h6 class="card-title">${attrs.FACILITY || 'Unnamed facility'}</h6>
                            <div class="card-text">
                                <div><strong>Distance:</strong> <span class="text-muted">${distance}</span></div>
                                ${attrs.ADDRESS ? `<div><strong>Address:</strong> ${attrs.ADDRESS}</div>` : ''}
                                ${attrs.CITY ? `<div><strong>City:</strong> ${attrs.CITY}</div>` : ''}
                                ${attrs.PHONE ? `<div><strong>Phone:</strong> ${attrs.PHONE}</div>` : ''}
                                ${attrs.LIC_TYPE ? `<div><strong>Type:</strong> ${attrs.LIC_TYPE}</div>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        } else if (hospitalData === null) {
            let levelTitle = level.replace('_', ' ').toUpperCase();
            
            hospitalsHtml += `
                <div class="col-md-6">
                    <h6 class="text-warning mb-2">${levelTitle}</h6>
                    <div class="card border-warning">
                        <div class="card-body">
                            <p class="card-text text-muted">No ${levelTitle.toLowerCase()} found in the area.</p>
                        </div>
                    </div>
                </div>
            `;
        }
    });
    
    hospitalsHtml += '</div>';
    hospitalList.innerHTML = hospitalsHtml;
}

// Display incident data in the UI
function displayIncidentData() {
    if (!incidentData) return;
    
    // Update title
    document.getElementById('incidentTitle').textContent = incidentData.name || 'Unnamed Incident';
    
    // Update incident info
    const incidentInfo = document.getElementById('incidentInfo');
    const statusClass = incidentData.status === 'active' ? 'success' : 'secondary';
    incidentInfo.innerHTML = `
        <div class="row g-2">
            <div class="col-12">
                <strong>ID:</strong> <code class="bg-light px-2 py-1 rounded">${incidentData.incident_id}</code>
            </div>
            <div class="col-sm-6">
                <strong>Type:</strong> ${incidentData.incident_type || 'Unknown'}
            </div>
            <div class="col-sm-6">
                <strong>Status:</strong> <span class="badge bg-${statusClass}">${(incidentData.status || 'unknown').toUpperCase()}</span>
            </div>
            <div class="col-12">
                <strong>Created:</strong> ${incidentData.created_at ? new Date(incidentData.created_at).toLocaleString() : 'Unknown'}
            </div>
            ${incidentData.description ? `<div class="col-12"><strong>Description:</strong> <em>${incidentData.description}</em></div>` : ''}
        </div>
    `;
    
    // Update location info
    const locationInfo = document.getElementById('locationInfo');
    if (incidentData.latitude && incidentData.longitude) {
        locationInfo.innerHTML = `
            <div class="row g-2">
                <div class="col-12">
                    <strong>Address:</strong><br>
                    <span class="text-muted">${incidentData.address || 'Address not available'}</span>
                </div>
                <div class="col-12">
                    <strong>Coordinates:</strong><br>
                    <code class="bg-light px-2 py-1 rounded">${parseFloat(incidentData.latitude).toFixed(6)}, ${parseFloat(incidentData.longitude).toFixed(6)}</code>
                </div>
            </div>
        `;
    } else {
        locationInfo.innerHTML = '<div class="text-muted">Location not set</div>';
    }
    
    // Show content, hide loading
    document.getElementById('loadingDiv').classList.add('d-none');
    document.getElementById('incidentContent').classList.remove('d-none');
}

// Load divisions data
async function loadDivisions() {
    try {
        console.log('Loading divisions for incident:', incidentId); // Debug
        const response = await fetch(`/api/incident/${incidentId}/divisions`);
        console.log('Divisions response status:', response.status); // Debug
        
        const data = await response.json();
        console.log('Divisions data:', data); // Debug
        
        if (data.success && data.divisions && data.divisions.length > 0) {
            divisionsData = data.divisions;
            console.log('Divisions loaded:', divisionsData.length, 'divisions'); // Debug
            displayDivisions(data.divisions);
            displayDivisionsOnMap(data.divisions);
        } else {
            console.log('No divisions found'); // Debug
            document.getElementById('divisionsSummary').innerHTML = '<div class="text-muted">No search divisions created yet.</div>';
            document.getElementById('divisionsList').innerHTML = '';
        }
    } catch (error) {
        console.error('Error loading divisions:', error);
        document.getElementById('divisionsSummary').innerHTML = '<div class="text-muted">Error loading divisions data.</div>';
    }
}

// Display divisions on map
function displayDivisionsOnMap(divisions) {
    console.log('Displaying divisions on map:', divisions.length); // Debug
    if (!divisions || divisions.length === 0) return;
    
    divisionsGroup.clearLayers();
    
    divisions.forEach((division, index) => {
        console.log('Processing division:', division.division_id, division); // Debug
        
        const color = division.status === 'assigned' ? '#198754' : 
                     division.status === 'completed' ? '#17a2b8' : '#ffc107';
        
        let coordinates = null;
        
        // Parse coordinates from different possible formats
        if (division.coordinates) {
            console.log('Using division.coordinates'); // Debug
            coordinates = division.coordinates.map(coord => [coord[1], coord[0]]);
        } else if (division.area_coordinates) {
            console.log('Using division.area_coordinates'); // Debug
            coordinates = division.area_coordinates.map(coord => [coord[1], coord[0]]);
        } else if (division.geometry_geojson) {
            console.log('Using division.geometry_geojson'); // Debug
            try {
                const geom = typeof division.geometry_geojson === 'string' ? 
                    JSON.parse(division.geometry_geojson) : division.geometry_geojson;
                if (geom.coordinates && geom.coordinates[0]) {
                    coordinates = geom.coordinates[0].map(coord => [coord[1], coord[0]]);
                }
            } catch (e) {
                console.error('Error parsing division geometry_geojson:', e);
            }
        } else if (division.geom) {
            console.log('Using division.geom'); // Debug
            try {
                const geom = typeof division.geom === 'string' ? JSON.parse(division.geom) : division.geom;
                if (geom.coordinates && geom.coordinates[0]) {
                    coordinates = geom.coordinates[0].map(coord => [coord[1], coord[0]]);
                }
            } catch (e) {
                console.error('Error parsing division geometry:', e);
            }
        }
        
        console.log('Division coordinates:', coordinates); // Debug
        
        if (coordinates && coordinates.length > 0) {
            const divisionPolygon = L.polygon(coordinates, {
                color: color,
                weight: 2,
                fillOpacity: 0.4,
                fillColor: color
            }).addTo(divisionsGroup);
            
            // Add label in center of division - UPDATED FOR JUST LETTER
            const center = divisionPolygon.getBounds().getCenter();
            const divisionLetter = division.division_id ? division.division_id.replace('DIV-', '') : (division.name || 'X');
            const label = L.marker(center, {
                icon: L.divIcon({
                    className: 'division-label',
                    html: `<div style="background: white; border: 2px solid ${color}; border-radius: 50%; width: 30px; height: 30px; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px;">${divisionLetter}</div>`,
                    iconSize: [30, 30],
                    iconAnchor: [15, 15]
                })
            }).addTo(divisionsGroup);
            
            // UPDATED POPUP CONTENT WITH PERCENTAGE
            const percentage = division.percentage_complete || 0;
            const progressBar = percentage > 0 ? 
                `<div class="mt-2"><strong>Progress:</strong> ${percentage}%<br><div class="progress" style="height: 8px;"><div class="progress-bar ${getProgressBarClass(percentage)}" style="width: ${percentage}%;"></div></div></div>` : '';
            
            const popupContent = `
                <b>${division.division_name || division.name}</b><br>
                <strong>Priority:</strong> ${division.priority || 'Low'}<br>
                <strong>Status:</strong> ${(division.status || 'unassigned').toUpperCase()}<br>
                <strong>Unit:</strong> ${division.assigned_unit_id || 'Not assigned'}<br>
                <strong>Officer:</strong> ${division.team_leader || 'Not assigned'}
                ${progressBar}
            `;
            
            divisionPolygon.bindPopup(popupContent);
            label.bindPopup(popupContent);
            
            console.log('Added division polygon to map'); // Debug
        } else {
            console.log('No valid coordinates for division:', division.division_id); // Debug
        }
    });
    
    console.log('Total features in divisionsGroup:', divisionsGroup.getLayers().length); // Debug
}

// Display divisions with assignment controls
function displayDivisions(divisions) {
    if (!divisions || divisions.length === 0) {
        document.getElementById('divisionsSummary').innerHTML = '<div class="text-muted">No search divisions created yet.</div>';
        document.getElementById('divisionsList').innerHTML = '';
        return;
    }
    
    // Update divisions summary
    const summary = document.getElementById('divisionsSummary');
    const totalDivisions = divisions.length;
    const assignedDivisions = divisions.filter(d => d.status === 'assigned').length;
    const completedDivisions = divisions.filter(d => d.status === 'completed').length;
    const unassignedDivisions = totalDivisions - assignedDivisions - completedDivisions;
    
    // Calculate overall progress
    const totalProgress = divisions.reduce((sum, d) => sum + (d.percentage_complete || 0), 0);
    const averageProgress = divisions.length > 0 ? Math.round(totalProgress / divisions.length) : 0;
    
    summary.innerHTML = `
        <div class="row g-2">
            <div class="col-sm-2">
                <div class="text-center">
                    <div class="fs-4 fw-bold text-primary">${totalDivisions}</div>
                    <small class="text-muted">Total</small>
                </div>
            </div>
            <div class="col-sm-2">
                <div class="text-center">
                    <div class="fs-4 fw-bold text-success">${assignedDivisions}</div>
                    <small class="text-muted">Assigned</small>
                </div>
            </div>
            <div class="col-sm-2">
                <div class="text-center">
                    <div class="fs-4 fw-bold text-info">${completedDivisions}</div>
                    <small class="text-muted">Completed</small>
                </div>
            </div>
            <div class="col-sm-2">
                <div class="text-center">
                    <div class="fs-4 fw-bold text-warning">${unassignedDivisions}</div>
                    <small class="text-muted">Unassigned</small>
                </div>
            </div>
            <div class="col-sm-4">
                <div class="text-center">
                    <div class="fs-4 fw-bold text-secondary">${averageProgress}%</div>
                    <small class="text-muted">Overall Progress</small>
                    <div class="progress mt-1" style="height: 8px;">
                        <div class="progress-bar ${getProgressBarClass(averageProgress)}" style="width: ${averageProgress}%;"></div>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Display division cards with assignment controls
    const divisionsList = document.getElementById('divisionsList');
    divisionsList.innerHTML = divisions.map(division => {
        const statusClass = division.status === 'assigned' ? 'success' : 
                           division.status === 'completed' ? 'info' : 'warning';
        const borderClass = division.status === 'assigned' ? 'border-success' : 
                           division.status === 'completed' ? 'border-info' : 'border-warning';
        
        const priorityClass = division.priority === 'High' ? 'danger' :
                             division.priority === 'Medium' ? 'warning' : 'secondary';
        
        const percentage = division.percentage_complete || 0;
        const lastUpdate = division.last_update ? new Date(division.last_update).toLocaleString() : null;
        
        // Check if division is assigned to hide dropdowns
        const isAssigned = division.assigned_unit_id;
        
        return `
            <div class="col-md-6 col-lg-4">
                <div class="card h-100 ${borderClass}">
                    <div class="card-header">
                        <div class="d-flex justify-content-between align-items-center">
                            <div>
                                <h6 class="card-title mb-0">${division.division_name || division.name}</h6>
                                <small class="text-muted">${division.division_id}</small>
                            </div>
                            <span class="badge bg-${priorityClass}">${division.priority || 'Low'}</span>
                        </div>
                    </div>
                    <div class="card-body">
                        <div class="mb-2">
                            <span class="badge bg-${statusClass}">${(division.status || 'unassigned').toUpperCase()}</span>
                        </div>
                        
                        <!-- Progress Display -->
                        ${percentage > 0 ? `
                            <div class="mb-3">
                                <div class="d-flex justify-content-between align-items-center mb-1">
                                    <small class="text-muted">Progress</small>
                                    <small class="fw-bold">${percentage}%</small>
                                </div>
                                <div class="progress" style="height: 8px;">
                                    <div class="progress-bar ${getProgressBarClass(percentage)}" style="width: ${percentage}%;"></div>
                                </div>
                                ${lastUpdate ? `<small class="text-muted">Updated: ${lastUpdate}</small>` : ''}
                            </div>
                        ` : ''}
                        
                        <!-- Unit Assignment - Hidden when assigned -->
                        ${!isAssigned ? `
                            <div class="mb-3">
                                <label class="form-label small">Assigned Unit:</label>
                                <select class="form-select form-select-sm" 
                                        id="unit-select-${division.division_id}" 
                                        onchange="assignUnitToDivision('${division.division_id}', this.value)">
                                    <option value="">Select Unit...</option>
                                </select>
                            </div>
                        ` : ''}
                        
                        <!-- Priority Selection - Hidden when assigned -->
                        ${!isAssigned ? `
                            <div class="mb-3">
                                <label class="form-label small">Priority:</label>
                                <select class="form-select form-select-sm" 
                                        id="priority-select-${division.division_id}"
                                        onchange="updateDivisionPriority('${division.division_id}', this.value)">
                                    <option value="High" ${division.priority === 'High' ? 'selected' : ''}>High</option>
                                    <option value="Medium" ${division.priority === 'Medium' ? 'selected' : ''}>Medium</option>
                                    <option value="Low" ${division.priority === 'Low' ? 'selected' : ''}>Low</option>
                                </select>
                            </div>
                        ` : ''}
                        
                        <div class="small">
                            <div><strong>Team:</strong> ${division.assigned_team || '<em>Not assigned</em>'}</div>
                            ${division.team_leader ? `<div><strong>Leader:</strong> ${division.team_leader}</div>` : ''}
                            ${division.assigned_unit_id ? `<div><strong>Unit:</strong> ${division.assigned_unit_id}</div>` : ''}
                            ${division.unit_name ? `<div><strong>Unit Name:</strong> ${division.unit_name}</div>` : ''}
                            ${division.unit_leader ? `<div><strong>Unit Leader:</strong> ${division.unit_leader}</div>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    // Load available units for dropdowns (only for unassigned divisions)
    loadAvailableUnits();
}

// Load available units for assignment dropdowns
async function loadAvailableUnits() {
    try {
        const response = await fetch(`/api/incident/${incidentId}/available-units`);
        const data = await response.json();
        
        if (data.success && data.units) {
            // Update all unit dropdowns
            document.querySelectorAll('[id^="unit-select-"]').forEach(select => {
                const currentValue = select.value;
                
                // Clear existing options except first one
                select.innerHTML = '<option value="">Select Unit...</option>';
                
                // Add available units
                data.units.forEach(unit => {
                    const option = document.createElement('option');
                    option.value = unit.unit_id;
                    option.textContent = `${unit.unit_id} - ${unit.unit_name || unit.unit_type}`;
                    select.appendChild(option);
                });
                
                // Restore previous selection if still valid
                if (currentValue) {
                    select.value = currentValue;
                }
            });
        }
    } catch (error) {
        console.error('Error loading available units:', error);
    }
}

// Assign unit to division
async function assignUnitToDivision(divisionId, unitId) {
    if (!unitId) return;
    
    try {
        const response = await fetch(`/api/incident/${incidentId}/division/${divisionId}/assign-unit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                unit_id: unitId
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showStatus(`Unit ${unitId} assigned to division ${divisionId}`, 'success');
            // Reload divisions to reflect changes
            loadDivisions();
            loadUnits(); // Refresh units list
        } else {
            showStatus(`Error assigning unit: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error assigning unit to division:', error);
        showStatus('Error assigning unit to division', 'error');
    }
}

// Update division priority
async function updateDivisionPriority(divisionId, priority) {
    try {
        const response = await fetch(`/api/incident/${incidentId}/division/${divisionId}/priority`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                priority: priority
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showStatus(`Division ${divisionId} priority updated to ${priority}`, 'success');
            // Reload divisions to reflect changes
            loadDivisions();
        } else {
            showStatus(`Error updating priority: ${data.error}`, 'error');
        }
    } catch (error) {
        console.error('Error updating division priority:', error);
        showStatus('Error updating division priority', 'error');
    }
}

// Update map with incident data
function updateMap() {
    if (!incidentData) return;
    
    // Add incident location marker
    if (incidentData.latitude && incidentData.longitude) {
        if (incidentMarker) {
            map.removeLayer(incidentMarker);
        }
        
        const lat = parseFloat(incidentData.latitude);
        const lng = parseFloat(incidentData.longitude);
        
        incidentMarker = L.marker([lat, lng], {
            icon: L.icon({
                iconUrl: 'data:image/svg+xml;base64,' + btoa(`
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#dc3545" width="32" height="32">
                        <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
                    </svg>
                `),
                iconSize: [32, 32],
                iconAnchor: [16, 32]
            })
        }).addTo(map);
        
        incidentMarker.bindPopup(`<b>Incident Location</b><br>${incidentData.address || 'Location not geocoded'}`);
        
        // Set map view to incident location with appropriate zoom (use 15 like creation page)
        map.setView([lat, lng], 15);
    }
    
    // Add search area if available
    if (incidentData.search_area_coordinates) {
        searchAreaLayer.clearLayers();
        
        try {
            const coordinates = typeof incidentData.search_area_coordinates === 'string' 
                ? JSON.parse(incidentData.search_area_coordinates) 
                : incidentData.search_area_coordinates;
                
            if (coordinates && coordinates.length > 0) {
                const searchArea = L.polygon(
                    coordinates.map(coord => [coord[1], coord[0]]), // Convert lng,lat to lat,lng
                    {
                        color: '#dc3545', // Bootstrap danger color
                        weight: 3,
                        fillOpacity: 0.2,
                        fillColor: '#dc3545'
                    }
                ).addTo(searchAreaLayer);
                
                searchArea.bindPopup('<b>Search Area</b><br>Primary search zone');
                
                // Fit map to show both incident and search area with padding
                const group = new L.featureGroup([incidentMarker, searchArea]);
                map.fitBounds(group.getBounds().pad(0.1));
            }
        } catch (e) {
            console.error('Error parsing search area coordinates:', e);
        }
    }
    
    // Force map resize to ensure proper display
    setTimeout(() => {
        map.invalidateSize();
    }, 250);
}

// Center map on incident
function centerMap() {
    if (incidentData && incidentData.latitude && incidentData.longitude) {
        map.setView([parseFloat(incidentData.latitude), parseFloat(incidentData.longitude)], 15);
    }
}

// Toggle divisions visibility
function toggleDivisions() {
    const toggle = document.getElementById('divisionsToggle');
    divisionsVisible = toggle.checked;
    
    console.log('Toggle divisions:', divisionsVisible, 'Divisions group layers:', divisionsGroup.getLayers().length); // Debug
    
    if (divisionsVisible) {
        map.addLayer(divisionsGroup);
        console.log('Added divisions layer to map'); // Debug
    } else {
        map.removeLayer(divisionsGroup);
        console.log('Removed divisions layer from map'); // Debug
    }
}

// Refresh data
function refreshData() {
    showStatus('Refreshing incident data...', 'success');
    loadIncidentData();
}

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    loadIncidentData();
    
    // Event listeners
    document.getElementById('centerMapBtn').addEventListener('click', centerMap);
    document.getElementById('refreshBtn').addEventListener('click', refreshData);
    document.getElementById('showHospitalsBtn').addEventListener('click', loadHospitalData);
    document.getElementById('divisionsToggle').addEventListener('change', toggleDivisions);
    
    // Auto-refresh units every 30 seconds
    setInterval(loadUnits, 30000);
});
