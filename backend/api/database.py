from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Table
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
    url = Column(String, nullable=False)
    active = Column(Boolean, default=True)
    last_scraped = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    listings = relationship("Listing", back_populates="source")


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
    listing_id = Column(Integer, ForeignKey('listings.id'))

    day_of_week = Column(String)  # Monday, Tuesday, etc.
    date = Column(DateTime)  # Actual date if known
    start_time = Column(String)  # 12PM
    end_time = Column(String)  # 12AM
    location = Column(String)  # Specific location for this schedule

    is_expired = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    listing = relationship("Listing", back_populates="schedules")


class Tag(Base):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    listings = relationship("Listing", secondary=listing_tags, back_populates="tags")


# Database setup
engine = create_engine('sqlite:///./escort_listings.db', echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
