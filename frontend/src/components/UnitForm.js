import React, { useState, useEffect } from 'react';
import { unitService, personnelService } from '../services/api';
import './UnitForm.css';

const UnitForm = ({ unit, incidentId, onClose }) => {
  const [formData, setFormData] = useState({
    unit_id: '',
    unit_name: '',
    unit_type: 'Fire',
    officer_name: '',
    status: 'available',
    current_address: '',
    unit_photo_url: '',
    contact_info: { phone: '', radio: '' },
    capabilities: { equipment: [], specialties: [] },
    incident_id: incidentId || ''
  });

  const [personnel, setPersonnel] = useState([]);
  const [newPersonnel, setNewPersonnel] = useState({
    person_name: '',
    role: '',
    certification_level: ''
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const unitTypes = [
    'Fire', 'Police', 'EMS', 'SAR', 'Hazmat', 'Technical Rescue',
    'K9', 'Aviation', 'Marine', 'Command', 'Support', 'Other'
  ];

  const statusOptions = [
    'available', 'en_route', 'on_scene', 'out_of_service'
  ];

  useEffect(() => {
    if (unit) {
      setFormData({
        unit_id: unit.unit_id || '',
        unit_name: unit.unit_name || '',
        unit_type: unit.unit_type || 'Fire',
        officer_name: unit.officer_name || '',
        status: unit.status || 'available',
        current_address: unit.current_address || '',
        unit_photo_url: unit.unit_photo_url || '',
        contact_info: unit.contact_info || { phone: '', radio: '' },
        capabilities: unit.capabilities || { equipment: [], specialties: [] },
        incident_id: unit.incident_id || incidentId || ''
      });
      
      // Load existing personnel
      loadPersonnel(unit.unit_id);
    }
  }, [unit, incidentId]);

  const loadPersonnel = async (unitId) => {
    try {
      const data = await personnelService.getByUnit(unitId);
      setPersonnel(data);
    } catch (err) {
      console.error('Failed to load personnel:', err);
    }
  };

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleContactInfoChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      contact_info: {
        ...prev.contact_info,
        [field]: value
      }
    }));
  };

  const handleCapabilitiesChange = (field, value) => {
    const items = value.split(',').map(item => item.trim()).filter(item => item);
    setFormData(prev => ({
      ...prev,
      capabilities: {
        ...prev.capabilities,
        [field]: items
      }
    }));
  };

  const handleAddPersonnel = async () => {
    if (!newPersonnel.person_name.trim()) return;

    try {
      const personnelData = {
        ...newPersonnel,
        unit_id: formData.unit_id
      };
      
      await personnelService.add(personnelData);
      setNewPersonnel({ person_name: '', role: '', certification_level: '' });
      
      if (unit) {
        await loadPersonnel(unit.unit_id);
      }
    } catch (err) {
      setError('Failed to add personnel: ' + err.message);
    }
  };

  const handleRemovePersonnel = async (personnelId) => {
    try {
      await personnelService.remove(personnelId);
      if (unit) {
        await loadPersonnel(unit.unit_id);
      }
    } catch (err) {
      setError('Failed to remove personnel: ' + err.message);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (unit) {
        await unitService.update(unit.unit_id, formData);
      } else {
        // Generate unit ID if not provided
        if (!formData.unit_id) {
          const timestamp = Date.now().toString().slice(-6);
          const unitTypePrefix = formData.unit_type.substring(0, 3).toUpperCase();
          formData.unit_id = `${unitTypePrefix}${timestamp}`;
        }
        
        await unitService.create(formData);
      }
      
      onClose();
    } catch (err) {
      setError('Failed to save unit: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // In a real app, you'd upload to a storage service
    // For now, we'll use a placeholder URL
    const photoUrl = URL.createObjectURL(file);
    setFormData(prev => ({
      ...prev,
      unit_photo_url: photoUrl
    }));
  };

  return (
    <div className="modal-overlay">
      <div className="modal-content unit-form">
        <div className="modal-header">
          <h2>{unit ? 'Edit Unit' : 'Create New Unit'}</h2>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>

        {error && <div className="error">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <div className="form-group">
              <label>Unit ID:</label>
              <input
                type="text"
                name="unit_id"
                value={formData.unit_id}
                onChange={handleInputChange}
                placeholder="Auto-generated if empty"
              />
            </div>
            <div className="form-group">
              <label>Unit Name:</label>
              <input
                type="text"
                name="unit_name"
                value={formData.unit_name}
                onChange={handleInputChange}
                required
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Unit Type:</label>
              <select
                name="unit_type"
                value={formData.unit_type}
                onChange={handleInputChange}
                required
              >
                {unitTypes.map(type => (
                  <option key={type} value={type}>{type}</option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label>Status:</label>
              <select
                name="status"
                value={formData.status}
                onChange={handleInputChange}
              >
                {statusOptions.map(status => (
                  <option key={status} value={status}>
                    {status.replace('_', ' ').toUpperCase()}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="form-group">
            <label>Officer Name:</label>
            <input
              type="text"
              name="officer_name"
              value={formData.officer_name}
              onChange={handleInputChange}
              required
            />
          </div>

          <div className="form-group">
            <label>Current Address:</label>
            <input
              type="text"
              name="current_address"
              value={formData.current_address}
              onChange={handleInputChange}
              placeholder="Current location address"
            />
          </div>

          <div className="form-group">
            <label>Unit Photo:</label>
            <input
              type="file"
              accept="image/*"
              onChange={handleFileUpload}
            />
            {formData.unit_photo_url && (
              <img 
                src={formData.unit_photo_url} 
                alt="Unit preview"
                className="photo-preview"
              />
            )}
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Phone:</label>
              <input
                type="tel"
                value={formData.contact_info.phone}
                onChange={(e) => handleContactInfoChange('phone', e.target.value)}
                placeholder="Contact phone number"
              />
            </div>
            <div className="form-group">
              <label>Radio:</label>
              <input
                type="text"
                value={formData.contact_info.radio}
                onChange={(e) => handleContactInfoChange('radio', e.target.value)}
                placeholder="Radio call sign/frequency"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Equipment (comma separated):</label>
              <input
                type="text"
                value={formData.capabilities.equipment.join(', ')}
                onChange={(e) => handleCapabilitiesChange('equipment', e.target.value)}
                placeholder="Ladder, Hose, Medical kit, etc."
              />
            </div>
            <div className="form-group">
              <label>Specialties (comma separated):</label>
              <input
                type="text"
                value={formData.capabilities.specialties.join(', ')}
                onChange={(e) => handleCapabilitiesChange('specialties', e.target.value)}
                placeholder="Technical rescue, Hazmat, K9, etc."
              />
            </div>
          </div>

          {/* Personnel Management */}
          <div className="personnel-section">
            <h3>Personnel</h3>
            
            {personnel.length > 0 && (
              <div className="personnel-list">
                {personnel.map(person => (
                  <div key={person.id} className="personnel-item">
                    <span>{person.person_name}</span>
                    {person.role && <span className="role">({person.role})</span>}
                    {person.certification_level && (
                      <span className="cert">[{person.certification_level}]</span>
                    )}
                    <button
                      type="button"
                      onClick={() => handleRemovePersonnel(person.id)}
                      className="remove-btn"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}

            <div className="add-personnel">
              <h4>Add Personnel</h4>
              <div className="form-row">
                <input
                  type="text"
                  placeholder="Name"
                  value={newPersonnel.person_name}
                  onChange={(e) => setNewPersonnel(prev => ({
                    ...prev,
                    person_name: e.target.value
                  }))}
                />
                <input
                  type="text"
                  placeholder="Role"
                  value={newPersonnel.role}
                  onChange={(e) => setNewPersonnel(prev => ({
                    ...prev,
                    role: e.target.value
                  }))}
                />
                <input
                  type="text"
                  placeholder="Certification"
                  value={newPersonnel.certification_level}
                  onChange={(e) => setNewPersonnel(prev => ({
                    ...prev,
                    certification_level: e.target.value
                  }))}
                />
                <button type="button" onClick={handleAddPersonnel}>
                  Add
                </button>
              </div>
            </div>
          </div>

          <div className="form-actions">
            <button type="button" onClick={onClose} disabled={loading}>
              Cancel
            </button>
            <button type="submit" disabled={loading}>
              {loading ? 'Saving...' : (unit ? 'Update Unit' : 'Create Unit')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UnitForm;
