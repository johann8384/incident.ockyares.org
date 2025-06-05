import pytest
import json
from unittest.mock import patch, MagicMock
import requests


class TestGeocodeRoutes:
    """Test geocoding endpoints"""

    def test_reverse_geocode_success(self, client):
        """Test successful reverse geocoding"""
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                'display_name': '123 Main St, Louisville, KY 40202',
                'address': {
                    'house_number': '123',
                    'road': 'Main St',
                    'city': 'Louisville',
                    'state': 'Kentucky',
                    'postcode': '40202'
                }
            }
            mock_get.return_value = mock_response

            data = {'latitude': 38.2527, 'longitude': -85.7585}
            
            response = client.post(
                '/api/geocode/reverse',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['success'] is True
            assert 'address' in result
            assert '123 Main St' in result['address']

    def test_reverse_geocode_missing_coordinates(self, client):
        """Test reverse geocode with missing coordinates"""
        data = {'latitude': 38.2527}  # Missing longitude
        
        response = client.post(
            '/api/geocode/reverse',
            data=json.dumps(data),
            content_type='application/json'
        )

        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'required' in result['error'].lower()

    def test_reverse_geocode_invalid_coordinates(self, client):
        """Test reverse geocode with invalid coordinate values"""
        data = {'latitude': 'invalid', 'longitude': -85.7585}
        
        response = client.post(
            '/api/geocode/reverse',
            data=json.dumps(data),
            content_type='application/json'
        )

        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'invalid' in result['error'].lower()

    def test_reverse_geocode_api_timeout(self, client):
        """Test reverse geocode with API timeout"""
        with patch('requests.get') as mock_get:
            mock_get.side_effect = requests.exceptions.Timeout()

            data = {'latitude': 38.2527, 'longitude': -85.7585}
            
            response = client.post(
                '/api/geocode/reverse',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 500
            result = json.loads(response.data)
            assert 'timeout' in result['error'].lower()

    def test_reverse_geocode_api_error(self, client):
        """Test reverse geocode with API error"""
        with patch('requests.get') as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_get.return_value = mock_response

            data = {'latitude': 38.2527, 'longitude': -85.7585}
            
            response = client.post(
                '/api/geocode/reverse',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 500


class TestHospitalRoutes:
    """Test hospital search endpoints"""

    def test_search_hospitals_success(self, client):
        """Test successful hospital search"""
        with patch('app.Hospital') as mock_hospital_class:
            mock_hospital = MagicMock()
            mock_hospital.get_hospitals_for_location.return_value = {
                'success': True,
                'hospitals': {
                    'trauma_centers': [
                        {'name': 'University Hospital', 'distance': 2.1}
                    ],
                    'general_hospitals': [
                        {'name': 'Baptist East', 'distance': 3.4}
                    ]
                },
                'total_found': 2,
                'source': 'api'
            }
            mock_hospital_class.return_value = mock_hospital

            data = {'latitude': 38.2527, 'longitude': -85.7585}
            
            response = client.post(
                '/api/hospitals/search',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['success'] is True
            assert 'hospitals' in result
            assert result['total_found'] == 2

    def test_search_hospitals_missing_coordinates(self, client):
        """Test hospital search with missing coordinates"""
        data = {'latitude': 38.2527}  # Missing longitude
        
        response = client.post(
            '/api/hospitals/search',
            data=json.dumps(data),
            content_type='application/json'
        )

        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'required' in result['error'].lower()

    def test_search_hospitals_api_failure(self, client):
        """Test hospital search with API failure"""
        with patch('app.Hospital') as mock_hospital_class:
            mock_hospital = MagicMock()
            mock_hospital.get_hospitals_for_location.return_value = {
                'success': False,
                'error': 'API connection failed'
            }
            mock_hospital_class.return_value = mock_hospital

            data = {'latitude': 38.2527, 'longitude': -85.7585}
            
            response = client.post(
                '/api/hospitals/search',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 500
            result = json.loads(response.data)
            assert result['success'] is False


class TestDivisionRoutes:
    """Test division-related endpoints"""

    def test_generate_divisions_preview_success(self, client):
        """Test successful division preview generation"""
        with patch('app.Incident') as mock_incident_class:
            mock_incident = MagicMock()
            mock_incident.generate_divisions_preview.return_value = [
                {'name': 'Division A', 'area_m2': 35000, 'coordinates': []},
                {'name': 'Division B', 'area_m2': 42000, 'coordinates': []}
            ]
            mock_incident_class.return_value = mock_incident

            data = {
                'coordinates': [
                    [-85.7585, 38.2527],
                    [-85.7575, 38.2527],
                    [-85.7575, 38.2537],
                    [-85.7585, 38.2537]
                ],
                'area_size_m2': 40000
            }
            
            response = client.post(
                '/api/divisions/generate',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['success'] is True
            assert result['count'] == 2
            assert len(result['divisions']) == 2

    def test_generate_divisions_preview_missing_coordinates(self, client):
        """Test division preview with missing coordinates"""
        data = {'area_size_m2': 40000}  # Missing coordinates
        
        response = client.post(
            '/api/divisions/generate',
            data=json.dumps(data),
            content_type='application/json'
        )

        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'coordinates required' in result['error'].lower()

    def test_generate_divisions_preview_insufficient_coordinates(self, client):
        """Test division preview with too few coordinates"""
        data = {
            'coordinates': [[-85.7585, 38.2527], [-85.7575, 38.2527]],  # Only 2 points
            'area_size_m2': 40000
        }
        
        response = client.post(
            '/api/divisions/generate',
            data=json.dumps(data),
            content_type='application/json'
        )

        assert response.status_code == 400

    def test_save_divisions_success(self, client):
        """Test successful division saving"""
        with patch('app.Incident.get_incident_by_id') as mock_get_incident:
            mock_incident = MagicMock()
            mock_incident.save_divisions.return_value = True
            mock_get_incident.return_value = mock_incident

            data = {
                'divisions': [
                    {'name': 'Division A', 'area_m2': 35000},
                    {'name': 'Division B', 'area_m2': 42000}
                ]
            }
            
            response = client.post(
                '/api/incident/TEST-001/divisions',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['success'] is True
            assert 'Saved 2 divisions' in result['message']

    def test_save_divisions_incident_not_found(self, client):
        """Test division saving with non-existent incident"""
        with patch('app.Incident.get_incident_by_id') as mock_get_incident:
            mock_get_incident.return_value = None

            data = {'divisions': [{'name': 'Division A'}]}
            
            response = client.post(
                '/api/incident/NONEXISTENT/divisions',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 404
            result = json.loads(response.data)
            assert 'not found' in result['error'].lower()

    def test_get_divisions_success(self, client):
        """Test successful division retrieval"""
        with patch('app.Incident') as mock_incident_class:
            mock_incident = MagicMock()
            mock_incident.get_divisions.return_value = [
                {'name': 'Division A', 'status': 'assigned'},
                {'name': 'Division B', 'status': 'unassigned'}
            ]
            mock_incident_class.return_value = mock_incident

            response = client.get('/api/incident/TEST-001/divisions')

            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['success'] is True
            assert result['count'] == 2
            assert len(result['divisions']) == 2


class TestUnitRoutes:
    """Test unit check-in and management endpoints"""

    def test_unit_checkin_success(self, client):
        """Test successful unit check-in"""
        with patch('app.Incident.get_incident_by_id') as mock_get_incident, \
             patch('app.db_manager.connect') as mock_connect:
            
            # Mock incident exists
            mock_incident = MagicMock()
            mock_get_incident.return_value = mock_incident
            
            # Mock database operations
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.side_effect = [None, [123]]  # No existing unit, then new ID
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            data = {
                'incident_id': 'TEST-001',
                'unit_id': 'ENGINE-01',
                'company_officer': 'Captain Smith',
                'number_of_personnel': 4,
                'latitude': 38.2527,
                'longitude': -85.7585,
                'bsar_tech': True,
                'notes': 'Ready for assignment'
            }
            
            response = client.post(
                '/api/unit/checkin',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['success'] is True
            assert result['unit_id'] == 'ENGINE-01'

    def test_unit_checkin_missing_fields(self, client):
        """Test unit check-in with missing required fields"""
        data = {
            'incident_id': 'TEST-001',
            'unit_id': 'ENGINE-01'
            # Missing required fields
        }
        
        response = client.post(
            '/api/unit/checkin',
            data=json.dumps(data),
            content_type='application/json'
        )

        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'required' in result['error'].lower()

    def test_unit_checkin_invalid_personnel_count(self, client):
        """Test unit check-in with invalid personnel count"""
        with patch('app.Incident.get_incident_by_id') as mock_get_incident:
            mock_incident = MagicMock()
            mock_get_incident.return_value = mock_incident

            data = {
                'incident_id': 'TEST-001',
                'unit_id': 'ENGINE-01',
                'company_officer': 'Captain Smith',
                'number_of_personnel': 0,  # Invalid count
                'latitude': 38.2527,
                'longitude': -85.7585
            }
            
            response = client.post(
                '/api/unit/checkin',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 400
            result = json.loads(response.data)
            assert 'at least 1' in result['error'].lower()

    def test_unit_checkin_duplicate_unit(self, client):
        """Test check-in of already checked-in unit"""
        with patch('app.Incident.get_incident_by_id') as mock_get_incident, \
             patch('app.db_manager.connect') as mock_connect:
            
            mock_incident = MagicMock()
            mock_get_incident.return_value = mock_incident
            
            # Mock database operations - unit already exists
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = [123]  # Existing unit found
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            data = {
                'incident_id': 'TEST-001',
                'unit_id': 'ENGINE-01',
                'company_officer': 'Captain Smith',
                'number_of_personnel': 4,
                'latitude': 38.2527,
                'longitude': -85.7585
            }
            
            response = client.post(
                '/api/unit/checkin',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 400
            result = json.loads(response.data)
            assert 'already checked in' in result['error'].lower()

    def test_unit_checkin_incident_not_found(self, client):
        """Test unit check-in with non-existent incident"""
        with patch('app.Incident.get_incident_by_id') as mock_get_incident:
            mock_get_incident.return_value = None

            data = {
                'incident_id': 'NONEXISTENT',
                'unit_id': 'ENGINE-01',
                'company_officer': 'Captain Smith',
                'number_of_personnel': 4,
                'latitude': 38.2527,
                'longitude': -85.7585
            }
            
            response = client.post(
                '/api/unit/checkin',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 404
            result = json.loads(response.data)
            assert 'not found' in result['error'].lower()

    def test_get_incident_units_success(self, client):
        """Test successful retrieval of incident units"""
        with patch('app.db_manager.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = [
                ('ENGINE-01', 'Captain Smith', 4, True, 38.2527, -85.7585, 
                 'active', '2024-01-01T10:00:00', '2024-01-01T10:00:00', 'Ready'),
                ('TRUCK-02', 'Lieutenant Jones', 3, False, 38.2530, -85.7580,
                 'active', '2024-01-01T10:05:00', '2024-01-01T10:05:00', '')
            ]
            mock_conn.cursor.return_value = mock_cursor
            mock_connect.return_value = mock_conn

            response = client.get('/api/incident/TEST-001/units')

            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['success'] is True
            assert result['count'] == 2
            assert len(result['units']) == 2
            assert result['units'][0]['unit_id'] == 'ENGINE-01'


class TestIncidentDetailRoutes:
    """Test incident detail endpoints"""

    def test_get_incident_success(self, client):
        """Test successful incident retrieval"""
        with patch('app.Incident.get_incident_by_id') as mock_get_incident:
            mock_incident = MagicMock()
            mock_incident.get_incident_data.return_value = {
                'incident_id': 'TEST-001',
                'name': 'Test Incident',
                'status': 'active',
                'latitude': 38.2527,
                'longitude': -85.7585
            }
            mock_get_incident.return_value = mock_incident

            response = client.get('/api/incident/TEST-001')

            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['success'] is True
            assert 'incident' in result
            assert result['incident']['incident_id'] == 'TEST-001'

    def test_get_incident_not_found(self, client):
        """Test retrieval of non-existent incident"""
        with patch('app.Incident.get_incident_by_id') as mock_get_incident:
            mock_get_incident.return_value = None

            response = client.get('/api/incident/NONEXISTENT')

            assert response.status_code == 404
            result = json.loads(response.data)
            assert 'not found' in result['error'].lower()

    def test_save_hospital_data_success(self, client):
        """Test successful hospital data saving"""
        with patch('app.Incident') as mock_incident_class:
            mock_incident = MagicMock()
            mock_incident.save_hospital_data.return_value = True
            mock_incident_class.return_value = mock_incident

            data = {
                'hospital_data': {
                    'trauma_centers': [{'name': 'University Hospital'}],
                    'general_hospitals': [{'name': 'Baptist East'}]
                }
            }
            
            response = client.post(
                '/api/incident/TEST-001/hospitals',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 200
            result = json.loads(response.data)
            assert result['success'] is True

    def test_save_hospital_data_missing_data(self, client):
        """Test hospital data saving with missing data"""
        data = {}  # Missing hospital_data
        
        response = client.post(
            '/api/incident/TEST-001/hospitals',
            data=json.dumps(data),
            content_type='application/json'
        )

        assert response.status_code == 400
        result = json.loads(response.data)
        assert 'required' in result['error'].lower()


class TestTemplateRoutes:
    """Test template rendering routes"""

    def test_index_route(self, client):
        """Test main index page"""
        response = client.get('/')
        assert response.status_code == 200
        assert b'html' in response.data

    def test_view_incident_route(self, client):
        """Test incident view page"""
        response = client.get('/incident/TEST-001')
        assert response.status_code == 200
        assert b'html' in response.data

    def test_unit_checkin_route(self, client):
        """Test unit check-in page"""
        response = client.get('/incident/TEST-001/unit-checkin')
        assert response.status_code == 200
        assert b'html' in response.data


class TestErrorHandling:
    """Test error handling scenarios"""

    def test_invalid_json_data(self, client):
        """Test endpoints with invalid JSON"""
        response = client.post(
            '/api/incident',
            data='invalid json',
            content_type='application/json'
        )
        assert response.status_code == 500

    def test_missing_json_data(self, client):
        """Test endpoints with no JSON data"""
        response = client.post('/api/incident')
        assert response.status_code == 500

    def test_general_exception_handling(self, client):
        """Test general exception handling"""
        with patch('app.Incident') as mock_incident_class:
            mock_incident_class.side_effect = Exception("Unexpected error")

            data = {'name': 'Test', 'incident_type': 'Test'}
            
            response = client.post(
                '/api/incident',
                data=json.dumps(data),
                content_type='application/json'
            )

            assert response.status_code == 500
            result = json.loads(response.data)
            assert 'error' in result
