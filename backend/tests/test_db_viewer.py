"""
Tests for database viewer endpoints.
"""

import pytest
from fastapi import status


class TestDatabaseViewer:
    """Test the database viewer endpoints."""

    def test_get_tables(self, client):
        """Test getting list of tables."""
        response = client.get("/db/tables")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "tables" in data
        assert isinstance(data["tables"], list)

    def test_get_table_data_valid(self, client):
        """Test getting data from a valid table."""
        response = client.get("/db/table/sources")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "table" in data
        assert "columns" in data
        assert "data" in data
        assert "total_count" in data

    def test_get_table_data_invalid(self, client):
        """Test getting data from an invalid table."""
        response = client.get("/db/table/nonexistent_table")
        
        # Should return 400 with error message
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "detail" in data
        assert "Invalid table name" in data["detail"]

    def test_get_table_data_sql_injection_attempt(self, client):
        """Test that SQL injection attempts are blocked."""
        # Attempt SQL injection
        response = client.get("/db/table/sources; DROP TABLE users;--")
        
        # Should return 400 because table name is not in whitelist
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_db_stats(self, client):
        """Test getting database statistics."""
        response = client.get("/db/stats")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, dict)

    def test_get_backend_status(self, client):
        """Test getting backend status."""
        response = client.get("/db/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "status" in data
        assert "timestamp" in data

    def test_execute_query_select(self, client):
        """Test executing a SELECT query."""
        response = client.get("/db/query?sql=SELECT 1 as test")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "columns" in data
        assert "data" in data

    def test_execute_query_non_select_blocked(self, client):
        """Test that non-SELECT queries are blocked."""
        response = client.get("/db/query?sql=DROP TABLE sources")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "error" in data
        assert "SELECT" in data["error"]
