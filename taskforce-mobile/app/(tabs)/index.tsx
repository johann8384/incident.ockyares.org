import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  Alert,
  Linking,
  TouchableOpacity,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useLocalSearchParams } from 'expo-router';
import { BarCodeScanner } from 'expo-barcode-scanner';
import { StatusBar } from 'expo-status-bar';

import IncidentScanner from '@/components/IncidentScanner';
import ManualIncidentEntry from '@/components/ManualIncidentEntry';
import UnitCheckinForm from '@/components/UnitCheckinForm';

type AppState = 'scanner' | 'manual' | 'checkin';

export default function HomeScreen() {
  const [currentState, setCurrentState] = useState<AppState>('scanner');
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const params = useLocalSearchParams();

  useEffect(() => {
    // Check for deep link incident ID
    if (params.incidentId) {
      setIncidentId(params.incidentId as string);
      setCurrentState('checkin');
    }

    // Request camera permission
    (async () => {
      const { status } = await BarCodeScanner.requestPermissionsAsync();
      setHasPermission(status === 'granted');
      setLoading(false);
    })();

    // Handle deep links
    const handleDeepLink = (url: string) => {
      // Handle taskforce://checkin/:incidentId
      const match = url.match(/taskforce:\/\/checkin\/(.+)/);
      if (match) {
        const id = match[1];
        setIncidentId(id);
        setCurrentState('checkin');
      }
    };

    // Check for initial URL
    Linking.getInitialURL().then((url) => {
      if (url) {
        handleDeepLink(url);
      }
    });

    // Listen for incoming URLs
    const subscription = Linking.addEventListener('url', (event) => {
      handleDeepLink(event.url);
    });

    return () => subscription?.remove();
  }, [params.incidentId]);

  const handleScanSuccess = (data: string) => {
    // Handle QR code data
    const match = data.match(/taskforce:\/\/checkin\/(.+)/);
    if (match) {
      const id = match[1];
      setIncidentId(id);
      setCurrentState('checkin');
    } else {
      Alert.alert('Invalid QR Code', 'This QR code is not for incident check-in.');
    }
  };

  const handleManualEntry = (id: string) => {
    setIncidentId(id);
    setCurrentState('checkin');
  };

  const handleCheckinComplete = () => {
    Alert.alert(
      'Unit Checked In',
      'Unit successfully checked in to incident.',
      [
        {
          text: 'Check In Another Unit',
          onPress: () => {
            setIncidentId(null);
            setCurrentState('scanner');
          },
        },
        {
          text: 'Done',
          style: 'default',
        },
      ]
    );
  };

  const handleBack = () => {
    if (currentState === 'checkin') {
      setIncidentId(null);
      setCurrentState('scanner');
    } else if (currentState === 'manual') {
      setCurrentState('scanner');
    }
  };

  if (loading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#007AFF" />
          <Text style={styles.loadingText}>Loading...</Text>
        </View>
      </SafeAreaView>
    );
  }

  if (hasPermission === null) {
    return (
      <SafeAreaView style={styles.container}>
        <Text>Requesting camera permission...</Text>
      </SafeAreaView>
    );
  }

  if (hasPermission === false) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.errorContainer}>
          <Text style={styles.errorTitle}>Camera Access Required</Text>
          <Text style={styles.errorText}>
            This app needs camera access to scan QR codes for incident check-in.
          </Text>
          <TouchableOpacity
            style={styles.settingsButton}
            onPress={() => Linking.openSettings()}
          >
            <Text style={styles.settingsButtonText}>Open Settings</Text>
          </TouchableOpacity>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <StatusBar style="auto" />
      
      {currentState === 'scanner' && (
        <IncidentScanner
          onScanSuccess={handleScanSuccess}
          onManualEntry={() => setCurrentState('manual')}
        />
      )}

      {currentState === 'manual' && (
        <ManualIncidentEntry
          onSubmit={handleManualEntry}
          onBack={handleBack}
        />
      )}

      {currentState === 'checkin' && incidentId && (
        <UnitCheckinForm
          incidentId={incidentId}
          onCheckinComplete={handleCheckinComplete}
          onBack={handleBack}
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#f8f9fa',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 16,
    fontSize: 16,
    color: '#666',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorTitle: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#333',
    marginBottom: 16,
    textAlign: 'center',
  },
  errorText: {
    fontSize: 16,
    color: '#666',
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 24,
  },
  settingsButton: {
    backgroundColor: '#007AFF',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  settingsButtonText: {
    color: 'white',
    fontSize: 16,
    fontWeight: '600',
  },
});
