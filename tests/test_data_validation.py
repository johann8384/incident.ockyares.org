import pytest
from shapely.geometry import Polygon

class TestDataValidation:
    
    def test_valid_coordinates(self):
        """Test validation of coordinate data"""
        valid_coords = [
            [-122.42, 37.77],
            [-122.41, 37.77],
            [-122.41, 37.78],
            [-122.42, 37.78]
        ]
        
        # Should be able to create a polygon
        polygon = Polygon(valid_coords)
        assert polygon.is_valid
        assert polygon.area > 0
    
    def test_invalid_coordinates(self):
        """Test handling of invalid coordinates"""
        invalid_coords = [
            [999, 999],  # Invalid longitude/latitude
            [-999, -999]
        ]
        
        # Should still create polygon but may not be valid geographically
        polygon = Polygon(invalid_coords)
        # Test should verify the application handles this appropriately
        
    def test_team_data_validation(self, sample_teams):
        """Test team data structure validation"""
        for team in sample_teams:
            assert 'team_id' in team
            assert 'team_name' in team
            assert 'team_leader' in team
            assert len(team['team_id']) > 0
            assert len(team['team_name']) > 0
            assert len(team['team_leader']) > 0
    
    def test_incident_data_validation(self, sample_incident_data):
        """Test incident data structure validation"""
        required_fields = [
            'incident_name', 'incident_type', 'ic_name', 
            'latitude', 'longitude'
        ]
        
        for field in required_fields:
            assert field in sample_incident_data
            assert sample_incident_data[field] is not None
        
        # Test coordinate ranges
        assert -90 <= sample_incident_data['latitude'] <= 90
        assert -180 <= sample_incident_data['longitude'] <= 180
