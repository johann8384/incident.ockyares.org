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

// Load divisions for specific unit
async function loadDivisionsForUnit(unitId) {
    if (!unitId) {
        // Clear division select if no unit ID
        const divisionSelect = document.getElementById('division');
        divisionSelect.innerHTML = '<option value="">Select Division</option>';
        return;
    }

    try {
        const data = await apiCall(`/api/unit/${unitId}/divisions?incident_id=${incidentId}`);
        
        const divisionSelect = document.getElementById('division');
        divisionSelect.innerHTML = '<option value="">Select Division</option>';
        
        if (data.divisions) {
            data.divisions.forEach(division => {
                const option = document.createElement('option');
                option.value = division.division_id;
                
                // Show division name with status indicator
                let displayText = division.division_name;
                if (division.is_assigned_to_unit) {
                    displayText += ' (Currently Assigned)';
                    option.selected = true; // Auto-select currently assigned division
                } else if (division.assigned_unit_id) {
                    displayText += ` (Assigned to ${division.assigned_unit_id})`;
                    option.disabled = true; // Disable divisions assigned to other units
                } else {
                    displayText += ' (Available)';
                }
                
                if (division.priority && division.priority !== 'Medium') {
                    displayText += ` [${division.priority}]`;
                }
                
                option.textContent = displayText;
                divisionSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error loading divisions for unit:', error);
        showAlert('Error loading divisions: ' + error.message, 'warning');
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
        
        // Reload divisions for current unit when division section becomes visible
        const unitId = document.getElementById('unitId').value;
        if (unitId) {
            loadDivisionsForUnit(unitId);
        }
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

// Percentage slider handler with completion warning
function handlePercentageChange() {
    const percentage = document.getElementById('percentage');
    const percentageValue = document.getElementById('percentageValue');
    const status = document.getElementById('status').value;
    
    percentageValue.textContent = percentage.value + '%';
    
    // Show warning when approaching 100% completion
    if (percentage.value == 100 && status === 'operating') {
        percentageValue.innerHTML = percentage.value + '% <small class="text-warning">(Will auto-transition to Recovering)</small>';
    }
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
    
    const percentage = parseInt(document.getElementById('percentage').value);
    const currentStatus = document.getElementById('status').value;
    
    // Warn user about 100% completion auto-transition
    if (percentage === 100 && currentStatus === 'operating') {
        const confirmed = confirm(
            'Setting progress to 100% will automatically:\n' +
            '• Mark the division as COMPLETED\n' +
            '• Change your unit status to RECOVERING\n' +
            '• Unassign you from the division\n\n' +
            'Do you want to continue?'
        );
        
        if (!confirmed) {
            return;
        }
    }
    
    const formData = {
        incident_id: incidentId,
        status: currentStatus,
        division_id: document.getElementById('division').value || null,
        percentage_complete: percentage,
        latitude: document.getElementById('latitude').value || null,
        longitude: document.getElementById('longitude').value || null,
        notes: document.getElementById('notes').value,
        user_name: document.getElementById('userName').value
    };

    try {
        const unitId = document.getElementById('unitId').value;
        const response = await apiCall(`/api/unit/${unitId}/status`, {
            method: 'POST',
            body: JSON.stringify(formData)
        });
        
        // Show appropriate success message
        let message = 'Status updated successfully';
        if (response.auto_transitioned) {
            message = 'Division completed! Unit automatically transitioned to Recovering status.';
            
            // Update the form to reflect the new status
            document.getElementById('status').value = response.new_status;
            document.getElementById('percentage').value = 0;
            handleStatusChange(); // Refresh UI sections
            handlePercentageChange(); // Reset percentage display
            
            showAlert(message, 'success');
        } else {
            showAlert(message, 'success');
        }
        
        loadStatusHistory();
        
        // Reload divisions after status update in case assignments changed
        loadDivisionsForUnit(unitId);
        
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
                
                // Add special styling for completion entries
                let statusClass = '';
                let statusText = entry.status.replace('_', ' ').toUpperCase();
                if (entry.percentage_complete === 100) {
                    statusClass = 'text-success fw-bold';
                    statusText += ' (DIVISION COMPLETED)';
                } else if (entry.status === 'recovering') {
                    statusClass = 'text-info';
                }
                
                historyItem.innerHTML = `
                    <div class="d-flex justify-content-between">
                        <strong class="${statusClass}">${statusText}</strong>
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
        
        // Load divisions for this specific unit
        const status = document.getElementById('status').value;
        if (['assigned', 'operating', 'recovering'].includes(status)) {
            loadDivisionsForUnit(unitId);
        }
    } else {
        // Clear divisions if no unit ID
        loadDivisionsForUnit(null);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initMap();
    initCommonFeatures();
    
    // Event listeners
    document.getElementById('status').addEventListener('change', handleStatusChange);
    document.getElementById('percentage').addEventListener('input', handlePercentageChange);
    document.getElementById('getCurrentLocation').addEventListener('click', handleGetCurrentLocation);
    document.getElementById('statusForm').addEventListener('submit', handleFormSubmission);
    document.getElementById('unitId').addEventListener('blur', handleUnitIdChange);
    document.getElementById('unitId').addEventListener('input', handleUnitIdChange); // Also trigger on input for real-time updates
});
