// Common JavaScript functions shared across templates

// Common map initialization settings
const MAP_DEFAULTS = {
    defaultCenter: [38.3960874, -85.4425145], // Louisville, KY
    defaultZoom: 13,
    tileLayer: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '© OpenStreetMap contributors'
};

// Common status message function
function showStatus(message, type = 'success', elementId = 'status') {
    const status = document.getElementById(elementId);
    if (!status) return;
    
    const alertClass = type === 'error' ? 'alert-danger' : 'alert-success';
    const icon = type === 'error' ? 'bi-exclamation-triangle' : 'bi-check-circle';
    
    status.className = `alert ${alertClass} d-flex align-items-center`;
    status.innerHTML = `<i class="bi ${icon} me-2"></i>${message}`;
    status.classList.remove('d-none');
    
    setTimeout(() => {
        status.classList.add('d-none');
    }, 5000);
}

// Common alert function for floating alerts
function showAlert(message, type = 'success', containerId = 'alertContainer') {
    const alertContainer = document.getElementById(containerId);
    if (!alertContainer) {
        // Fallback to console if no container
        console.log(`${type.toUpperCase()}: ${message}`);
        return;
    }
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    alertContainer.appendChild(alert);
    
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

// Common map update functions
function updateMapInfo(map) {
    const zoomElement = document.getElementById('mapZoom');
    if (zoomElement && map) {
        zoomElement.innerHTML = `<i class="bi bi-zoom-in me-1"></i>Zoom: ${map.getZoom()}`;
    }
}

function setupMapCoordinateDisplay(map) {
    if (!map) return;
    
    // Add mouse move event to show coordinates
    map.on('mousemove', function(e) {
        const coords = document.getElementById('mapCoordinates');
        if (coords) {
            coords.innerHTML = `<i class="bi bi-crosshair me-1"></i>Lat: ${e.latlng.lat.toFixed(6)}, Lng: ${e.latlng.lng.toFixed(6)}`;
        }
    });

    // Add zoom events to update zoom level
    map.on('zoomend', () => updateMapInfo(map));
    
    // Initial zoom level display
    updateMapInfo(map);
}

// Common location handling
function getCurrentLocation(callback, errorCallback) {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            function(position) {
                callback(position.coords.latitude, position.coords.longitude);
            },
            function(error) {
                const message = 'Error getting location: ' + error.message;
                if (errorCallback) {
                    errorCallback(message);
                } else {
                    showAlert(message, 'danger');
                }
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 300000
            }
        );
    } else {
        const message = 'Geolocation is not supported by this browser.';
        if (errorCallback) {
            errorCallback(message);
        } else {
            showAlert(message, 'danger');
        }
    }
}

// Common marker creation functions
function createIncidentMarker(lat, lng, popupText = 'Incident Location') {
    const incidentIcon = L.icon({
        iconUrl: 'data:image/svg+xml;base64,' + btoa(`
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#dc3545" width="32" height="32">
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
            </svg>
        `),
        iconSize: [32, 32],
        iconAnchor: [16, 32]
    });
    
    return L.marker([lat, lng], { icon: incidentIcon }).bindPopup(popupText);
}

function createUnitMarker(lat, lng, popupText = 'Unit Location') {
    const unitIcon = L.icon({
        iconUrl: 'data:image/svg+xml;base64,' + btoa(`
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#0d6efd" width="32" height="32">
                <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
            </svg>
        `),
        iconSize: [32, 32],
        iconAnchor: [16, 32]
    });
    
    return L.marker([lat, lng], { icon: unitIcon }).bindPopup(popupText);
}

// Common form validation
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// Common API helper functions
async function apiCall(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        return data;
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

// Common utility functions
function formatCoordinates(lat, lng, precision = 6) {
    return `${parseFloat(lat).toFixed(precision)}, ${parseFloat(lng).toFixed(precision)}`;
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleString();
}

// Initialize common functionality
function initCommonFeatures() {
    // Force map resize after a short delay to ensure proper rendering
    setTimeout(function() {
        const maps = document.querySelectorAll('[id*="map"]');
        maps.forEach(mapElement => {
            if (window[mapElement.id] && window[mapElement.id].invalidateSize) {
                window[mapElement.id].invalidateSize();
            }
        });
    }, 100);
}