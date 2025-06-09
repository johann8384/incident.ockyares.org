import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
  RefreshControl,
  Platform,
} from 'react-native';
import { router } from 'expo-router';
import { ThemedText } from '@/components/ThemedText';
import { ThemedView } from '@/components/ThemedView';

interface Incident {
  incident_id: string;
  name: string;
  incident_type: string;
  description: string;
  address: string;
  status: string;
  created_at: string;
  latitude: number;
  longitude: number;
}

export default function IncidentListScreen() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

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

  const fetchIncidents = async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      console.log('Fetching from:', `${API_BASE_URL}/api/incidents/active`);
      const response = await fetch(`${API_BASE_URL}/api/incidents/active`);
      const data = await response.json();
      
      if (data.success) {
        setIncidents(data.incidents);
      } else {
        Alert.alert('Error', 'Failed to load incidents');
      }
    } catch (error) {
      console.error('Error fetching incidents:', error);
      Alert.alert(
        'Connection Error', 
        `Failed to connect to server at ${API_BASE_URL}. Make sure the Flask app is running.`
      );
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, []);

  const onRefresh = () => {
    fetchIncidents(true);
  };

  const handleIncidentSelect = (incident: Incident) => {
    router.push({
      pathname: '/checkin',
      params: { 
        incidentId: incident.incident_id,
        incidentName: incident.name,
        incidentAddress: incident.address,
        incidentLat: incident.latitude?.toString() || '',
        incidentLng: incident.longitude?.toString() || ''
      }
    });
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const formatLocation = (lat: number, lng: number) => {
    if (lat && lng) {
      return `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
    }
    return 'No location';
  };

  const renderIncident = ({ item }: { item: Incident }) => (
    <TouchableOpacity
      style={styles.incidentCard}
      onPress={() => handleIncidentSelect(item)}
    >
      <View style={styles.cardHeader}>
        <Text style={styles.incidentName}>{item.name}</Text>
        <View style={styles.statusBadge}>
          <Text style={styles.statusText}>{item.status}</Text>
        </View>
      </View>
      
      <Text style={styles.incidentType}>{item.incident_type}</Text>
      
      {item.address && (
        <Text style={styles.address} numberOfLines={2}>
          📍 {item.address}
        </Text>
      )}

      {item.latitude && item.longitude && (
        <Text style={styles.coordinates}>
          🌐 {formatLocation(item.latitude, item.longitude)}
        </Text>
      )}
      
      <Text style={styles.date}>
        Created: {formatDate(item.created_at)}
      </Text>
      
      {item.description && (
        <Text style={styles.description} numberOfLines={2}>
          {item.description}
        </Text>
      )}
    </TouchableOpacity>
  );

  if (loading) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator size="large" color="#007bff" />
        <ThemedText style={styles.loadingText}>Loading incidents...</ThemedText>
        <Text style={styles.debugText}>Connecting to: {API_BASE_URL}</Text>
      </ThemedView>
    );
  }

  return (
    <ThemedView style={styles.container}>
      <ThemedView style={styles.header}>
        <ThemedText type="title">Active Incidents</ThemedText>
        <ThemedText type="subtitle">Select an incident to check in</ThemedText>
        <Text style={styles.debugText}>API: {API_BASE_URL}</Text>
      </ThemedView>

      {incidents.length === 0 ? (
        <View style={styles.emptyState}>
          <Text style={styles.emptyText}>No active incidents found</Text>
          <TouchableOpacity style={styles.refreshButton} onPress={() => fetchIncidents()}>
            <Text style={styles.refreshButtonText}>Refresh</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <FlatList
          data={incidents}
          keyExtractor={(item) => item.incident_id}
          renderItem={renderIncident}
          style={styles.list}
          contentContainerStyle={styles.listContent}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          }
        />
      )}
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f5f5f5',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  header: {
    padding: 20,
    backgroundColor: 'white',
    borderBottomWidth: 1,
    borderBottomColor: '#e0e0e0',
  },
  loadingText: {
    marginTop: 10,
    fontSize: 16,
    color: '#666',
  },
  debugText: {
    fontSize: 12,
    color: '#888',
    marginTop: 5,
    fontStyle: 'italic',
  },
  list: {
    flex: 1,
  },
  listContent: {
    padding: 16,
  },
  incidentCard: {
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: '#e0e0e0',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  incidentName: {
    fontSize: 18,
    fontWeight: '600',
    color: '#333',
    flex: 1,
  },
  statusBadge: {
    backgroundColor: '#28a745',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusText: {
    color: 'white',
    fontSize: 12,
    fontWeight: '600',
  },
  incidentType: {
    fontSize: 14,
    fontWeight: '500',
    color: '#007bff',
    marginBottom: 8,
  },
  address: {
    fontSize: 14,
    color: '#666',
    marginBottom: 6,
    lineHeight: 20,
  },
  coordinates: {
    fontSize: 12,
    color: '#888',
    marginBottom: 8,
    fontFamily: 'monospace',
  },
  date: {
    fontSize: 12,
    color: '#888',
    marginBottom: 8,
  },
  description: {
    fontSize: 14,
    color: '#555',
    lineHeight: 20,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 40,
  },
  emptyText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    marginBottom: 20,
  },
  refreshButton: {
    backgroundColor: '#007bff',
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
  },
  refreshButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
});
