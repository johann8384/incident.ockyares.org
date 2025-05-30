import pytest
import os
import tempfile
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, IncidentManager

# Test database configuration
TEST_DB_CONFIG = {
    'host': os.getenv('TEST_DB_HOST', 'localhost'),
    'port': os.getenv('TEST_DB_PORT', '5433'),  # Different port for test DB
    'database': 'emergency_ops_test',
    'user': os.getenv('TEST_DB_USER', 'postgres'),
    'password': os.getenv('TEST_DB_PASSWORD', 'test_password')
}

@pytest.fixture(scope='session')
def test_database():
    """Create and destroy test database for the entire test session"""
    # Connect to postgres database to create test database
    conn = psycopg2.connect(
        host=TEST_DB_CONFIG['host'],
        port=TEST_DB_CONFIG['port'],
        database='postgres',
        user=TEST_DB_CONFIG['user'],
        password=TEST_DB_CONFIG['password']
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Create test database
    cursor.execute(f"DROP DATABASE IF EXISTS {TEST_DB_CONFIG['database']}")
    cursor.execute(f"CREATE DATABASE {TEST_DB_CONFIG['database']}")
    
    # Connect to test database and create schema
    test_conn = psycopg2.connect(**TEST_DB_CONFIG)
    test_cursor = test_conn.cursor()
    
    # Read and execute schema
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'init', '01_schema.sql')
    if os.path.exists(schema_path):
        with open(schema_path, 'r') as f:
            schema_sql = f.read()
            test_cursor.execute(schema_sql)
    else:
        # Fallback inline schema
        test_cursor.execute("""
            CREATE EXTENSION IF NOT EXISTS postgis;
            
            CREATE TABLE incidents (
                id SERIAL PRIMARY KEY,
                incident_id VARCHAR(50) UNIQUE NOT NULL,
                incident_name VARCHAR(255) NOT NULL,
                incident_type VARCHAR(100) NOT NULL,
                ic_name VARCHAR(255) NOT NULL,
                start_time TIMESTAMP DEFAULT NOW(),
                end_time TIMESTAMP,
                status VARCHAR(50) DEFAULT 'active',
                center_point GEOMETRY(POINT, 4326),
                description TEXT,
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE TABLE search_areas (
                id SERIAL PRIMARY KEY,
                incident_id VARCHAR(50) REFERENCES incidents(incident_id),
                area_name VARCHAR(255) NOT NULL,
                area_type VARCHAR(50) NOT NULL,
                priority INTEGER DEFAULT 1,
                geom GEOMETRY(POLYGON, 4326),
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE TABLE search_divisions (
                id SERIAL PRIMARY KEY,
                incident_id VARCHAR(50) REFERENCES incidents(incident_id),
                division_id VARCHAR(50) NOT NULL,
                division_name VARCHAR(255) NOT NULL,
                assigned_team VARCHAR(255),
                team_leader VARCHAR(255),
                priority INTEGER DEFAULT 1,
                search_type VARCHAR(50) DEFAULT 'primary',
                estimated_duration VARCHAR(50),
                status VARCHAR(50) DEFAULT 'unassigned',
                geom GEOMETRY(POLYGON, 4326),
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE TABLE search_progress (
                id SERIAL PRIMARY KEY,
                incident_id VARCHAR(50) REFERENCES incidents(incident_id),
                division_id VARCHAR(50),
                user_name VARCHAR(255),
                report_type VARCHAR(100),
                description TEXT,
                photo_path TEXT,
                timestamp TIMESTAMP DEFAULT NOW(),
                status VARCHAR(50),
                geom GEOMETRY(POINT, 4326)
            );
        """)
    
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
    # Override database config for testing
    app.config['TESTING'] = True
    app.config['DB_CONFIG'] = test_database
    
    # Patch the IncidentManager to use test database
    original_db_config = IncidentManager.__init__
    
    def patched_init(self):
        original_db_config(self)
        self.db_config = test_database
    
    IncidentManager.__init__ = patched_init
    
    with app.test_client() as client:
        with app.app_context():
            yield client

@pytest.fixture
def incident_manager(test_database):
    """IncidentManager instance configured for testing"""
    manager = IncidentManager()
    manager.db_config = test_database
    
    # Override connect_db method
    def connect_test_db():
        return psycopg2.connect(**test_database)
    
    manager.connect_db = connect_test_db
    return manager

@pytest.fixture
def sample_incident_data():
    """Sample incident data for testing"""
    return {
        'incident_name': 'Test Building Collapse',
        'incident_type': 'Urban Search & Rescue',
        'ic_name': 'Test Commander',
        'latitude': 37.7749,
        'longitude': -122.4194,
        'description': 'Test incident for unit testing'
    }

@pytest.fixture
def sample_search_area():
    """Sample search area coordinates"""
    return [
        [-122.42, 37.77],
        [-122.41, 37.77],
        [-122.41, 37.78],
        [-122.42, 37.78],
        [-122.42, 37.77]  # Closed polygon
    ]

@pytest.fixture
def sample_teams():
    """Sample team data"""
    return [
        {
            'team_id': 'team1',
            'team_name': 'Test Team Alpha',
            'team_leader': 'Captain Test'
        },
        {
            'team_id': 'team2',
            'team_name': 'Test Team Bravo',
            'team_leader': 'Lieutenant Test'
        }
    ]
