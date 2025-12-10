from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Table, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime, timezone


def utc_now():
    """Return current UTC time (timezone-aware). Replaces deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)

Base = declarative_base()

# Association table for many-to-many relationship between listings and tags
listing_tags = Table('listing_tags', Base.metadata,
    Column('listing_id', Integer, ForeignKey('listings.id')),
    Column('tag_id', Integer, ForeignKey('tags.id'))
)


class Source(Base):
    __tablename__ = 'sources'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    url = Column(String, nullable=False)  # Schedule page URL
    base_url = Column(String)  # Base URL for profiles (e.g., https://example.com/escorts/)
    image_base_url = Column(String)  # Base URL for images (e.g., https://example.com/thumbnails/)
    active = Column(Boolean, default=True)
    last_scraped = Column(DateTime)
    created_at = Column(DateTime, default=utc_now)

    listings = relationship("Listing", back_populates="source")
    locations = relationship("Location", back_populates="source")
    tiers = relationship("Tier", back_populates="source")


class Location(Base):
    __tablename__ = 'locations'

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('sources.id'), nullable=False, index=True)

    # Location details
    town = Column(String, nullable=False, index=True)  # Vaughan, Midtown, Downtown, etc.
    location = Column(String, nullable=False)  # Yonge & Eglinton, unknown, etc.
    address = Column(String)  # Optional full address
    notes = Column(Text)  # Optional notes about the location

    # For matching/searching
    is_default = Column(Boolean, default=False, index=True)  # Mark the "Unknown, unknown" as default

    # Metadata
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    source = relationship("Source", back_populates="locations")
    schedules = relationship("Schedule", back_populates="location")

    # Composite index for location matching
    __table_args__ = (
        Index('ix_location_source_town_location', 'source_id', 'town', 'location'),
    )


class Listing(Base):
    __tablename__ = 'listings'

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('sources.id'), index=True)

    # Basic info
    name = Column(String, nullable=False, index=True)
    profile_url = Column(String)
    tier = Column(String, index=True)  # PLATINUM VIP, ELITE, ULTRA VIP, etc.

    # Personal details
    age = Column(Integer)
    nationality = Column(String)
    ethnicity = Column(String)  # Race/ethnicity (e.g., Latina, Asian, etc.)
    height = Column(String)
    weight = Column(String)
    measurements = Column(String)  # Chest/Waist/Hips (e.g., 34DD-28-38)
    bust = Column(String)
    bust_type = Column(String)  # Natural or Enhanced
    eye_color = Column(String)
    hair_color = Column(String)
    service_type = Column(String)  # GF ENTERTAINER, GFE, etc.

    # Note: Rates are now retrieved via the tier field from the tiers table
    # This avoids data duplication and ensures consistent pricing

    # Images
    images = Column(Text)  # JSON array of image URLs

    # Metadata
    is_active = Column(Boolean, default=True, index=True)
    is_expired = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=utc_now)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Relationships
    source = relationship("Source", back_populates="listings")
    schedules = relationship("Schedule", back_populates="listing", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=listing_tags, back_populates="listings")
    
    # Composite indexes for common query patterns
    __table_args__ = (
        Index('ix_listings_source_expired', 'source_id', 'is_expired'),
        Index('ix_listings_source_tier', 'source_id', 'tier'),
        Index('ix_listings_updated_at', 'updated_at'),
    )


class Schedule(Base):
    __tablename__ = 'schedules'

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey('listings.id'), index=True)
    location_id = Column(Integer, ForeignKey('locations.id'), nullable=False, index=True)  # Reference to Location table - always provided by scraper

    day_of_week = Column(String, nullable=False, index=True)  # Monday, Tuesday, etc. - indexed for filtering, always provided by scraper
    date = Column(DateTime)  # Actual date if known
    start_time = Column(String)  # 12PM
    end_time = Column(String)  # 12AM

    is_expired = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=utc_now)

    listing = relationship("Listing", back_populates="schedules")
    location = relationship("Location", back_populates="schedules")


class Tier(Base):
    __tablename__ = 'tiers'

    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey('sources.id'), nullable=False, index=True)

    # Tier details
    tier = Column(String, nullable=False)  # Elite, VIP, Ultra VIP, Platinum VIP
    star = Column(Integer, nullable=False)  # 1, 2, 3, 4
    incall_30min = Column(String)  # Price as string (e.g., "$160")
    incall_45min = Column(String)  # Price as string (e.g., "$200")
    incall_1hr = Column(String)  # Price as string (e.g., "$250")
    outcall_per_hr = Column(String)  # Price as string (e.g., "$270" or "Unknown")

    # Metadata
    created_at = Column(DateTime, default=utc_now)

    # Relationships
    source = relationship("Source", back_populates="tiers")

    # Composite index for tier lookup
    __table_args__ = (
        Index('ix_tier_source_tier', 'source_id', 'tier'),
        Index('ix_tier_source_star', 'source_id', 'star'),
    )


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    listings = relationship("Listing", secondary=listing_tags, back_populates="tags")


# Database setup - import settings for database URL
from api.config import settings

# Configure engine with connection pooling for better performance
engine = create_engine(
    settings.database_url,
    echo=False,
    pool_size=5,           # Number of connections to keep in pool
    max_overflow=10,       # Additional connections allowed beyond pool_size
    pool_pre_ping=True,    # Verify connections before use (handles stale connections)
    pool_recycle=3600,     # Recycle connections after 1 hour
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
