import pytest
from models.database import DatabaseManager


class TestDatabaseManager:

    def test_database_connection(self, db_manager):
        """Test database connection works"""
        conn = db_manager.connect()
        assert conn is not None
        db_manager.close()

    def test_execute_query_select(self, db_manager):
        """Test query execution with fetch"""
        result = db_manager.execute_query("SELECT 1 as test", fetch=True)
        assert len(result) == 1
        assert result[0]["test"] == 1

    def test_execute_query_insert(self, db_manager):
        """Test query execution without fetch"""
        # Insert test incident
        query = """
        INSERT INTO incidents (incident_id, name, incident_type)
        VALUES (%s, %s, %s)
        """

        rowcount = db_manager.execute_query(
            query, ("TEST-001", "Test Incident", "Test Type")
        )

        assert rowcount == 1

        # Verify it was inserted
        result = db_manager.execute_query(
            "SELECT * FROM incidents WHERE incident_id = %s", ("TEST-001",), fetch=True
        )

        assert len(result) == 1
        assert result[0]["name"] == "Test Incident"

    def test_create_tables(self, db_manager):
        """Test table creation"""
        # Tables should already exist from conftest.py
        # Test that we can query them
        result = db_manager.execute_query(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'",
            fetch=True,
        )

        table_names = [row["table_name"] for row in result]
        assert "incidents" in table_names
        assert "search_divisions" in table_names

    def test_postgis_enabled(self, db_manager):
        """Test that PostGIS extension is enabled"""
        result = db_manager.execute_query(
            "SELECT name FROM pg_available_extensions WHERE name = 'postgis' AND installed_version IS NOT NULL",
            fetch=True,
        )

        assert len(result) == 1
        assert result[0]["name"] == "postgis"
