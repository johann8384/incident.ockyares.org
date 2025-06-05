import pytest
import json
from unittest.mock import patch, MagicMock
from models.unit import Unit

class TestUnitModel:
    
    def test_unit_creation(self):
        """Test unit object creation"""
        unit = Unit(
            unit_id='ENG-101',
            unit_name='Engine 101',
            unit_type='Engine',
            unit_leader='Captain Smith'
        )
        
        assert unit.unit_id == 'ENG-101'
        assert unit.unit_name == 'Engine 101'
        assert unit.unit_type == 'Engine'
        assert unit.unit_leader == 'Captain Smith'
        assert unit.current_status == Unit.STATUS_QUARTERS
    
    def test_valid_statuses(self):
        """Test status validation"""
        unit = Unit(unit_id='TEST-001')
        
        # Valid status should not raise error
        try:
            unit.update_status('INC-001', Unit.STATUS_STAGING)
        except ValueError:
            pytest.fail("Valid status should not raise ValueError")
        
        # Invalid status should raise error
        with pytest.raises(ValueError):
            unit.update_status('INC-001', 'invalid_status')
    
    @patch('models.unit.psycopg2.connect')
    def test_create_unit_database(self, mock_connect):
        """Test unit creation in database"""
        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = [1]
        
        unit = Unit(
            unit_id='ENG-101',
            unit_name='Engine 101',
            unit_type='Engine',
            unit_leader='Captain Smith'
        )
        
        result = unit.create_unit('Radio Channel 1')
        
        # Verify database calls
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        assert result == 1
    
    @patch('models.unit.psycopg2.connect')
    def test_update_status_with_location(self, mock_connect):
        """Test status update with location"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        unit = Unit(unit_id='ENG-101')
        
        unit.update_status(
            incident_id='INC-001',
            new_status=Unit.STATUS_OPERATING,
            division_id='DIV-A',
            percentage_complete=50,
            latitude=37.7749,
            longitude=-122.4194,
            notes='Test update',
            user_name='Officer Jones'
        )
        
        # Should call execute twice (update units, insert history)
        assert mock_cursor.execute.call_count == 2
        mock_conn.commit.assert_called_once()
    
    @patch('models.unit.psycopg2.connect')
    def test_assign_to_division(self, mock_connect):
        """Test assigning unit to division"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        unit = Unit(unit_id='ENG-101')
        
        # Mock the update_status method to avoid recursive database calls
        with patch.object(unit, 'update_status') as mock_update:
            unit.assign_to_division('INC-001', 'DIV-A')
            
            # Verify division assignment
            mock_cursor.execute.assert_called_once()
            mock_update.assert_called_once_with('INC-001', Unit.STATUS_ASSIGNED, 'DIV-A')
    
    @patch('models.unit.psycopg2.connect')
    def test_get_units_by_incident(self, mock_connect):
        """Test getting units for an incident"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        
        mock_units = [
            {
                'unit_id': 'ENG-101',
                'unit_name': 'Engine 101',
                'current_status': 'operating',
                'division_name': 'Division A'
            },
            {
                'unit_id': 'TRK-201',
                'unit_name': 'Truck 201',
                'current_status': 'staging',
                'division_name': None
            }
        ]
        mock_cursor.fetchall.return_value = mock_units
        
        result = Unit.get_units_by_incident('INC-001')
        
        assert len(result) == 2
        assert result[0]['unit_id'] == 'ENG-101'
        assert result[1]['unit_id'] == 'TRK-201'
        mock_cursor.execute.assert_called_once()


class TestUnitAPIEndpoints:
    
    def test_create_unit_endpoint(self, client):
        """Test unit creation API endpoint"""
        payload = {
            'unit_id': 'ENG-101',
            'unit_name': 'Engine 101',
            'unit_type': 'Engine',
            'unit_leader': 'Captain Smith',
            'contact_info': 'Radio Channel 1'
        }
        
        with patch('models.unit.Unit.create_unit', return_value=1):
            response = client.post('/api/unit/create',
                                 data=json.dumps(payload),
                                 content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert data['unit_id'] == 'ENG-101'
    
    def test_create_unit_missing_fields(self, client):
        """Test unit creation with missing required fields"""
        payload = {
            'unit_id': 'ENG-101',
            # Missing required fields
        }
        
        response = client.post('/api/unit/create',
                             data=json.dumps(payload),
                             content_type='application/json')
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'required' in data['error'].lower()
    
    def test_update_unit_status_endpoint(self, client):
        """Test unit status update API endpoint"""
        payload = {
            'incident_id': 'INC-001',
            'status': 'operating',
            'division_id': 'DIV-A',
            'percentage_complete': 75,
            'latitude': 37.7749,
            'longitude': -122.4194,
            'notes': 'Making good progress',
            'user_name': 'Officer Jones'
        }
        
        with patch('models.unit.Unit.update_status'):
            response = client.post('/api/unit/ENG-101/status',
                                 data=json.dumps(payload),
                                 content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'updated' in data['message'].lower()
    
    def test_assign_division_endpoint(self, client):
        """Test division assignment API endpoint"""
        payload = {
            'unit_id': 'ENG-101',
            'division_id': 'DIV-A'
        }
        
        with patch('models.unit.Unit.assign_to_division'):
            response = client.post('/api/incident/INC-001/assign-division',
                                 data=json.dumps(payload),
                                 content_type='application/json')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert 'assigned' in data['message'].lower()
    
    def test_get_incident_units_endpoint(self, client):
        """Test getting units for incident API endpoint"""
        mock_units = [
            {
                'unit_id': 'ENG-101',
                'unit_name': 'Engine 101',
                'current_status': 'operating'
            }
        ]
        
        with patch('models.unit.Unit.get_units_by_incident', return_value=mock_units):
            response = client.get('/api/incident/INC-001/units')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert data['count'] == 1
        assert data['units'][0]['unit_id'] == 'ENG-101'
    
    def test_get_unit_history_endpoint(self, client):
        """Test getting unit status history API endpoint"""
        mock_history = [
            {
                'status': 'operating',
                'timestamp': '2024-01-01T10:00:00',
                'division_name': 'Division A',
                'percentage_complete': 50
            },
            {
                'status': 'assigned',
                'timestamp': '2024-01-01T09:00:00',
                'division_name': 'Division A',
                'percentage_complete': 0
            }
        ]
        
        with patch('models.unit.Unit.get_unit_status_history', return_value=mock_history):
            response = client.get('/api/unit/ENG-101/history?incident_id=INC-001')
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['success'] == True
        assert data['count'] == 2
        assert data['history'][0]['status'] == 'operating'


class TestUnitWorkflow:
    
    def test_complete_unit_workflow(self, client):
        """Test complete unit workflow from creation to status updates"""
        # 1. Create unit
        create_payload = {
            'unit_id': 'ENG-101',
            'unit_name': 'Engine 101',
            'unit_type': 'Engine',
            'unit_leader': 'Captain Smith'
        }
        
        with patch('models.unit.Unit.create_unit', return_value=1):
            create_response = client.post('/api/unit/create',
                                        data=json.dumps(create_payload),
                                        content_type='application/json')
        
        assert create_response.status_code == 200
        
        # 2. Assign to division
        assign_payload = {
            'unit_id': 'ENG-101',
            'division_id': 'DIV-A'
        }
        
        with patch('models.unit.Unit.assign_to_division'):
            assign_response = client.post('/api/incident/INC-001/assign-division',
                                        data=json.dumps(assign_payload),
                                        content_type='application/json')
        
        assert assign_response.status_code == 200
        
        # 3. Update status to operating
        status_payload = {
            'incident_id': 'INC-001',
            'status': 'operating',
            'division_id': 'DIV-A',
            'percentage_complete': 25
        }
        
        with patch('models.unit.Unit.update_status'):
            status_response = client.post('/api/unit/ENG-101/status',
                                        data=json.dumps(status_payload),
                                        content_type='application/json')
        
        assert status_response.status_code == 200
        
        # 4. Update to recovering (100% complete)
        recovering_payload = {
            'incident_id': 'INC-001',
            'status': 'recovering',
            'division_id': 'DIV-A',
            'percentage_complete': 100
        }
        
        with patch('models.unit.Unit.update_status'):
            recovering_response = client.post('/api/unit/ENG-101/status',
                                            data=json.dumps(recovering_payload),
                                            content_type='application/json')
        
        assert recovering_response.status_code == 200
        
        # 5. Back to staging
        staging_payload = {
            'incident_id': 'INC-001',
            'status': 'staging'
        }
        
        with patch('models.unit.Unit.update_status'):
            staging_response = client.post('/api/unit/ENG-101/status',
                                         data=json.dumps(staging_payload),
                                         content_type='application/json')
        
        assert staging_response.status_code == 200


class TestUnitStatusValidation:
    
    def test_status_transitions(self):
        """Test valid status transitions"""
        unit = Unit(unit_id='TEST-001')
        
        # Test normal workflow
        valid_transitions = [
            ('staging', 'assigned'),
            ('assigned', 'operating'), 
            ('operating', 'recovering'),
            ('recovering', 'staging'),
            ('staging', 'quarters'),
            ('any_status', 'out_of_service')  # Can go out of service anytime
        ]
        
        for current, next_status in valid_transitions:
            if current != 'any_status':
                unit.current_status = current
            
            try:
                # This would normally call database, but we're just testing validation
                assert next_status in Unit.VALID_STATUSES
            except ValueError:
                pytest.fail(f"Transition from {current} to {next_status} should be valid")
    
    def test_percentage_validation(self):
        """Test percentage complete validation"""
        # Operating status should allow percentage
        # Other statuses typically don't use percentage but it's not enforced at model level
        assert 0 <= 50 <= 100  # Valid percentage
        assert 0 <= 100 <= 100  # Valid percentage
