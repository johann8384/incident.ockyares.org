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

  const API_BASE_URL = 'http://localhost:5000'; // TODO: Make configurable

  const fetchIncidents = async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/incidents/active`);
      const data = await response.json();
      
      if (data.success) {
        setIncidents(data.incidents);
      } else {
        Alert.alert('Error', 'Failed to load incidents');
      }
    } catch (error) {
      console.error('Error fetching incidents:', error);
      Alert.alert('Error', 'Failed to connect to server');
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
        incidentAddress: incident.address 
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
      </ThemedView>
    );
  }

  return (
    <ThemedView style={styles.container}>
      <ThemedView style={styles.header}>
        <ThemedText type="title">Active Incidents</ThemedText>
        <ThemedText type="subtitle">Select an incident to check in</ThemedText>
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
    marginBottom: 8,
    lineHeight: 20,
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
