// Unit Status specific JavaScript
const incidentId = window.location.pathname.split('/').slice(-2)[0]; // Get incident ID from URL
let map, marker;

// Initialize map
function initMap() {
    map = L.map('map').setView(MAP_DEFAULTS.defaultCenter, MAP_DEFAULTS.defaultZoom);
    
    L.tileLayer(MAP_DEFAULTS.tileLayer, {
        attribution: MAP_DEFAULTS.attribution
    }).addTo(map);
    
    map.on('click', function(e) {
        updateMapLocation(e.latlng.lat, e.latlng.lng);
    });
}

function updateMapLocation(lat, lng) {
    document.getElementById('latitude').value = lat.toFixed(6);
    document.getElementById('longitude').value = lng.toFixed(6);
    
    if (marker) {
        map.removeLayer(marker);
    }
    marker = L.marker([lat, lng]).addTo(map);
    map.setView([lat, lng], 15);
}

// Load divisions for incident
async function loadDivisions() {
    try {
        const data = await apiCall(`/api/incident/${incidentId}/divisions`);
        
        const divisionSelect = document.getElementById('division');
        divisionSelect.innerHTML = '<option value="">Select Division</option>';
        
        if (data.divisions) {
            data.divisions.forEach(division => {
                const option = document.createElement('option');
                option.value = division.division_id;
                option.textContent = division.division_name;
                divisionSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading divisions:', error);
    }
}

// Status change handler
function handleStatusChange() {
    const status = document.getElementById('status').value;
    const divisionSection = document.getElementById('divisionSection');
    const percentageSection = document.getElementById('percentageSection');
    
    // Show division selection for assigned/operating/recovering
    if (['assigned', 'operating', 'recovering'].includes(status)) {
        divisionSection.style.display = 'block';
    } else {
        divisionSection.style.display = 'none';
    }
    
    // Show percentage for operating status
    if (status === 'operating') {
        percentageSection.style.display = 'block';
    } else {
        percentageSection.style.display = 'none';
    }
}

// Percentage slider handler
function handlePercentageChange() {
    const percentage = document.getElementById('percentage');
    document.getElementById('percentageValue').textContent = percentage.value + '%';
}

// Get current location
function handleGetCurrentLocation() {
    getCurrentLocation(
        updateMapLocation,
        (error) => showAlert(error, 'danger')
    );
}

// Form submission
async function handleFormSubmission(e) {
    e.preventDefault();
    
    const formData = {
        incident_id: incidentId,
        status: document.getElementById('status').value,
        division_id: document.getElementById('division').value || null,
        percentage_complete: document.getElementById('percentage').value,
        latitude: document.getElementById('latitude').value || null,
        longitude: document.getElementById('longitude').value || null,
        notes: document.getElementById('notes').value,
        user_name: document.getElementById('userName').value
    };

    try {
        const unitId = document.getElementById('unitId').value;
        await apiCall(`/api/unit/${unitId}/status`, {
            method: 'POST',
            body: JSON.stringify(formData)
        });
        
        showAlert('Status updated successfully', 'success');
        loadStatusHistory();
        
    } catch (error) {
        showAlert('Error updating status: ' + error.message, 'danger');
    }
}

// Load status history
async function loadStatusHistory() {
    const unitId = document.getElementById('unitId').value;
    if (!unitId) return;

    try {
        const data = await apiCall(`/api/unit/${unitId}/history?incident_id=${incidentId}`);
        
        if (data.history && data.history.length > 0) {
            const historyList = document.getElementById('historyList');
            historyList.innerHTML = '';
            
            data.history.forEach(entry => {
                const historyItem = document.createElement('div');
                historyItem.className = 'border-bottom pb-2 mb-2';
                historyItem.innerHTML = `
                    <div class="d-flex justify-content-between">
                        <strong>${entry.status.replace('_', ' ').toUpperCase()}</strong>
                        <small class="text-muted">${formatDate(entry.timestamp)}</small>
                    </div>
                    ${entry.division_name ? `<div>Division: ${entry.division_name}</div>` : ''}
                    ${entry.percentage_complete > 0 ? `<div>Progress: ${entry.percentage_complete}%</div>` : ''}
                    ${entry.notes ? `<div class="text-muted">${entry.notes}</div>` : ''}
                `;
                historyList.appendChild(historyItem);
            });
            
            document.getElementById('statusHistory').style.display = 'block';
        }
    } catch (error) {
        console.error('Error loading status history:', error);
    }
}

// Unit ID change handler
function handleUnitIdChange() {
    const unitId = document.getElementById('unitId').value;
    if (unitId) {
        loadStatusHistory();
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    initCommonFeatures();
    loadDivisions();
    
    // Event listeners
    document.getElementById('status').addEventListener('change', handleStatusChange);
    document.getElementById('percentage').addEventListener('input', handlePercentageChange);
    document.getElementById('getCurrentLocation').addEventListener('click', handleGetCurrentLocation);
    document.getElementById('statusForm').addEventListener('submit', handleFormSubmission);
    document.getElementById('unitId').addEventListener('blur', handleUnitIdChange);
});