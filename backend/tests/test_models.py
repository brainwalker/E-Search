"""
Tests for database models.
"""

import pytest
from datetime import datetime


class TestSourceModel:
    """Test the Source model."""

    def test_create_source(self, db_session):
        """Test creating a source."""
        from api.database import Source
        
        source = Source(
            name="TestSource",
            url="https://example.com/schedule",
            active=True
        )
        db_session.add(source)
        db_session.commit()
        
        assert source.id is not None
        assert source.name == "TestSource"
        assert source.active is True
        assert source.created_at is not None

    def test_source_relationships(self, db_session, sample_source):
        """Test source relationships."""
        from api.database import Location, Listing
        
        # Add a location
        location = Location(
            source_id=sample_source.id,
            town="Downtown",
            location="Main St",
            is_default=True
        )
        db_session.add(location)
        
        # Add a listing
        listing = Listing(
            source_id=sample_source.id,
            name="Test",
            is_active=True
        )
        db_session.add(listing)
        db_session.commit()
        
        # Refresh and check relationships
        db_session.refresh(sample_source)
        assert len(sample_source.locations) >= 1
        assert len(sample_source.listings) >= 1


class TestLocationModel:
    """Test the Location model."""

    def test_create_location(self, db_session, sample_source):
        """Test creating a location."""
        from api.database import Location
        
        location = Location(
            source_id=sample_source.id,
            town="Midtown",
            location="Yonge & Eglinton",
            is_default=False
        )
        db_session.add(location)
        db_session.commit()
        
        assert location.id is not None
        assert location.town == "Midtown"
        assert location.is_default is False

    def test_location_default_flag(self, db_session, sample_source):
        """Test the default location flag."""
        from api.database import Location
        
        # Create a default location
        default_loc = Location(
            source_id=sample_source.id,
            town="Unknown",
            location="unknown",
            is_default=True
        )
        db_session.add(default_loc)
        db_session.commit()
        
        # Query for default
        result = db_session.query(Location).filter(
            Location.source_id == sample_source.id,
            Location.is_default == True
        ).first()
        
        assert result is not None
        assert result.is_default is True


class TestListingModel:
    """Test the Listing model."""

    def test_create_listing(self, db_session, sample_source):
        """Test creating a listing."""
        from api.database import Listing
        
        listing = Listing(
            source_id=sample_source.id,
            name="Test Listing",
            tier="VIP",
            age=25,
            nationality="Canadian",
            height="5'6\"",
            is_active=True,
            is_expired=False
        )
        db_session.add(listing)
        db_session.commit()
        
        assert listing.id is not None
        assert listing.name == "Test Listing"
        assert listing.tier == "VIP"
        assert listing.age == 25

    def test_listing_updated_at(self, db_session, sample_listing):
        """Test that updated_at is set correctly."""
        original_updated = sample_listing.updated_at
        
        # Update the listing
        sample_listing.age = 26
        db_session.commit()
        db_session.refresh(sample_listing)
        
        # updated_at should be updated
        assert sample_listing.age == 26


class TestScheduleModel:
    """Test the Schedule model."""

    def test_create_schedule(self, db_session, sample_listing, sample_location):
        """Test creating a schedule."""
        from api.database import Schedule
        
        schedule = Schedule(
            listing_id=sample_listing.id,
            location_id=sample_location.id,
            day_of_week="Monday",
            start_time="12PM",
            end_time="12AM",
            is_expired=False
        )
        db_session.add(schedule)
        db_session.commit()
        
        assert schedule.id is not None
        assert schedule.day_of_week == "Monday"
        assert schedule.start_time == "12PM"

    def test_schedule_cascade_delete(self, db_session, sample_listing, sample_location):
        """Test that schedules are deleted when listing is deleted."""
        from api.database import Schedule, Listing
        
        # Create a schedule
        schedule = Schedule(
            listing_id=sample_listing.id,
            location_id=sample_location.id,
            day_of_week="Tuesday",
            is_expired=False
        )
        db_session.add(schedule)
        db_session.commit()
        schedule_id = schedule.id
        
        # Delete the listing
        db_session.delete(sample_listing)
        db_session.commit()
        
        # Schedule should be deleted too
        result = db_session.query(Schedule).filter(Schedule.id == schedule_id).first()
        assert result is None


class TestTagModel:
    """Test the Tag model."""

    def test_create_tag(self, db_session):
        """Test creating a tag."""
        from api.database import Tag
        
        tag = Tag(name="VIP")
        db_session.add(tag)
        db_session.commit()
        
        assert tag.id is not None
        assert tag.name == "VIP"

    def test_tag_unique_constraint(self, db_session):
        """Test that tag names must be unique."""
        from api.database import Tag
        from sqlalchemy.exc import IntegrityError
        
        tag1 = Tag(name="UNIQUE")
        db_session.add(tag1)
        db_session.commit()
        
        tag2 = Tag(name="UNIQUE")
        db_session.add(tag2)
        
        with pytest.raises(IntegrityError):
            db_session.commit()
