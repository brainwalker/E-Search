"""
Base classes for the Crawlee-based scraper system.

This module defines the abstract base class and data structures
used by all site-specific scrapers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)


class ScraperType(Enum):
    """Types of scrapers based on site requirements."""
    STATIC = "static"           # httpx + BeautifulSoup (fast)
    JAVASCRIPT = "javascript"   # Playwright (JS rendering)
    STEALTH = "stealth"         # Camoufox (anti-bot bypass)


@dataclass
class SiteConfig:
    """Configuration for a scraping source."""
    name: str                           # Full display name
    short_name: str                     # Database identifier (e.g., 'SFT')
    schedule_url: str                   # Schedule page URL
    base_url: str                       # Base URL for building profile URLs
    scraper_type: ScraperType           # Which crawler to use
    image_base_url: Optional[str] = None  # Base URL for images
    requires_age_gate: bool = False     # Needs age verification handling
    rate_limit_seconds: float = 1.0     # Delay between requests
    selectors: Dict[str, str] = field(default_factory=dict)  # CSS selectors
    enabled: bool = True                # Whether to include in scrapes


@dataclass
class ScheduleItem:
    """A single schedule entry from the schedule page."""
    name: str
    profile_url: str
    day_of_week: str
    location: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    tier: Optional[str] = None


@dataclass
class ScrapedListing:
    """Standardized listing data after scraping."""
    name: str
    profile_url: str
    source: str

    # Schedule info
    schedules: List[Dict] = field(default_factory=list)

    # Profile details
    tier: Optional[str] = None
    age: Optional[int] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    bust: Optional[str] = None
    bust_type: Optional[str] = None
    measurements: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    service_type: Optional[str] = None

    # Media and tags
    images: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)

    # Raw data for debugging
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScrapeResult:
    """Result of a scraping operation."""
    source: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    total: int = 0
    new: int = 0
    updated: int = 0
    errors: int = 0
    error_details: List[Dict] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.errors == 0

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    def to_dict(self) -> Dict:
        return {
            'source': self.source,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'total': self.total,
            'new': self.new,
            'updated': self.updated,
            'errors': self.errors,
            'error_details': self.error_details[:10],  # Limit error details
            'success': self.success,
        }


class BaseScraper(ABC):
    """
    Abstract base class for all site scrapers.

    Subclasses must implement:
    - scrape_schedule(): Parse the schedule page
    - scrape_profile(): Parse an individual profile page

    Optional overrides:
    - normalize_listing(): Custom data normalization
    - save_listing(): Custom database saving logic
    """

    def __init__(self, config: SiteConfig, db_session=None):
        """
        Initialize the scraper.

        Args:
            config: Site configuration
            db_session: SQLAlchemy database session (optional)
        """
        self.config = config
        self.db = db_session
        self.result = ScrapeResult(
            source=config.short_name,
            started_at=datetime.utcnow()
        )
        self.logger = logging.getLogger(f"scraper.{config.short_name}")

    @abstractmethod
    async def scrape_schedule(self) -> List[ScheduleItem]:
        """
        Scrape the schedule page and return list of schedule items.

        Returns:
            List of ScheduleItem objects
        """
        pass

    @abstractmethod
    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape an individual profile page.

        Args:
            profile_url: URL or slug of the profile

        Returns:
            Dictionary of profile data
        """
        pass

    def normalize_listing(self, schedule_item: ScheduleItem, profile_data: Dict) -> ScrapedListing:
        """
        Convert raw scraped data to standardized ScrapedListing.

        Override this method for site-specific normalization.
        """
        return ScrapedListing(
            name=schedule_item.name,
            profile_url=schedule_item.profile_url,
            source=self.config.short_name,
            tier=profile_data.get('tier') or schedule_item.tier,
            age=profile_data.get('age'),
            nationality=profile_data.get('nationality'),
            ethnicity=profile_data.get('ethnicity'),
            height=profile_data.get('height'),
            weight=profile_data.get('weight'),
            bust=profile_data.get('bust'),
            bust_type=profile_data.get('bust_type'),
            measurements=profile_data.get('measurements'),
            hair_color=profile_data.get('hair_color'),
            eye_color=profile_data.get('eye_color'),
            service_type=profile_data.get('service_type'),
            images=profile_data.get('images', []),
            tags=profile_data.get('tags', []),
            schedules=[{
                'day_of_week': schedule_item.day_of_week,
                'location': schedule_item.location,
                'start_time': schedule_item.start_time,
                'end_time': schedule_item.end_time,
            }],
            raw_data=profile_data,
        )

    def _get_date_from_day_of_week(self, day_of_week: str) -> datetime:
        """Convert day of week string to actual date (next occurrence of that day)."""
        day_map = {
            'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
            'Friday': 4, 'Saturday': 5, 'Sunday': 6
        }
        today = datetime.now()
        target_day = day_map.get(day_of_week)

        if target_day is None:
            return today.replace(hour=0, minute=0, second=0, microsecond=0)

        current_day = today.weekday()
        days_ahead = target_day - current_day
        if days_ahead <= 0:
            days_ahead += 7

        target_date = today + timedelta(days=days_ahead)
        return target_date.replace(hour=0, minute=0, second=0, microsecond=0)

    async def save_listing(self, listing: ScrapedListing) -> bool:
        """
        Save or update a listing in the database.

        Override this method for custom database logic.
        Returns True if new, False if updated.
        """
        if not self.db:
            self.logger.warning("No database session - skipping save")
            return False

        # Import here to avoid circular imports
        from api.database import Listing, Schedule, Source, Tag, Location

        # Get or create source
        source = self.db.query(Source).filter_by(name=self.config.short_name).first()
        if not source:
            source = Source(
                name=self.config.short_name,
                url=self.config.schedule_url,
                base_url=self.config.base_url,
                image_base_url=self.config.image_base_url,
                active=True
            )
            self.db.add(source)
            self.db.flush()

        # Check if listing exists
        existing = self.db.query(Listing).filter_by(
            name=listing.name,
            source_id=source.id
        ).first()

        is_new = existing is None

        if is_new:
            db_listing = Listing(
                name=listing.name,
                profile_url=listing.profile_url,
                source_id=source.id,
            )
            self.db.add(db_listing)
        else:
            db_listing = existing

        # Update fields
        db_listing.tier = listing.tier
        db_listing.age = listing.age
        db_listing.nationality = listing.nationality
        db_listing.ethnicity = listing.ethnicity
        db_listing.height = listing.height
        db_listing.weight = listing.weight
        db_listing.bust = listing.bust
        db_listing.bust_type = listing.bust_type
        db_listing.measurements = listing.measurements
        db_listing.hair_color = listing.hair_color
        db_listing.eye_color = listing.eye_color
        db_listing.service_type = listing.service_type
        db_listing.images = json.dumps(listing.images) if listing.images else None
        db_listing.is_active = True
        db_listing.is_expired = False

        self.db.flush()

        # Handle schedules
        for schedule_data in listing.schedules:
            # Match location
            location_str = schedule_data.get('location', 'Unknown')
            location = self.db.query(Location).filter(
                Location.source_id == source.id,
                Location.town.ilike(f"%{location_str.split(',')[0] if ',' in location_str else location_str}%")
            ).first()

            if not location:
                # Use default location
                location = self.db.query(Location).filter(
                    Location.source_id == source.id,
                    Location.is_default == True
                ).first()

            location_id = location.id if location else None
            day_of_week = schedule_data.get('day_of_week')
            schedule_date = self._get_date_from_day_of_week(day_of_week) if day_of_week else None

            # Check for existing schedule
            existing_schedule = self.db.query(Schedule).filter_by(
                listing_id=db_listing.id,
                day_of_week=day_of_week,
                location_id=location_id
            ).first()

            if existing_schedule:
                existing_schedule.date = schedule_date
                existing_schedule.start_time = schedule_data.get('start_time')
                existing_schedule.end_time = schedule_data.get('end_time')
                existing_schedule.is_expired = False
            else:
                new_schedule = Schedule(
                    listing_id=db_listing.id,
                    day_of_week=day_of_week,
                    date=schedule_date,
                    location_id=location_id,
                    start_time=schedule_data.get('start_time'),
                    end_time=schedule_data.get('end_time'),
                )
                self.db.add(new_schedule)

        # Handle tags
        existing_tag_ids = {t.id for t in db_listing.tags}
        for tag_name in listing.tags:
            tag = self.db.query(Tag).filter_by(name=tag_name).first()
            if not tag:
                tag = Tag(name=tag_name)
                self.db.add(tag)
                self.db.flush()
            if tag.id not in existing_tag_ids:
                db_listing.tags.append(tag)

        self.db.commit()
        return is_new

    async def run(self) -> ScrapeResult:
        """
        Main entry point - orchestrates the full scraping process.

        1. Scrape schedule page
        2. For each listing, scrape profile
        3. Normalize and save data
        4. Return results
        """
        self.logger.info(f"Starting scrape for {self.config.name}")

        try:
            # Step 1: Scrape schedule page
            schedule_items = await self.scrape_schedule()
            self.result.total = len(schedule_items)
            self.logger.info(f"Found {len(schedule_items)} schedule items")

            # Deduplicate by profile URL to avoid scraping same profile multiple times
            seen_profiles = {}
            for item in schedule_items:
                if item.profile_url not in seen_profiles:
                    seen_profiles[item.profile_url] = item
                else:
                    # Merge schedule into existing item's data
                    pass  # We'll handle this in normalize_listing

            unique_profiles = list(seen_profiles.values())
            self.logger.info(f"Processing {len(unique_profiles)} unique profiles")

            # Step 2: Process each listing
            for idx, item in enumerate(unique_profiles, 1):
                try:
                    self.logger.info(f"[{idx}/{len(unique_profiles)}] Scraping {item.name} ({item.profile_url})")

                    # Scrape profile
                    profile_data = await self.scrape_profile(item.profile_url)

                    # Normalize
                    listing = self.normalize_listing(item, profile_data)

                    # Save
                    is_new = await self.save_listing(listing)

                    if is_new:
                        self.result.new += 1
                    else:
                        self.result.updated += 1

                    # Progress update every 5 profiles
                    if idx % 5 == 0:
                        self.logger.info(f"Progress: {idx}/{len(unique_profiles)} profiles scraped")

                except Exception as e:
                    self.result.errors += 1
                    self.result.error_details.append({
                        'profile_url': item.profile_url,
                        'error': str(e),
                    })
                    self.logger.error(f"Error scraping {item.profile_url}: {e}")
                    # Continue to next profile instead of failing entire scrape

            self.result.completed_at = datetime.utcnow()
            duration = self.result.duration_seconds or 0
            self.logger.info(
                f"✅ Scrape complete in {duration:.1f}s: {self.result.new} new, "
                f"{self.result.updated} updated, {self.result.errors} errors"
            )

            return self.result

        except Exception as e:
            self.result.errors += 1
            self.result.error_details.append({'error': str(e)})
            self.result.completed_at = datetime.utcnow()
            self.logger.error(f"Scrape failed: {e}")
            raise
