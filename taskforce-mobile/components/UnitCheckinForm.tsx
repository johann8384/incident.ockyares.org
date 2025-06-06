import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
  ScrollView,
  Switch,
  ActivityIndicator,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import * as Location from 'expo-location';

interface UnitCheckinFormProps {
  incidentId: string;
  onCheckinComplete: () => void;
  onBack: () => void;
}

interface FormData {
  unitId: string;
  companyOfficer: string;
  numberOfPersonnel: string;
  bsarTech: boolean;
  notes: string;
  latitude?: number;
  longitude?: number;
}

const API_BASE_URL = 'https://incident.ockyares.org'; // Update this to your server URL

export default function UnitCheckinForm({ incidentId, onCheckinComplete, onBack }: UnitCheckinFormProps) {
  const [formData, setFormData] = useState<FormData>({
    unitId: '',
    companyOfficer: '',
    numberOfPersonnel: '',
    bsarTech: false,
    notes: '',
  });
  const [loading, setLoading] = useState(false);
  const [locationLoading, setLocationLoading] = useState(false);
  const [locationStatus, setLocationStatus] = useState<string>('Not set');
  const [incidentInfo, setIncidentInfo] = useState<any>(null);

  useEffect(() => {
    fetchIncidentInfo();
  }, []);

  const fetchIncidentInfo = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/incident/${incidentId}`);
      if (response.ok) {
        const data = await response.json();
        if (data.success) {
          setIncidentInfo(data.incident);
        }
      }
    } catch (error) {
      console.log('Failed to fetch incident info:', error);
    }
  };

  const getCurrentLocation = async () => {
    setLocationLoading(true);
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      
      if (status !== 'granted') {
        Alert.alert('Permission Denied', 'Location permission is required to set unit location.');
        setLocationLoading(false);
        return;
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.High,
      });

      setFormData(prev => ({
        ...prev,
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
      }));

      setLocationStatus(`${location.coords.latitude.toFixed(6)}, ${location.coords.longitude.toFixed(6)}`);
    } catch (error) {
      Alert.alert('Error', 'Failed to get current location. Please try again.');
    } finally {
      setLocationLoading(false);
    }
  };

  const clearLocation = () => {
    setFormData(prev => ({
      ...prev,
      latitude: undefined,
      longitude: undefined,
    }));
    setLocationStatus('Not set');
  };

  const validateForm = (): boolean => {
    if (!formData.unitId.trim()) {
      Alert.alert('Validation Error', 'Unit ID is required');
      return false;
    }
    if (!formData.companyOfficer.trim()) {
      Alert.alert('Validation Error', 'Company Officer is required');
      return false;
    }
    if (!formData.numberOfPersonnel.trim() || isNaN(Number(formData.numberOfPersonnel)) || Number(formData.numberOfPersonnel) < 1) {
      Alert.alert('Validation Error', 'Please enter a valid number of personnel (1 or more)');
      return false;
    }
    return true;
  };

  const submitCheckin = async () => {
    if (!validateForm()) return;

    setLoading(true);
    try {
      const checkinData = {
        incident_id: incidentId,
        unit_id: formData.unitId.trim(),
        company_officer: formData.companyOfficer.trim(),
        number_of_personnel: parseInt(formData.numberOfPersonnel),
        bsar_tech: formData.bsarTech,
        notes: formData.notes.trim() || 'Unit checked in via mobile app',
        latitude: formData.latitude,
        longitude: formData.longitude,
      };

      const response = await fetch(`${API_BASE_URL}/api/unit/checkin`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(checkinData),
      });

      const result = await response.json();

      if (response.ok && result.success) {
        onCheckinComplete();
      } else {
        Alert.alert('Check-in Failed', result.error || 'Failed to check in unit. Please try again.');
      }
    } catch (error) {
      Alert.alert('Network Error', 'Failed to connect to server. Please check your internet connection and try again.');
    } finally {
      setLoading(false);
    }
  };

  const updateFormData = (field: keyof FormData, value: any) => {
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={onBack}>
          <Ionicons name="arrow-back" size={24} color="#007AFF" />
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Unit Check-in</Text>
      </View>

      <ScrollView style={styles.scrollContainer} showsVerticalScrollIndicator={false}>
        {/* Incident Info */}
        <View style={styles.incidentCard}>
          <Text style={styles.incidentTitle}>Incident: {incidentId}</Text>
          {incidentInfo && (
            <Text style={styles.incidentLocation}>
              Location: {incidentInfo.address || 'Location not available'}
            </Text>
          )}
        </View>

        {/* Form */}
        <View style={styles.formCard}>
          {/* Unit ID */}
          <View style={styles.formGroup}>
            <Text style={styles.label}>Unit ID *</Text>
            <TextInput
              style={styles.input}
              value={formData.unitId}
              onChangeText={(value) => updateFormData('unitId', value)}
              placeholder="e.g., 4534"
              placeholderTextColor="#999"
              autoCapitalize="none"
              autoCorrect={false}
            />
          </View>

          {/* Company Officer */}
          <View style={styles.formGroup}>
            <Text style={styles.label}>Company Officer *</Text>
            <TextInput
              style={styles.input}
              value={formData.companyOfficer}
              onChangeText={(value) => updateFormData('companyOfficer', value)}
              placeholder="e.g., Jones"
              placeholderTextColor="#999"
              autoCapitalize="words"
            />
          </View>

          {/* Number of Personnel */}
          <View style={styles.formGroup}>
            <Text style={styles.label}>Number of Personnel *</Text>
            <TextInput
              style={styles.input}
              value={formData.numberOfPersonnel}
              onChangeText={(value) => updateFormData('numberOfPersonnel', value)}
              placeholder="Enter number"
              placeholderTextColor="#999"
              keyboardType="numeric"
            />
          </View>

          {/* BSAR Tech */}
          <View style={styles.formGroup}>
            <View style={styles.switchRow}>
              <Text style={styles.label}>BSAR Tech</Text>
              <Switch
                value={formData.bsarTech}
                onValueChange={(value) => updateFormData('bsarTech', value)}
                trackColor={{ false: '#e9ecef', true: '#007AFF40' }}
                thumbColor={formData.bsarTech ? '#007AFF' : '#f4f3f4'}
              />
            </View>
          </View>

          {/* Location */}
          <View style={styles.formGroup}>
            <Text style={styles.label}>Current Location</Text>
            <View style={styles.locationControls}>
              <TouchableOpacity
                style={[styles.locationButton, locationLoading && styles.locationButtonDisabled]}
                onPress={getCurrentLocation}
                disabled={locationLoading}
              >
                {locationLoading ? (
                  <ActivityIndicator size="small" color="#007AFF" />
                ) : (
                  <Ionicons name="location" size={20} color="#007AFF" />
                )}
                <Text style={styles.locationButtonText}>
                  {locationLoading ? 'Getting Location...' : 'Get Current Location'}
                </Text>
              </TouchableOpacity>
              
              {formData.latitude && formData.longitude && (
                <TouchableOpacity style={styles.clearButton} onPress={clearLocation}>
                  <Ionicons name="close-circle" size={20} color="#dc3545" />
                  <Text style={styles.clearButtonText}>Clear</Text>
                </TouchableOpacity>
              )}
            </View>
            <Text style={styles.locationStatus}>
              {locationStatus}
            </Text>
          </View>

          {/* Notes */}
          <View style={styles.formGroup}>
            <Text style={styles.label}>Notes (Optional)</Text>
            <TextInput
              style={[styles.input, styles.textArea]}
              value={formData.notes}
              onChangeText={(value) => updateFormData('notes', value)}
              placeholder="Additional information..."
              placeholderTextColor="#999"
              multiline
              numberOfLines={3}
              textAlignVertical="top"
            />
          </View>
        </View>

        {/* Submit Button */}
        <TouchableOpacity
          style={[styles.submitButton, loading && styles.submitButtonDisabled]}
          onPress={submitCheckin}
          disabled={loading}
        >
          {loading ? (
            <>
              <ActivityIndicator size="small" color="white" />
              <Text style={styles.submitButtonText}>Checking In...</Text>
            </>
          ) : (
            <>
              <Ionicons name="checkmark-circle" size={20} color="white" />
              <Text style={styles.submitButtonText}>Check In Unit</Text>
            </>
          )}
        </TouchableOpacity>

        <View style={styles.bottomPadding} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#e9ecef',
  },
  backButton: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  backText: {
    fontSize: 16,
    color: '#007AFF',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    marginLeft: 24,
  },
  scrollContainer: {
    flex: 1,
  },
  incidentCard: {
    backgroundColor: '#e3f2fd',
    margin: 20,
    padding: 16,
    borderRadius: 12,
    borderLeftWidth: 4,
    borderLeftColor: '#2196f3',
  },
  incidentTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1976d2',
    marginBottom: 4,
  },
  incidentLocation: {
    fontSize: 14,
    color: '#666',
  },
  formCard: {
    backgroundColor: 'white',
    marginHorizontal: 20,
    padding: 20,
    borderRadius: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  formGroup: {
    marginBottom: 20,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 8,
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 12,
    fontSize: 16,
    backgroundColor: '#fff',
  },
  textArea: {
    height: 80,
    paddingTop: 12,
  },
  switchRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  locationControls: {
    flexDirection: 'row',
    gap: 12,
    marginBottom: 8,
  },
  locationButton: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f8f9fa',
    borderWidth: 1,
    borderColor: '#007AFF',
    borderRadius: 8,
    paddingVertical: 12,
    gap: 8,
  },
  locationButtonDisabled: {
    opacity: 0.6,
  },
  locationButtonText: {
    fontSize: 14,
    color: '#007AFF',
    fontWeight: '500',
  },
  clearButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#f8f9fa',
    borderWidth: 1,
    borderColor: '#dc3545',
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    gap: 4,
  },
  clearButtonText: {
    fontSize: 14,
    color: '#dc3545',
    fontWeight: '500',
  },
  locationStatus: {
    fontSize: 12,
    color: '#666',
    fontStyle: 'italic',
  },
  submitButton: {
    backgroundColor: '#007AFF',
    marginHorizontal: 20,
    marginTop: 20,
    borderRadius: 12,
    paddingVertical: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  submitButtonDisabled: {
    backgroundColor: '#ccc',
  },
  submitButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  bottomPadding: {
    height: 40,
  },
});
