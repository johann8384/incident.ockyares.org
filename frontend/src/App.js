import React, { useState } from 'react';
import UnitList from './components/UnitList';
import './App.css';

function App() {
  const [selectedIncident] = useState('USR202501301234'); // Demo incident ID
  const [selectedUnit, setSelectedUnit] = useState(null);

  const handleUnitSelect = (unit) => {
    setSelectedUnit(unit);
    console.log('Selected unit:', unit);
  };

  return (
    <div className="App">
      <header className="app-header">
        <h1>Emergency Incident Management</h1>
        <p>Unit Management System</p>
      </header>

      <main className="app-main">
        <UnitList 
          incidentId={selectedIncident}
          onUnitSelect={handleUnitSelect}
        />
        
        {selectedUnit && (
          <div className="unit-details-panel">
            <h3>Selected Unit: {selectedUnit.unit_name}</h3>
            <p>Officer: {selectedUnit.officer_name}</p>
            <p>Status: {selectedUnit.status}</p>
            <p>Location: {selectedUnit.current_address || 'Not set'}</p>
            <button onClick={() => setSelectedUnit(null)}>
              Close Details
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
