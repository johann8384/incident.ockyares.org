import pytest
import json
from unittest.mock import patch, MagicMock

class TestFlaskRoutes:
    
    def test_index_route(self, client):
        """Test the main index route"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Create New Incident' in response.data
    
    def test_health_check_healthy(self, client):
        """Test health check when system is healthy"""
        response = client.get('/health')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['status'] == 'healthy'
        assert data['database'] == 'connected'
    
    @patch('app.incident_mgr.test_connection')
    def test_health_check_unhealthy(self, mock_test_connection, client):
        """Test health check when database is down"""
        mock_test_connection.return_value = False
        
        response = client.get('/health')
        assert response.status_code == 503
        
        data = json.loads(response.data)
        assert data['status'] == 'unhealthy'
        assert data['database'] == 'disconnected'
    
    def test_create_incident_success(self, client, sample_incident_data, sample_search_area, sample_teams):
        """Test successful incident creation"""
        payload = {
            'incident': sample_incident_data,
            'search_area_coordinates': sample_search_area,
            'grid_size': 100,
            'teams': sample_teams
        }
        
        response = client.post('/create_incident', 
                             data=json.dumps(payload),
                             content_type='application/json')
        
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'incident_id' in data
        assert 'divisions' in data
        assert 'qr_codes' in data
    
    def test_create_incident_missing_name(self, client, sample_search_area):
        """Test incident creation with missing incident name"""
        payload = {
            'incident': {
                'incident_name': '',  # Empty name
                'incident_type': 'Test',
                'ic_name': 'Test Commander',
                'latitude': 37.7749,
                'longitude': -122.4194
            },
            'search_area_coordinates': sample_search_area,
            'teams': []
        }
        
        response = client.post('/create_incident',
                             data=json.dumps(payload),
                             content_type='application/json')
        
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] == False
        assert 'Incident name is required' in data['error']
    
    def test_create_incident_invalid_search_area(self, client, sample_incident_data):
        """Test incident creation with invalid search area"""
        payload = {
            'incident': sample_incident_data,
            'search_area_coordinates': [[-122.42, 37.77]],  # Only 1 point
            'teams': []
        }
        
        response = client.post('/create_incident',
                             data=json.dumps(payload),
                             content_type='application/json')
        
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] == False
        assert 'at least 3 coordinates' in data['error']
    
    def test_create_incident_no_json(self, client):
        """Test incident creation with no JSON data"""
        response = client.post('/create_incident')
        
        assert response.status_code == 500  # Will fail due to no JSON
    
    def test_view_incident_route(self, client):
        """Test incident view route"""
        response = client.get('/incident/TEST123')
        assert response.status_code == 200
        assert b'incident_id' in response.data
    
    def test_qr_code_route_not_found(self, client):
        """Test QR code route with non-existent file"""
        response = client.get('/qr/nonexistent.png')
        assert response.status_code == 404

class TestIntegrationFlow:
    
    def test_complete_incident_creation_flow(self, client, sample_incident_data, sample_search_area, sample_teams):
        """Test the complete flow from incident creation to QR codes"""
        # 1. Create incident
        payload = {
            'incident': sample_incident_data,
            'search_area_coordinates': sample_search_area,
            'grid_size': 150,
            'teams': sample_teams
        }
        
        response = client.post('/create_incident',
                             data=json.dumps(payload),
                             content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        
        incident_id = data['incident_id']
        
        # 2. Verify incident was created
        assert incident_id.startswith('USR')
        
        # 3. Verify divisions were created
        divisions = data['divisions']
        assert len(divisions) > 0
        assert all('division_id' in div for div in divisions)
        
        # 4. Verify QR codes were generated
        qr_codes = data['qr_codes']
        assert len(qr_codes) == len(sample_teams)
        
        for team in sample_teams:
            team_id = team['team_id']
            assert team_id in qr_codes
            assert 'qr_code' in qr_codes[team_id]
            assert 'config' in qr_codes[team_id]
        
        # 5. Test viewing the incident
        view_response = client.get(f'/incident/{incident_id}')
        assert view_response.status_code == 200
