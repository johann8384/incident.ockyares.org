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