import pytest
from unittest.mock import patch, MagicMock
from models.incident import Incident
from shapely.geometry import Point, Polygon

class TestIncident:
    
    def test_create_incident(self, incident, sample_incident_data):
        """Test incident creation"""
        incident_id = incident.create_incident(
            name=sample_incident_data['name'],
            incident_type=sample_incident_data['incident_type'],
            description=sample_incident_data['description']
        )
        
        assert incident_id is not None
        assert incident_id.startswith('INC-')
        assert len(incident_id) == 21  # INC- + 8 digit date + 8 char UUID
        assert incident.incident_id == incident_id
        assert incident.name == sample_incident_data['name']
    
    def test_create_incident_invalid_data(self, incident):
        """Test incident creation with invalid data"""
        with pytest.raises(Exception):
            incident.create_incident(
                name="",  # Empty name should fail
                incident_type="Test"
            )
    
    def test_set_location(self, incident, sample_incident_data, sample_coordinates):
        """Test setting incident location"""
        # First create an incident
        incident_id = incident.create_incident(
            name=sample_incident_data['name'],
            incident_type=sample_incident_data['incident_type']
        )
        
        # Set location
        success = incident.set_location(
            latitude=sample_coordinates['latitude'],
            longitude=sample_coordinates['longitude']
        )
        
        assert success is True
        assert incident.incident_location is not None
        assert isinstance(incident.incident_location, Point)
        assert incident.address is not None
    
    @patch('requests.get')
    def test_reverse_geocode_success(self, mock_get, incident):
        """Test reverse geocoding success"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'display_name': '123 Test Street, Test City, CA, USA'
        }
        mock_get.return_value = mock_response
        
        address = incident._reverse_geocode(37.7749, -122.4194)
        assert address == '123 Test Street, Test City, CA, USA'
    
    @patch('requests.get')
    def test_reverse_geocode_failure(self, mock_get, incident):
        """Test reverse geocoding failure"""
        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        address = incident._reverse_geocode(37.7749, -122.4194)
        assert address == '37.7749, -122.4194'  # Should return coordinates
    
    def test_set_search_area(self, incident, sample_incident_data, sample_search_area):
        """Test setting search area"""
        # First create an incident
        incident_id = incident.create_incident(
            name=sample_incident_data['name'],
            incident_type=sample_incident_data['incident_type']
        )
        
        # Set search area
        success = incident.set_search_area(sample_search_area)
        
        assert success is True
        assert incident.search_area is not None
        assert isinstance(incident.search_area, Polygon)
    
    def test_set_search_area_invalid_polygon(self, incident, sample_incident_data):
        """Test setting invalid search area"""
        # First create an incident
        incident_id = incident.create_incident(
            name=sample_incident_data['name'],
            incident_type=sample_incident_data['incident_type']
        )
        
        # Try to set invalid search area (only 2 points)
        invalid_area = [[37.77, -122.42], [37.78, -122.41]]
        
        success = incident.set_search_area(invalid_area)
        assert success is False
    
    def test_calculate_area_m2(self, incident):
        """Test area calculation"""
        # Create a simple square polygon
        polygon = Polygon([
            [0, 0], [0, 0.001], [0.001, 0.001], [0.001, 0], [0, 0]
        ])
        
        area = incident._calculate_area_m2(polygon)
        assert area > 0
        assert area < 1000000  # Should be reasonable size
    
    def test_generate_divisions(self, incident, sample_incident_data, sample_search_area):
        """Test division generation"""
        # Create incident and set search area
        incident_id = incident.create_incident(
            name=sample_incident_data['name'],
            incident_type=sample_incident_data['incident_type']
        )
        
        incident.set_search_area(sample_search_area)
        
        # Generate divisions
        divisions = incident.generate_divisions()
        
        assert isinstance(divisions, list)
        assert len(divisions) > 0
        
        # Check first division
        first_div = divisions[0]
        assert 'name' in first_div
        assert 'geometry' in first_div
        assert 'area_m2' in first_div
        assert 'status' in first_div
        assert first_div['status'] == 'unassigned'
    
    def test_generate_divisions_no_search_area(self, incident, sample_incident_data):
        """Test division generation without search area"""
        # Create incident without search area
        incident_id = incident.create_incident(
            name=sample_incident_data['name'],
            incident_type=sample_incident_data['incident_type']
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="Search area must be set"):
            incident.generate_divisions()
    
    def test_create_grid_divisions(self, incident, sample_search_area):
        """Test grid division creation"""
        # Set up search area
        incident.search_area = Polygon(sample_search_area)
        
        # Create grid divisions
        divisions = incident._create_grid_divisions(4)
        
        assert len(divisions) <= 4  # May be less due to clipping
        
        for division in divisions:
            assert division['name'].startswith('Division ')
            assert division['area_m2'] > 0
            assert hasattr(division['geometry'], 'area')