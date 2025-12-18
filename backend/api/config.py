"""
Application Configuration
Loads settings from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    database_url: str = "sqlite:///./data/escort_listings.db"
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False
    
    # CORS Configuration - includes "null" for file:// URLs and "*" for development
    cors_origins: List[str] = ["*"]  # Allow all origins for development
    
    # Frontend Configuration
    frontend_url: str = "http://localhost:3000"
    
    # Scraper Configuration
    scraper_timeout: int = 30
    scraper_max_retries: int = 3
    scraper_user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    
    # Logging Configuration
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Paths
    @property
    def log_dir(self) -> Path:
        """Get the log directory path."""
        return Path(__file__).parent.parent.parent / "logs"
    
    @property
    def log_file(self) -> Path:
        """Get the log file path."""
        return self.log_dir / "backend.log"
    
    @property
    def data_dir(self) -> Path:
        """Get the data directory path."""
        return Path(__file__).parent.parent / "data"

    class Config:
        # Only load .env if it exists to avoid permission errors
        env_file = ".env" if __import__("pathlib").Path(".env").exists() else None
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


# Global settings instance
settings = Settings()
