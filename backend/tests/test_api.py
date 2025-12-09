"""
Tests for API endpoints.
"""

import pytest
from fastapi import status


class TestRootEndpoint:
    """Test the root endpoint."""

    def test_root_returns_json(self, client):
        """Test that root endpoint returns expected JSON."""
        response = client.get("/")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "message" in data
        assert data["message"] == "E-Search API"
        assert "version" in data


class TestSourcesEndpoint:
    """Test the sources endpoints."""

    def test_get_sources_empty(self, client):
        """Test getting sources when database is empty."""
        response = client.get("/api/sources")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)

    def test_get_sources_with_data(self, client, sample_source):
        """Test getting sources when data exists."""
        response = client.get("/api/sources")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1


class TestListingsEndpoint:
    """Test the listings endpoints."""

    def test_get_listings_empty(self, client):
        """Test getting listings when database is empty."""
        response = client.get("/api/listings")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    def test_get_listings_with_data(self, client, sample_listing):
        """Test getting listings when data exists."""
        response = client.get("/api/listings")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) >= 1

    def test_get_listings_with_filters(self, client, sample_listing):
        """Test filtering listings."""
        # Filter by tier
        response = client.get("/api/listings?tier=VIP")
        assert response.status_code == status.HTTP_200_OK
        
        # Filter by search
        response = client.get("/api/listings?search=Test")
        assert response.status_code == status.HTTP_200_OK
        
        # Hide expired
        response = client.get("/api/listings?hide_expired=true")
        assert response.status_code == status.HTTP_200_OK

    def test_get_listing_not_found(self, client):
        """Test getting a non-existent listing."""
        response = client.get("/api/listings/99999")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestStatsEndpoint:
    """Test the stats endpoint."""

    def test_get_stats(self, client):
        """Test getting statistics."""
        response = client.get("/api/stats")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_listings" in data
        assert "active_listings" in data
        assert "total_sources" in data


class TestTagsEndpoint:
    """Test the tags endpoint."""

    def test_get_tags_empty(self, client):
        """Test getting tags when database is empty."""
        response = client.get("/api/tags")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)


class TestTiersEndpoint:
    """Test the tiers endpoint."""

    def test_get_tiers_empty(self, client):
        """Test getting tiers when database is empty."""
        response = client.get("/api/tiers")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert isinstance(data, list)
