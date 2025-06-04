import pytest
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.database import DatabaseManager
from models.incident import Incident

# Test database configuration
TEST_DB_CONFIG = {
    "host": os.getenv("TEST_DB_HOST", "localhost"),
    "port": os.getenv("TEST_DB_PORT", "5433"),
    "database": "emergency_ops_test",
    "user": os.getenv("TEST_DB_USER", "postgres"),
    "password": os.getenv("TEST_DB_PASSWORD", "test_password"),
}


@pytest.fixture(scope="session")
def test_database():
    """Create and destroy test database for the entire test session"""
    # Connect to postgres database to create test database
    conn = psycopg2.connect(
        host=TEST_DB_CONFIG["host"],
        port=TEST_DB_CONFIG["port"],
        database="postgres",
        user=TEST_DB_CONFIG["user"],
        password=TEST_DB_CONFIG["password"],
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    # Create test database
    cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_CONFIG['database']}")
    cursor.execute(f"CREATE DATABASE {TEST_DB_CONFIG['database']}")

    # Connect to test database and create schema
    test_conn = psycopg2.connect(**TEST_DB_CONFIG)
    test_cursor = test_conn.cursor()

    # Enable PostGIS and create schema
    test_cursor.execute(
        """
        CREATE EXTENSION IF NOT EXISTS postgis;
        
        CREATE TABLE incidents (
            id SERIAL PRIMARY KEY,
            incident_id VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            incident_type VARCHAR(100) NOT NULL,
            description TEXT,
            incident_location GEOMETRY(POINT, 4326),
            address TEXT,
            search_area GEOMETRY(POLYGON, 4326),
            created_at TIMESTAMP DEFAULT NOW(),
            status VARCHAR(50) DEFAULT 'active'
        );
        
        CREATE TABLE search_divisions (
            id SERIAL PRIMARY KEY,
            incident_id VARCHAR(50) REFERENCES incidents(incident_id),
            division_name VARCHAR(100) NOT NULL,
            area_geometry GEOMETRY(POLYGON, 4326),
            estimated_area_m2 FLOAT,
            assigned_team VARCHAR(255),
            status VARCHAR(50) DEFAULT 'unassigned',
            created_at TIMESTAMP DEFAULT NOW()
        );
        
        CREATE INDEX idx_incidents_location ON incidents USING GIST(incident_location);
        CREATE INDEX idx_incidents_search_area ON incidents USING GIST(search_area);
        CREATE INDEX idx_divisions_geometry ON search_divisions USING GIST(area_geometry);
    """
    )

    test_conn.commit()
    test_cursor.close()
    test_conn.close()

    yield TEST_DB_CONFIG

    # Cleanup: Drop test database
    cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_CONFIG['database']}")
    cursor.close()
    conn.close()


@pytest.fixture
def client(test_database):
    """Flask test client with test database configuration"""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.test_client() as client:
        with app.app_context():
            yield client


@pytest.fixture
def db_manager(test_database):
    """DatabaseManager instance configured for testing"""
    manager = DatabaseManager()
    manager.db_config = test_database
    return manager


@pytest.fixture
def incident(db_manager):
    """Incident instance configured for testing"""
    return Incident(db_manager)


@pytest.fixture
def sample_incident_data():
    """Sample incident data for testing"""
    return {
        "name": "Test Building Collapse",
        "incident_type": "Building Collapse",
        "description": "Test incident for unit testing",
    }


@pytest.fixture
def sample_coordinates():
    """Sample coordinates for testing"""
    return {"latitude": 37.7749, "longitude": -122.4194}


@pytest.fixture
def sample_search_area():
    """Sample search area polygon coordinates"""
    return [
        [37.77, -122.42],
        [37.77, -122.41],
        [37.78, -122.41],
        [37.78, -122.42],
        [37.77, -122.42],  # Closed polygon
    ]
