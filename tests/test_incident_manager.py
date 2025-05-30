import pytest
import json
from unittest.mock import patch, MagicMock
from app import IncidentManager

class TestIncidentManager:
    
    def test_database_connection(self, incident_manager):
        """Test database connection works"""
        assert incident_manager.test_connection() == True
    
    def test_create_incident(self, incident_manager, sample_incident_data):
        """Test incident creation"""
        incident_id = incident_manager.create_incident(sample_incident_data)
        
        assert incident_id is not None
        assert incident_id.startswith('USR')
        assert len(incident_id) == 15  # USR + 8 digit date + 4 char UUID
    
    def test_create_incident_invalid_data(self, incident_manager):
        """Test incident creation with invalid data"""
        invalid_data = {
            'incident_name': '',
            'incident_type': 'Test',
            'ic_name': 'Test',
            'latitude': 'invalid',
            'longitude': -122.4194
        }
        
        with pytest.raises(Exception):
            incident_manager.create_incident(invalid_data)
    
    def test_create_search_area(self, incident_manager, sample_incident_data, sample_search_area):
        """Test search area creation"""
        # First create an incident
        incident_id = incident_manager.create_incident(sample_incident_data)
        
        # Then create search area
        area_id = incident_manager.create_search_area(incident_id, sample_search_area)
        
        assert area_id is not None
        assert isinstance(area_id, int)
    
    def test_create_search_area_invalid_polygon(self, incident_manager, sample_incident_data):
        """Test search area creation with invalid polygon"""
        incident_id = incident_manager.create_incident(sample_incident_data)
        
        # Only 2 points - not enough for polygon
        invalid_area = [[-122.42, 37.77], [-122.41, 37.77]]
        
        result = incident_manager.create_search_area(incident_id, invalid_area)
        assert result is None
    
    def test_create_divisions(self, incident_manager, sample_incident_data, sample_search_area, sample_teams):
        """Test division creation"""
        incident_id = incident_manager.create_incident(sample_incident_data)
        
        divisions = incident_manager.create_divisions(
            incident_id, 
            sample_search_area, 
            grid_size=200,  # Larger grid for test
            teams=sample_teams
        )
        
        assert isinstance(divisions, list)
        assert len(divisions) > 0
        
        # Check first division
        first_div = divisions[0]
        assert 'division_id' in first_div
        assert 'division_name' in first_div
        assert first_div['assigned_team'] == 'Test Team Alpha'
    
    def test_generate_qr_codes(self, incident_manager, sample_incident_data, sample_teams):
        """Test QR code generation"""
        incident_id = incident_manager.create_incident(sample_incident_data)
        
        qr_codes = incident_manager.generate_qr_codes(incident_id, sample_teams)
        
        assert isinstance(qr_codes, dict)
        assert len(qr_codes) == len(sample_teams)
        
        # Check first QR code
        first_qr = qr_codes['team1']
        assert 'team_name' in first_qr
        assert 'qr_code' in first_qr
        assert 'config' in first_qr
        
        # Validate QR code config
        config = first_qr['config']
        assert config['incident_id'] == incident_id
        assert config['team_id'] == 'team1'

class TestIncidentManagerErrorHandling:
    
    def test_database_connection_failure(self):
        """Test handling of database connection failures"""
        manager = IncidentManager()
        manager.db_config = {
            'host': 'nonexistent',
            'database': 'nonexistent',
            'user': 'nonexistent',
            'password': 'nonexistent'
        }
        
        assert manager.test_connection() == False
    
    @patch('psycopg2.connect')
    def test_create_incident_database_error(self, mock_connect, sample_incident_data):
        """Test incident creation with database error"""
        mock_connect.side_effect = Exception("Database error")
        
        manager = IncidentManager()
        
        with pytest.raises(Exception):
            manager.create_incident(sample_incident_data)
