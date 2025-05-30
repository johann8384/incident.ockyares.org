import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000';
const POSTGREST_URL = process.env.REACT_APP_POSTGREST_URL || 'http://localhost:3000';

function App() {
  const [incidents, setIncidents] = useState([]);
  const [backendStatus, setBackendStatus] = useState('checking...');
  const [postgrestStatus, setPostgrestStatus] = useState('checking...');
  const [newIncident, setNewIncident] = useState({
    name: '',
    description: '',
    latitude: 37.839333,
    longitude: -84.27277
  });

  useEffect(() => {
    checkBackendHealth();
    checkPostgrestHealth();
    fetchIncidents();
  }, []);

  const checkBackendHealth = async () => {
    try {
      const response = await axios.get(`${API_URL}/health`);
      setBackendStatus(`✅ ${response.data.status}`);
    } catch (error) {
      setBackendStatus('❌ offline');
    }
  };

  const checkPostgrestHealth = async () => {
    try {
      const response = await axios.get(`${POSTGREST_URL}/`);
      setPostgrestStatus('✅ connected');
    } catch (error) {
      setPostgrestStatus('❌ offline');
    }
  };

  const fetchIncidents = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/incidents`);
      setIncidents(response.data);
    } catch (error) {
      console.error('Error fetching incidents:', error);
    }
  };

  const createIncident = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API_URL}/api/incidents`, newIncident);
      setNewIncident({
        name: '',
        description: '',
        latitude: 37.839333,
        longitude: -84.27277
      });
      fetchIncidents(); // Refresh the list
    } catch (error) {
      console.error('Error creating incident:', error);
    }
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>🚨 Incident Management System</h1>
        <p>Fresh start with PostGIS, PostgREST, Flask, and React</p>
        
        <div className="status-panel">
          <h3>System Status</h3>
          <div>Flask Backend: {backendStatus}</div>
          <div>PostgREST API: {postgrestStatus}</div>
        </div>

        <div className="incident-form">
          <h3>Create New Incident</h3>
          <form onSubmit={createIncident}>
            <div>
              <input
                type="text"
                placeholder="Incident Name"
                value={newIncident.name}
                onChange={(e) => setNewIncident({...newIncident, name: e.target.value})}
                required
              />
            </div>
            <div>
              <textarea
                placeholder="Description"
                value={newIncident.description}
                onChange={(e) => setNewIncident({...newIncident, description: e.target.value})}
              />
            </div>
            <div>
              <input
                type="number"
                step="any"
                placeholder="Latitude"
                value={newIncident.latitude}
                onChange={(e) => setNewIncident({...newIncident, latitude: parseFloat(e.target.value)})}
              />
              <input
                type="number"
                step="any"
                placeholder="Longitude"
                value={newIncident.longitude}
                onChange={(e) => setNewIncident({...newIncident, longitude: parseFloat(e.target.value)})}
              />
            </div>
            <button type="submit">Create Incident</button>
          </form>
        </div>

        <div className="incidents-list">
          <h3>Recent Incidents ({incidents.length})</h3>
          {incidents.map(incident => (
            <div key={incident.id} className="incident-card">
              <h4>{incident.name}</h4>
              <p>{incident.description}</p>
              <p>📍 {incident.latitude}, {incident.longitude}</p>
              <small>Created: {new Date(incident.created_at).toLocaleString()}</small>
            </div>
          ))}
        </div>
      </header>
    </div>
  );
}

export default App;
