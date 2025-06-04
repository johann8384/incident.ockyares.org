import pytest
import json
from unittest.mock import patch, MagicMock


class TestFlaskRoutes:

    def test_health_check_success(self, client):
        """Test health check endpoint when healthy"""
        with patch("app.db_manager.connect") as mock_connect, patch(
            "app.db_manager.close"
        ) as mock_close:

            mock_connect.return_value = MagicMock()

            response = client.get("/health")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["status"] == "healthy"
            assert data["database"] == "connected"

    def test_health_check_failure(self, client):
        """Test health check endpoint when database fails"""
        with patch("app.db_manager.connect") as mock_connect:
            mock_connect.side_effect = Exception("Database connection failed")

            response = client.get("/health")
            assert response.status_code == 503

            data = json.loads(response.data)
            assert data["status"] == "unhealthy"

    def test_create_incident_success(self, client, sample_incident_data):
        """Test successful incident creation"""
        with patch("app.Incident") as mock_incident_class:
            mock_incident = MagicMock()
            mock_incident.create_incident.return_value = "INC-20240101-ABCD1234"
            mock_incident_class.return_value = mock_incident

            response = client.post(
                "/api/incident",
                data=json.dumps(sample_incident_data),
                content_type="application/json",
            )

            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["success"] is True
            assert "incident_id" in data
            assert data["incident_id"] == "INC-20240101-ABCD1234"

    def test_create_incident_missing_name(self, client):
        """Test incident creation with missing name"""
        invalid_data = {"incident_type": "Test", "description": "Test description"}

        response = client.post(
            "/api/incident",
            data=json.dumps(invalid_data),
            content_type="application/json",
        )

        assert response.status_code == 400

        data = json.loads(response.data)
        assert "error" in data
        assert "required" in data["error"].lower()

    def test_create_incident_missing_type(self, client):
        """Test incident creation with missing incident type"""
        invalid_data = {"name": "Test Incident", "description": "Test description"}

        response = client.post(
            "/api/incident",
            data=json.dumps(invalid_data),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_set_incident_location_success(self, client, sample_coordinates):
        """Test successful location setting"""
        with patch("app.Incident") as mock_incident_class:
            mock_incident = MagicMock()
            mock_incident.set_location.return_value = True
            mock_incident.address = "123 Test Street, Test City"
            mock_incident_class.return_value = mock_incident

            response = client.post(
                "/api/incident/TEST-001/location",
                data=json.dumps(sample_coordinates),
                content_type="application/json",
            )

            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["success"] is True
            assert "address" in data

    def test_set_incident_location_missing_coordinates(self, client):
        """Test location setting with missing coordinates"""
        invalid_data = {"latitude": 37.7749}  # Missing longitude

        response = client.post(
            "/api/incident/TEST-001/location",
            data=json.dumps(invalid_data),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_set_search_area_success(self, client, sample_search_area):
        """Test successful search area setting"""
        with patch("app.Incident") as mock_incident_class:
            mock_incident = MagicMock()
            mock_incident.set_search_area.return_value = True
            mock_incident_class.return_value = mock_incident

            response = client.post(
                "/api/incident/TEST-001/search-area",
                data=json.dumps({"coordinates": sample_search_area}),
                content_type="application/json",
            )

            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["success"] is True

    def test_set_search_area_insufficient_coordinates(self, client):
        """Test search area setting with too few coordinates"""
        invalid_data = {
            "coordinates": [[37.77, -122.42], [37.78, -122.41]]  # Only 2 points
        }

        response = client.post(
            "/api/incident/TEST-001/search-area",
            data=json.dumps(invalid_data),
            content_type="application/json",
        )

        assert response.status_code == 400

    def test_generate_divisions_success(self, client):
        """Test successful division generation"""
        mock_divisions = [
            {"name": "Division A", "area_m2": 35000, "status": "unassigned"},
            {"name": "Division B", "area_m2": 42000, "status": "unassigned"},
        ]

        with patch("app.Incident") as mock_incident_class:
            mock_incident = MagicMock()
            mock_incident.generate_divisions.return_value = mock_divisions
            mock_incident_class.return_value = mock_incident

            response = client.post("/api/incident/TEST-001/divisions")

            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["success"] is True
            assert data["count"] == 2
            assert len(data["divisions"]) == 2


class TestIntegrationFlow:

    def test_complete_incident_workflow(
        self, client, sample_incident_data, sample_coordinates, sample_search_area
    ):
        """Test complete incident creation workflow"""

        with patch("app.Incident") as mock_incident_class:
            mock_incident = MagicMock()
            mock_incident.create_incident.return_value = "INC-20240101-ABCD1234"
            mock_incident.set_location.return_value = True
            mock_incident.address = "123 Test Street"
            mock_incident.set_search_area.return_value = True
            mock_incident.generate_divisions.return_value = [
                {"name": "Division A", "area_m2": 40000, "status": "unassigned"}
            ]
            mock_incident_class.return_value = mock_incident

            # 1. Create incident
            response = client.post(
                "/api/incident",
                data=json.dumps(sample_incident_data),
                content_type="application/json",
            )
            assert response.status_code == 200
            data = json.loads(response.data)
            incident_id = data["incident_id"]

            # 2. Set location
            response = client.post(
                f"/api/incident/{incident_id}/location",
                data=json.dumps(sample_coordinates),
                content_type="application/json",
            )
            assert response.status_code == 200

            # 3. Set search area
            response = client.post(
                f"/api/incident/{incident_id}/search-area",
                data=json.dumps({"coordinates": sample_search_area}),
                content_type="application/json",
            )
            assert response.status_code == 200

            # 4. Generate divisions
            response = client.post(f"/api/incident/{incident_id}/divisions")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["success"] is True
            assert data["count"] == 1
