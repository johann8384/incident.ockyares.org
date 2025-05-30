// PostgREST API service for units
import axios from 'axios';

// Use nginx proxy paths instead of direct ports
const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

// Create axios instance with default config for PostgREST
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  }
});

// Add request interceptor for debugging in development
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

// Unit API services
export const unitService = {
  // Get all units
  getAll: async (incidentId = null) => {
    const params = incidentId ? `?incident_id=eq.${incidentId}` : '';
    const response = await api.get(`/unit_checkin_view${params}`);
    return response.data;
  },

  // Get unit by ID
  getById: async (unitId) => {
    const response = await api.get(`/unit_checkin_view?unit_id=eq.${unitId}`);
    return response.data[0];
  },

  // Create new unit
  create: async (unitData) => {
    const response = await api.post('/units', unitData, {
      headers: { 'Prefer': 'return=representation' }
    });
    return response.data[0];
  },

  // Update unit
  update: async (unitId, unitData) => {
    const response = await api.patch(`/units?unit_id=eq.${unitId}`, unitData, {
      headers: { 'Prefer': 'return=representation' }
    });
    return response.data[0];
  },

  // Delete unit
  delete: async (unitId) => {
    await api.delete(`/units?unit_id=eq.${unitId}`);
  },

  // Update unit location using the stored function
  updateLocation: async (unitId, locationData) => {
    const response = await api.post('/rpc/update_unit_location', {
      p_unit_id: unitId,
      p_latitude: locationData.latitude,
      p_longitude: locationData.longitude,
      p_address: locationData.address,
      p_status: locationData.status,
      p_incident_id: locationData.incident_id,
      p_notes: locationData.notes
    });
    return response.data;
  }
};

// Personnel API services
export const personnelService = {
  // Get personnel for a unit
  getByUnit: async (unitId) => {
    const response = await api.get(`/unit_personnel?unit_id=eq.${unitId}`);
    return response.data;
  },

  // Add personnel to unit
  add: async (personnelData) => {
    const response = await api.post('/unit_personnel', personnelData, {
      headers: { 'Prefer': 'return=representation' }
    });
    return response.data[0];
  },

  // Update personnel
  update: async (personnelId, personnelData) => {
    const response = await api.patch(`/unit_personnel?id=eq.${personnelId}`, personnelData, {
      headers: { 'Prefer': 'return=representation' }
    });
    return response.data[0];
  },

  // Remove personnel
  remove: async (personnelId) => {
    await api.delete(`/unit_personnel?id=eq.${personnelId}`);
  }
};

// Check-in API services
export const checkinService = {
  // Get check-ins for a unit
  getByUnit: async (unitId) => {
    const response = await api.get(`/unit_check_ins?unit_id=eq.${unitId}&order=check_in_time.desc`);
    return response.data;
  },

  // Create check-in
  create: async (checkinData) => {
    const response = await api.post('/unit_check_ins', checkinData, {
      headers: { 'Prefer': 'return=representation' }
    });
    return response.data[0];
  }
};

export default api;
