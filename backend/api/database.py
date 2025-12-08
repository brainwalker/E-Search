from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Table, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

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
    created_at = Column(DateTime, default=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

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
    source_id = Column(Integer, ForeignKey('sources.id'))

    # Basic info
    name = Column(String, nullable=False)
    profile_url = Column(String)
    tier = Column(String)  # PLATINUM VIP, ELITE, ULTRA VIP, etc.

    # Personal details
    age = Column(Integer)
    nationality = Column(String)
    height = Column(String)
    weight = Column(String)
    bust = Column(String)
    bust_type = Column(String)  # Natural or Enhanced
    eye_color = Column(String)
    hair_color = Column(String)
    service_type = Column(String)  # GF ENTERTAINER, etc.

    # Rates
    incall_30min = Column(Integer)
    incall_45min = Column(Integer)
    incall_1hr = Column(Integer)
    outcall_1hr = Column(Integer)
    rate_notes = Column(Text)

    # Images
    images = Column(Text)  # JSON array of image URLs

    # Metadata
    is_active = Column(Boolean, default=True)
    is_expired = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    source = relationship("Source", back_populates="listings")
    schedules = relationship("Schedule", back_populates="listing", cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=listing_tags, back_populates="listings")


class Schedule(Base):
    __tablename__ = 'schedules'

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey('listings.id'), index=True)
    location_id = Column(Integer, ForeignKey('locations.id'), index=True)  # Reference to Location table

    day_of_week = Column(String, index=True)  # Monday, Tuesday, etc. - indexed for filtering
    date = Column(DateTime)  # Actual date if known
    start_time = Column(String)  # 12PM
    end_time = Column(String)  # 12AM

    is_expired = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

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


# Database setup
engine = create_engine('sqlite:///./data/escort_listings.db', echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
