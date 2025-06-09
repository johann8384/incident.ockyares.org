import React, { useState, useEffect, useRef } from 'react';
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
  Dimensions,
} from 'react-native';
import { WebView } from 'react-native-webview';
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
  const incidentLat = params.incidentLat ? parseFloat(params.incidentLat as string) : null;
  const incidentLng = params.incidentLng ? parseFloat(params.incidentLng as string) : null;

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
  const [showMap, setShowMap] = useState(false);
  const webViewRef = useRef<WebView>(null);

  // Use different URLs for different platforms
  const getApiUrl = () => {
    if (Platform.OS === 'android') {
      return 'http://10.0.2.2'; // Android emulator special IP
    } else if (Platform.OS === 'ios') {
      return 'http://localhost'; // iOS simulator can use localhost
    } else {
      return 'http://localhost'; // Web/other platforms
    }
  };

  const API_BASE_URL = getApiUrl();

  // Generate the HTML for the map
  const generateMapHTML = () => {
    const defaultLat = incidentLat || 38.3960874; // Louisville, KY fallback
    const defaultLng = incidentLng || -85.4425145;
    const unitLat = formData.latitude || defaultLat;
    const unitLng = formData.longitude || defaultLng;

    return `
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
    <title>Unit Location Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" 
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY="
          crossorigin=""/>
    <style>
        body { margin: 0; padding: 0; }
        #map { height: 100vh; width: 100vw; }
        .map-controls {
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 1000;
            background: white;
            padding: 5px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }
        .control-btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 8px 12px;
            margin: 2px;
            border-radius: 4px;
            font-size: 12px;
            cursor: pointer;
        }
        .control-btn:hover {
            background: #0056b3;
        }
    </style>
</head>
<body>
    <div class="map-controls">
        <button class="control-btn" onclick="centerOnIncident()">📍 Incident</button>
        <button class="control-btn" onclick="getCurrentLocation()">📱 My Location</button>
        <button class="control-btn" onclick="setUnitLocation()">✅ Set Location</button>
    </div>
    <div id="map"></div>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo="
            crossorigin=""></script>
    <script>
        var map = L.map('map').setView([${defaultLat}, ${defaultLng}], 13);
        
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);

        // Incident marker (red)
        ${incidentLat && incidentLng ? `
        var incidentIcon = L.icon({
            iconUrl: 'data:image/svg+xml;base64,' + btoa(\`
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#dc3545" width="32" height="32">
                    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
                </svg>
            \`),
            iconSize: [32, 32],
            iconAnchor: [16, 32]
        });
        
        var incidentMarker = L.marker([${incidentLat}, ${incidentLng}], { icon: incidentIcon })
            .addTo(map)
            .bindPopup('<b>Incident Location</b><br>${incidentName}<br>${incidentAddress}');
        ` : ''}

        // Unit marker (blue) - draggable
        var unitIcon = L.icon({
            iconUrl: 'data:image/svg+xml;base64,' + btoa(\`
                <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="#0d6efd" width="32" height="32">
                    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/>
                </svg>
            \`),
            iconSize: [32, 32],
            iconAnchor: [16, 32]
        });

        var unitMarker = L.marker([${unitLat}, ${unitLng}], { 
            icon: unitIcon,
            draggable: true
        }).addTo(map).bindPopup('<b>Unit Location</b><br>Drag to set position');

        // Handle marker drag
        unitMarker.on('dragend', function(e) {
            var position = e.target.getLatLng();
            updateUnitLocation(position.lat, position.lng);
        });

        // Handle map click to set unit location
        map.on('click', function(e) {
            unitMarker.setLatLng(e.latlng);
            updateUnitLocation(e.latlng.lat, e.latlng.lng);
        });

        function updateUnitLocation(lat, lng) {
            // Send location back to React Native
            window.ReactNativeWebView.postMessage(JSON.stringify({
                type: 'locationUpdate',
                latitude: lat,
                longitude: lng
            }));
        }

        function centerOnIncident() {
            ${incidentLat && incidentLng ? `
            map.setView([${incidentLat}, ${incidentLng}], 15);
            ` : `
            alert('No incident location available');
            `}
        }

        function getCurrentLocation() {
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(function(position) {
                    var lat = position.coords.latitude;
                    var lng = position.coords.longitude;
                    unitMarker.setLatLng([lat, lng]);
                    map.setView([lat, lng], 16);
                    updateUnitLocation(lat, lng);
                }, function(error) {
                    alert('Error getting location: ' + error.message);
                });
            } else {
                alert('Geolocation is not supported');
            }
        }

        function setUnitLocation() {
            var position = unitMarker.getLatLng();
            window.ReactNativeWebView.postMessage(JSON.stringify({
                type: 'setLocation',
                latitude: position.lat,
                longitude: position.lng
            }));
        }

        // Fit map to show both markers if both exist
        ${incidentLat && incidentLng ? `
        if (${formData.latitude} && ${formData.longitude}) {
            var group = new L.featureGroup([incidentMarker, unitMarker]);
            map.fitBounds(group.getBounds().pad(0.1));
        }
        ` : ''}
    </script>
</body>
</html>
    `;
  };

  const handleWebViewMessage = (event: any) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      if (data.type === 'locationUpdate') {
        setFormData(prev => ({
          ...prev,
          latitude: data.latitude,
          longitude: data.longitude,
        }));
      } else if (data.type === 'setLocation') {
        setFormData(prev => ({
          ...prev,
          latitude: data.latitude,
          longitude: data.longitude,
        }));
        Alert.alert('Location Set', `Unit location set to: ${data.latitude.toFixed(6)}, ${data.longitude.toFixed(6)}`);
      }
    } catch (error) {
      console.error('Error parsing WebView message:', error);
    }
  };

  const getCurrentLocation = async () => {
    setLocationLoading(true);
    try {
      if (Platform.OS === 'web' || __DEV__) {
        // Fallback for web/emulator - simulate location
        setTimeout(() => {
          setFormData(prev => ({
            ...prev,
            latitude: incidentLat || 37.7749, // Use incident location or San Francisco as fallback
            longitude: incidentLng || -122.4194,
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

      console.log('Submitting to:', `${API_BASE_URL}/api/unit/checkin`);
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
                setShowMap(false);
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
      Alert.alert(
        'Connection Error', 
        `Failed to connect to server at ${API_BASE_URL}. Please check your connection.`
      );
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

  const toggleMap = () => {
    setShowMap(!showMap);
  };

  if (showMap) {
    return (
      <View style={styles.container}>
        <View style={styles.mapHeader}>
          <TouchableOpacity
            style={[styles.button, styles.secondaryButton]}
            onPress={toggleMap}
          >
            <Text style={styles.secondaryButtonText}>← Back to Form</Text>
          </TouchableOpacity>
          <Text style={styles.mapTitle}>Set Unit Location</Text>
          <Text style={styles.mapSubtitle}>Tap on map or drag blue marker</Text>
        </View>
        
        <WebView
          ref={webViewRef}
          source={{ html: generateMapHTML() }}
          style={styles.webView}
          onMessage={handleWebViewMessage}
          javaScriptEnabled={true}
          domStorageEnabled={true}
          geolocationEnabled={true}
          allowsInlineMediaPlayback={true}
          mediaPlaybackRequiresUserAction={false}
        />
        
        <View style={styles.mapFooter}>
          <Text style={styles.locationDisplay}>
            Current: {formatLocation()}
          </Text>
        </View>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container}>
      <ThemedView style={styles.header}>
        <ThemedText type="title">Unit Checkin</ThemedText>
        <ThemedText type="subtitle">Incident: {incidentName}</ThemedText>
        {incidentAddress && (
          <Text style={styles.incidentAddress}>📍 {incidentAddress}</Text>
        )}
        <Text style={styles.debugText}>API: {API_BASE_URL}</Text>
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
          <Text style={styles.label}>Unit Location</Text>
          
          <TouchableOpacity
            style={[styles.button, styles.mapButton]}
            onPress={toggleMap}
          >
            <Text style={styles.buttonText}>🗺️ Open Map to Set Location</Text>
          </TouchableOpacity>
          
          <View style={styles.locationControls}>
            <TouchableOpacity
              style={[styles.button, styles.primaryButton]}
              onPress={getCurrentLocation}
              disabled={locationLoading}
            >
              {locationLoading ? (
                <ActivityIndicator color="white" />
              ) : (
                <Text style={styles.buttonText}>📍 Use Current Location</Text>
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
            🔴 Red marker = Incident Location | 🔵 Blue marker = Unit Location
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
  debugText: {
    fontSize: 12,
    color: '#888',
    marginTop: 5,
    fontStyle: 'italic',
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
    marginTop: 10,
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
  mapButton: {
    backgroundColor: '#28a745',
    marginBottom: 10,
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
  // Map view styles
  mapHeader: {
    backgroundColor: 'white',
    padding: 15,
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  mapTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#333',
    textAlign: 'center',
    marginTop: 10,
  },
  mapSubtitle: {
    fontSize: 14,
    color: '#666',
    textAlign: 'center',
    marginTop: 5,
  },
  webView: {
    flex: 1,
  },
  mapFooter: {
    backgroundColor: 'white',
    padding: 15,
    borderTopWidth: 1,
    borderTopColor: '#e0e0e0',
  },
});
