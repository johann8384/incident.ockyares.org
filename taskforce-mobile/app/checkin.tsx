import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Alert,
  Switch,
  ActivityIndicator,
  Platform,
} from 'react-native';
import { router, useLocalSearchParams } from 'expo-router';
import { ThemedText } from '@/components/ThemedText';
import { ThemedView } from '@/components/ThemedView';

interface UnitCheckinData {
  unitId: string;
  companyOfficer: string;
  personnel: string;
  bsarTech: boolean;
  notes: string;
  latitude: number | null;
  longitude: number | null;
}

export default function UnitCheckinScreen() {
  const params = useLocalSearchParams();
  const incidentId = params.incidentId as string;
  const incidentName = params.incidentName as string;
  const incidentAddress = params.incidentAddress as string;

  const [formData, setFormData] = useState<UnitCheckinData>({
    unitId: '',
    companyOfficer: '',
    personnel: '',
    bsarTech: false,
    notes: '',
    latitude: null,
    longitude: null,
  });
  
  const [loading, setLoading] = useState(false);
  const [locationLoading, setLocationLoading] = useState(false);

  const API_BASE_URL = 'http://localhost:5000'; // TODO: Make configurable

  const getCurrentLocation = async () => {
    setLocationLoading(true);
    try {
      if (Platform.OS === 'web' || __DEV__) {
        // Fallback for web/emulator - simulate location
        setTimeout(() => {
          setFormData(prev => ({
            ...prev,
            latitude: 37.7749, // San Francisco coordinates as example
            longitude: -122.4194,
          }));
          Alert.alert('Success', 'Mock location set for testing');
          setLocationLoading(false);
        }, 1000);
        return;
      }

      // For actual device with native modules
      const Location = await import('expo-location');
      let { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') {
        Alert.alert('Permission denied', 'Location permission is required for unit checkin');
        return;
      }

      let location = await Location.getCurrentPositionAsync({});
      setFormData(prev => ({
        ...prev,
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
      }));
      
      Alert.alert('Success', 'Location captured successfully');
    } catch (error) {
      Alert.alert('Error', 'Failed to get current location');
    } finally {
      setLocationLoading(false);
    }
  };

  const clearLocation = () => {
    setFormData(prev => ({
      ...prev,
      latitude: null,
      longitude: null,
    }));
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
    if (!formData.personnel.trim() || parseInt(formData.personnel) < 1) {
      Alert.alert('Validation Error', 'Number of personnel must be at least 1');
      return false;
    }
    return true;
  };

  const handleSubmit = async () => {
    if (!validateForm()) return;

    setLoading(true);
    try {
      const checkinData = {
        incident_id: incidentId,
        unit_id: formData.unitId,
        company_officer: formData.companyOfficer,
        number_of_personnel: parseInt(formData.personnel),
        bsar_tech: formData.bsarTech,
        latitude: formData.latitude,
        longitude: formData.longitude,
        notes: formData.notes,
        unit_type: 'Field Unit', // Default value
      };

      const response = await fetch(`${API_BASE_URL}/api/unit/checkin`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(checkinData),
      });

      const result = await response.json();

      if (result.success) {
        Alert.alert(
          'Success',
          `Unit ${formData.unitId} has been successfully checked in.`,
          [
            {
              text: 'Check In Another Unit',
              onPress: () => {
                setFormData({
                  unitId: '',
                  companyOfficer: '',
                  personnel: '',
                  bsarTech: false,
                  notes: '',
                  latitude: null,
                  longitude: null,
                });
              }
            },
            {
              text: 'Back to Incidents',
              onPress: () => router.back()
            }
          ]
        );
      } else {
        Alert.alert('Error', result.error || 'Failed to check in unit');
      }
    } catch (error) {
      console.error('Checkin error:', error);
      Alert.alert('Error', 'Failed to connect to server. Please check your connection.');
    } finally {
      setLoading(false);
    }
  };

  const formatLocation = () => {
    if (formData.latitude && formData.longitude) {
      return `${formData.latitude.toFixed(6)}, ${formData.longitude.toFixed(6)}`;
    }
    return 'No location set';
  };

  return (
    <ScrollView style={styles.container}>
      <ThemedView style={styles.header}>
        <ThemedText type="title">Unit Checkin</ThemedText>
        <ThemedText type="subtitle">Incident: {incidentName}</ThemedText>
        {incidentAddress && (
          <Text style={styles.incidentAddress}>📍 {incidentAddress}</Text>
        )}
        {(__DEV__ || Platform.OS === 'web') && (
          <Text style={styles.devNote}>Development Mode: Using mock location</Text>
        )}
      </ThemedView>

      <ThemedView style={styles.form}>
        <View style={styles.inputGroup}>
          <Text style={styles.label}>Unit ID</Text>
          <TextInput
            style={styles.input}
            value={formData.unitId}
            onChangeText={(text) => setFormData(prev => ({ ...prev, unitId: text }))}
            placeholder="e.g., 4534"
            autoCapitalize="characters"
          />
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Company Officer</Text>
          <TextInput
            style={styles.input}
            value={formData.companyOfficer}
            onChangeText={(text) => setFormData(prev => ({ ...prev, companyOfficer: text }))}
            placeholder="e.g., Jones"
            autoCapitalize="words"
          />
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Number of Personnel</Text>
          <TextInput
            style={styles.input}
            value={formData.personnel}
            onChangeText={(text) => setFormData(prev => ({ ...prev, personnel: text }))}
            placeholder="1"
            keyboardType="numeric"
          />
        </View>

        <View style={styles.switchGroup}>
          <Text style={styles.label}>BSAR Tech</Text>
          <Switch
            value={formData.bsarTech}
            onValueChange={(value) => setFormData(prev => ({ ...prev, bsarTech: value }))}
          />
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Current Location</Text>
          <View style={styles.locationControls}>
            <TouchableOpacity
              style={[styles.button, styles.primaryButton]}
              onPress={getCurrentLocation}
              disabled={locationLoading}
            >
              {locationLoading ? (
                <ActivityIndicator color="white" />
              ) : (
                <Text style={styles.buttonText}>📍 Get Device Location</Text>
              )}
            </TouchableOpacity>
            
            <TouchableOpacity
              style={[styles.button, styles.secondaryButton]}
              onPress={clearLocation}
            >
              <Text style={styles.secondaryButtonText}>Clear Location</Text>
            </TouchableOpacity>
          </View>
          
          <Text style={styles.locationDisplay}>
            {formatLocation()}
          </Text>
          
          <Text style={styles.locationHelp}>
            🟢 Green marker = Incident Location | 🔵 Blue marker = Unit Location
          </Text>
        </View>

        <View style={styles.inputGroup}>
          <Text style={styles.label}>Notes (Optional)</Text>
          <TextInput
            style={[styles.input, styles.textArea]}
            value={formData.notes}
            onChangeText={(text) => setFormData(prev => ({ ...prev, notes: text }))}
            placeholder="Additional information..."
            multiline
            numberOfLines={3}
          />
        </View>

        <TouchableOpacity
          style={[styles.button, styles.submitButton]}
          onPress={handleSubmit}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color="white" />
          ) : (
            <Text style={styles.buttonText}>Check In Unit</Text>
          )}
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.button, styles.secondaryButton]}
          onPress={() => router.back()}
        >
          <Text style={styles.secondaryButtonText}>Back to Incidents</Text>
        </TouchableOpacity>
      </ThemedView>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  header: {
    padding: 20,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  incidentAddress: {
    fontSize: 14,
    color: '#666',
    marginTop: 4,
  },
  devNote: {
    fontSize: 12,
    color: '#ff6b35',
    fontStyle: 'italic',
    marginTop: 5,
  },
  form: {
    padding: 20,
  },
  inputGroup: {
    marginBottom: 20,
  },
  switchGroup: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 20,
    paddingVertical: 10,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
    color: '#333',
  },
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    backgroundColor: 'white',
  },
  textArea: {
    height: 80,
    textAlignVertical: 'top',
  },
  locationControls: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 10,
  },
  button: {
    flex: 1,
    padding: 12,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryButton: {
    backgroundColor: '#007bff',
  },
  secondaryButton: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: '#6c757d',
  },
  submitButton: {
    backgroundColor: '#007bff',
    marginBottom: 10,
  },
  buttonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
  secondaryButtonText: {
    color: '#6c757d',
    fontSize: 16,
    fontWeight: '600',
  },
  locationDisplay: {
    fontSize: 14,
    color: '#666',
    marginBottom: 5,
  },
  locationHelp: {
    fontSize: 12,
    color: '#888',
  },
});
