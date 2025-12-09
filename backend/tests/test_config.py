"""
Tests for application configuration.
"""

import pytest


class TestSettings:
    """Test the Settings configuration class."""

    def test_settings_defaults(self):
        """Test that settings have sensible defaults."""
        from api.config import settings
        
        assert settings.api_host == "0.0.0.0"
        assert settings.api_port == 8000
        assert settings.api_debug is False
        assert settings.scraper_timeout == 30
        assert settings.scraper_max_retries == 3
        assert settings.log_level == "INFO"

    def test_settings_database_url(self):
        """Test that database URL is set."""
        from api.config import settings
        
        assert settings.database_url is not None
        assert "escort_listings.db" in settings.database_url

    def test_settings_cors_origins(self):
        """Test that CORS origins are configured."""
        from api.config import settings
        
        assert isinstance(settings.cors_origins, list)
        assert len(settings.cors_origins) > 0

    def test_settings_log_paths(self):
        """Test that log paths are valid."""
        from api.config import settings
        
        assert settings.log_dir is not None
        assert settings.log_file is not None
        assert settings.log_file.name == "backend.log"

    def test_settings_data_dir(self):
        """Test that data directory path is valid."""
        from api.config import settings
        
        assert settings.data_dir is not None
        assert "data" in str(settings.data_dir)
