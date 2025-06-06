import React, { useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TextInput,
  TouchableOpacity,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface ManualIncidentEntryProps {
  onSubmit: (incidentId: string) => void;
  onBack: () => void;
}

export default function ManualIncidentEntry({ onSubmit, onBack }: ManualIncidentEntryProps) {
  const [incidentId, setIncidentId] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!incidentId.trim()) {
      Alert.alert('Error', 'Please enter an incident ID');
      return;
    }

    setLoading(true);

    try {
      // Validate incident ID format (you can adjust this validation as needed)
      const trimmedId = incidentId.trim();
      
      // Basic validation - ensure it's not empty and contains valid characters
      if (!/^[a-zA-Z0-9-_]+$/.test(trimmedId)) {
        Alert.alert('Invalid Format', 'Incident ID contains invalid characters');
        setLoading(false);
        return;
      }

      onSubmit(trimmedId);
    } catch (error) {
      Alert.alert('Error', 'Failed to validate incident ID');
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity style={styles.backButton} onPress={onBack}>
          <Ionicons name="arrow-back" size={24} color="#007AFF" />
          <Text style={styles.backText}>Back</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Enter Incident ID</Text>
      </View>

      {/* Content */}
      <View style={styles.content}>
        <View style={styles.card}>
          <Text style={styles.label}>Incident ID</Text>
          <TextInput
            style={styles.input}
            value={incidentId}
            onChangeText={setIncidentId}
            placeholder="e.g., INC-2025-001"
            placeholderTextColor="#999"
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="done"
            onSubmitEditing={handleSubmit}
          />
          
          <Text style={styles.helpText}>
            Enter the incident ID exactly as shown on the incident dashboard
          </Text>

          <TouchableOpacity
            style={[styles.submitButton, loading && styles.submitButtonDisabled]}
            onPress={handleSubmit}
            disabled={loading}
          >
            {loading ? (
              <Text style={styles.submitButtonText}>Validating...</Text>
            ) : (
              <>
                <Ionicons name="checkmark-circle" size={20} color="white" />
                <Text style={styles.submitButtonText}>Continue to Check-in</Text>
              </>
            )}
          </TouchableOpacity>
        </View>

        {/* Instructions */}
        <View style={styles.instructions}>
          <Text style={styles.instructionTitle}>How to find the Incident ID:</Text>
          <View style={styles.instructionItem}>
            <Text style={styles.instructionBullet}>1.</Text>
            <Text style={styles.instructionText}>
              Look at the incident dashboard on a computer or tablet
            </Text>
          </View>
          <View style={styles.instructionItem}>
            <Text style={styles.instructionBullet}>2.</Text>
            <Text style={styles.instructionText}>
              The incident ID is displayed at the top of the page
            </Text>
          </View>
          <View style={styles.instructionItem}>
            <Text style={styles.instructionBullet}>3.</Text>
            <Text style={styles.instructionText}>
              Enter it exactly as shown, including any dashes or special characters
            </Text>
          </View>
        </View>
      </View>
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
  content: {
    flex: 1,
    padding: 20,
  },
  card: {
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
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
    marginBottom: 12,
  },
  helpText: {
    fontSize: 14,
    color: '#666',
    marginBottom: 24,
    lineHeight: 20,
  },
  submitButton: {
    backgroundColor: '#007AFF',
    borderRadius: 8,
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
  instructions: {
    marginTop: 32,
    backgroundColor: 'white',
    borderRadius: 12,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
  instructionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#333',
    marginBottom: 16,
  },
  instructionItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  instructionBullet: {
    fontSize: 14,
    fontWeight: '600',
    color: '#007AFF',
    marginRight: 12,
    width: 16,
  },
  instructionText: {
    flex: 1,
    fontSize: 14,
    color: '#666',
    lineHeight: 20,
  },
});
