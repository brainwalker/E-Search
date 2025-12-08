"""
Pytest configuration and fixtures for E-Search tests.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.database import Base, get_db
from api.main import app


# Create an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override the get_db dependency for testing."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """Create a test client with database override."""
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    
    # Use TestClient directly without context manager for compatibility
    test_client = TestClient(app)
    yield test_client
    
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_source(db_session):
    """Create a sample source for testing."""
    from api.database import Source
    
    source = Source(
        name="TestSource",
        url="https://example.com/schedule",
        base_url="https://example.com/",
        image_base_url="https://example.com/images/",
        active=True
    )
    db_session.add(source)
    db_session.commit()
    db_session.refresh(source)
    return source


@pytest.fixture
def sample_location(db_session, sample_source):
    """Create a sample location for testing."""
    from api.database import Location
    
    location = Location(
        source_id=sample_source.id,
        town="Downtown",
        location="Main Street",
        is_default=True
    )
    db_session.add(location)
    db_session.commit()
    db_session.refresh(location)
    return location


@pytest.fixture
def sample_listing(db_session, sample_source):
    """Create a sample listing for testing."""
    from api.database import Listing
    
    listing = Listing(
        source_id=sample_source.id,
        name="Test Listing",
        tier="VIP",
        age=25,
        nationality="Canadian",
        is_active=True,
        is_expired=False
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing
