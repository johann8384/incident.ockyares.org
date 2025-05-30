import React, { useState, useEffect } from 'react';
import { unitService } from '../services/api';
import UnitForm from './UnitForm';
import './UnitList.css';

const UnitList = ({ incidentId, onUnitSelect }) => {
  const [units, setUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [selectedUnit, setSelectedUnit] = useState(null);

  useEffect(() => {
    loadUnits();
  }, [incidentId]);

  const loadUnits = async () => {
    try {
      setLoading(true);
      const data = await unitService.getAll(incidentId);
      setUnits(data);
    } catch (err) {
      setError('Failed to load units: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUnit = () => {
    setSelectedUnit(null);
    setShowForm(true);
  };

  const handleEditUnit = (unit) => {
    setSelectedUnit(unit);
    setShowForm(true);
  };

  const handleDeleteUnit = async (unitId) => {
    if (window.confirm('Are you sure you want to delete this unit?')) {
      try {
        await unitService.delete(unitId);
        await loadUnits();
      } catch (err) {
        setError('Failed to delete unit: ' + err.message);
      }
    }
  };

  const handleFormClose = () => {
    setShowForm(false);
    setSelectedUnit(null);
    loadUnits();
  };

  const getStatusColor = (status) => {
    const colors = {
      'available': '#28a745',
      'en_route': '#ffc107',
      'on_scene': '#dc3545',
      'out_of_service': '#6c757d'
    };
    return colors[status] || '#6c757d';
  };

  const formatLastUpdate = (timestamp) => {
    if (!timestamp) return 'Never';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMinutes = Math.floor((now - date) / (1000 * 60));
    
    if (diffMinutes < 1) return 'Just now';
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffMinutes < 1440) return `${Math.floor(diffMinutes / 60)}h ago`;
    return date.toLocaleDateString();
  };

  if (loading) return <div className="loading">Loading units...</div>;
  if (error) return <div className="error">{error}</div>;

  return (
    <div className="unit-list">
      <div className="unit-list-header">
        <h2>Units</h2>
        <button className="btn btn-primary" onClick={handleCreateUnit}>
          Add Unit
        </button>
      </div>

      <div className="units-grid">
        {units.map(unit => (
          <div key={unit.unit_id} className="unit-card">
            <div className="unit-header">
              <div className="unit-info">
                <h3>{unit.unit_name || unit.unit_id}</h3>
                <span className="unit-type">{unit.unit_type}</span>
              </div>
              <div 
                className="status-indicator"
                style={{ backgroundColor: getStatusColor(unit.status) }}
                title={unit.status}
              />
            </div>

            {unit.unit_photo_url && (
              <img 
                src={unit.unit_photo_url} 
                alt={unit.unit_name}
                className="unit-photo"
              />
            )}

            <div className="unit-details">
              <div className="detail-row">
                <strong>Officer:</strong> {unit.officer_name}
              </div>
              
              {unit.current_address && (
                <div className="detail-row">
                  <strong>Location:</strong> {unit.current_address}
                </div>
              )}

              {unit.personnel && unit.personnel.length > 0 && (
                <div className="detail-row">
                  <strong>Personnel:</strong> {unit.personnel.length}
                  <div className="personnel-list">
                    {unit.personnel.map((person, idx) => (
                      <div key={idx} className="personnel-item">
                        {person.name} {person.role && `(${person.role})`}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="detail-row">
                <strong>Last Update:</strong> {formatLastUpdate(unit.updated_at)}
              </div>

              <div className="unit-actions">
                <button 
                  className="btn btn-sm btn-secondary"
                  onClick={() => handleEditUnit(unit)}
                >
                  Edit
                </button>
                <button 
                  className="btn btn-sm btn-info"
                  onClick={() => onUnitSelect && onUnitSelect(unit)}
                >
                  View Details
                </button>
                <button 
                  className="btn btn-sm btn-danger"
                  onClick={() => handleDeleteUnit(unit.unit_id)}
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      {units.length === 0 && (
        <div className="no-units">
          <p>No units found. Click "Add Unit" to create your first unit.</p>
        </div>
      )}

      {showForm && (
        <UnitForm
          unit={selectedUnit}
          incidentId={incidentId}
          onClose={handleFormClose}
        />
      )}
    </div>
  );
};

export default UnitList;
