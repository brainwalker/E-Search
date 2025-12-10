"""
Base classes for the Crawlee-based scraper system.

This module defines the abstract base class and data structures
used by all site-specific scrapers.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone
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

    # Number of listings to process before committing (batch size)
    COMMIT_BATCH_SIZE = 10

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
            started_at=datetime.now(timezone.utc)
        )
        self.logger = logging.getLogger(f"scraper.{config.short_name}")
        # Child loggers of 'scraper' will inherit handlers from parent 'scraper' logger
        # which is configured in main.py to prevent duplicates
        # Counter for batch commits
        self._pending_commits = 0
    
    def _parse_sft_location_fallback(self, location_str: str) -> tuple:
        """
        Fallback SFT location parser if the main one isn't available.
        Tries to extract town name from common patterns.
        """
        location_str = location_str.strip()
        known_towns = ['Vaughan', 'Midtown', 'Downtown', 'Etobicoke', 'Oakville',
                      'Mississauga', 'Brampton', 'North York', 'Scarborough',
                      'Markham', 'Richmond Hill']
        
        location_lower = location_str.lower()
        for town in sorted(known_towns, key=len, reverse=True):
            if location_lower.startswith(town.lower()):
                # Extract location part
                town_end = len(town)
                while town_end < len(location_str) and location_str[town_end] == ' ':
                    town_end += 1
                location_part = location_str[town_end:].strip()
                return (town, location_part if location_part else "unknown")
        
        # No match found
        return (location_str, "unknown")

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

    def normalize_listing(self, schedule_item: ScheduleItem, profile_data: Dict, all_schedule_items: Optional[List[ScheduleItem]] = None) -> ScrapedListing:
        """
        Convert raw scraped data to standardized ScrapedListing.

        Override this method for site-specific normalization.

        Args:
            schedule_item: First schedule item (for name, profile_url, tier)
            profile_data: Scraped profile data
            all_schedule_items: All schedule items for this profile (defaults to [schedule_item])
        """
        if all_schedule_items is None:
            all_schedule_items = [schedule_item]

        # Prefer schedule tier over profile tier (schedule is more current)
        tier = schedule_item.tier or profile_data.get('tier')

        # Convert all schedule items to schedule dicts
        schedules = [{
            'day_of_week': item.day_of_week,
            'location': item.location,
            'start_time': item.start_time,
            'end_time': item.end_time,
        } for item in all_schedule_items]

        return ScrapedListing(
            name=schedule_item.name,
            profile_url=schedule_item.profile_url,
            source=self.config.short_name,
            tier=tier,
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
            schedules=schedules,
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
            # Skip OUTCALL schedules for all sources
            location_str = schedule_data.get('location', 'Unknown')
            if not location_str or location_str.strip() == '':
                location_str = 'Unknown'
            
            # Skip OUTCALL locations
            if location_str.upper() == 'OUTCALL' or 'OUTCALL' in location_str.upper():
                self.logger.debug(f"Skipping OUTCALL schedule for listing '{listing.name}'")
                continue
            
            # Normalize location string - strip whitespace and handle different formats
            location_str = location_str.strip()
            
            # Parse location based on source format
            # For SFT: location format is "TOWN LOCATION_DETAIL" (e.g., "MIDTOWN YONGE & EGLINTON")
            # For DD: location format is "town, location" (e.g., "Vaughan, unknown")
            
            town_name = None
            location_detail = None
            
            if ',' in location_str:
                # DD format: "town, location"
                parts = location_str.split(',', 1)
                town_name = parts[0].strip()
                location_detail = parts[1].strip() if len(parts) > 1 else "unknown"
            else:
                # SFT format: try to parse "TOWN LOCATION_DETAIL"
                # Always use fallback parser first (more reliable), then try imported one if available
                town_name, location_detail = self._parse_sft_location_fallback(location_str)
                
                # Try to use the imported parser if available (it has better normalization)
                try:
                    from ..sites.sft import parse_sft_location
                    parsed_town, parsed_location = parse_sft_location(location_str)
                    # Use parsed result if it successfully split the location
                    if parsed_town != location_str and parsed_town != location_str.title():
                        town_name, location_detail = parsed_town, parsed_location
                        self.logger.debug(
                            f"Used imported parser for '{location_str}' -> town='{town_name}', location='{location_detail}'"
                        )
                    else:
                        self.logger.debug(
                            f"Imported parser didn't improve parsing for '{location_str}', using fallback result"
                        )
                except (ImportError, AttributeError):
                    # Fallback parser already used, that's fine
                    pass
                except Exception as e:
                    self.logger.debug(f"Error in parse_sft_location (non-critical): {e}")
                
                self.logger.debug(
                    f"Final parsed location '{location_str}' -> town='{town_name}', location='{location_detail}'"
                )
            
            # Normalize location_detail for better matching (handle common variations)
            normalized_location_detail = None
            if location_detail and location_detail.lower() != 'unknown':
                import re
                # Remove common prefixes/suffixes that might not be in database
                normalized_location_detail = location_detail.strip()
                
                # Remove parenthetical suffixes like "(AIRPORT)", "(NEAR DUNDAS SQ)"
                normalized_location_detail = re.sub(r'\s*\([^)]+\)\s*$', '', normalized_location_detail)
                
                # Remove "NEAR" prefix (case-insensitive)
                normalized_location_detail = re.sub(r'^NEAR\s+', '', normalized_location_detail, flags=re.IGNORECASE)
                
                # Normalize spaces (multiple spaces to single, trim)
                normalized_location_detail = ' '.join(normalized_location_detail.split())
                
                # Normalize hyphens/spaces in HWY patterns: "HWY 427" -> "HWY-427", "HWY427" -> "HWY-427"
                normalized_location_detail = re.sub(r'HWY\s*(\d+)', r'HWY-\1', normalized_location_detail, flags=re.IGNORECASE)
                
                # Handle common typos: "Trafalger" -> "Trafalgar"
                normalized_location_detail = normalized_location_detail.replace('Trafalger', 'Trafalgar')
                normalized_location_detail = normalized_location_detail.replace('trafalger', 'Trafalgar')
                
                # Normalize "&" spacing: "FRONT  & SPADINA" -> "Front & Spadina"
                normalized_location_detail = re.sub(r'\s*&\s*', ' & ', normalized_location_detail)
                
                # Capitalize properly (title case but preserve acronyms)
                words = normalized_location_detail.split()
                normalized_words = []
                for word in words:
                    # Preserve common acronyms and abbreviations
                    if word.upper() in ['HWY', 'SQ', 'ST', 'RD', 'E', 'W', 'N', 'S']:
                        normalized_words.append(word.upper())
                    elif word.upper() in ['&', 'AND']:
                        normalized_words.append('&')
                    else:
                        normalized_words.append(word.capitalize())
                normalized_location_detail = ' '.join(normalized_words)
                
                self.logger.debug(
                    f"Normalized location_detail: '{location_detail}' -> '{normalized_location_detail}'"
                )
            
            # Try multiple matching strategies
            # Strategy 1: Match both town and location exactly (case-insensitive)
            if town_name and location_detail:
                location = self.db.query(Location).filter(
                    Location.source_id == source.id,
                    Location.town.ilike(town_name),
                    Location.location.ilike(location_detail)
                ).first()
            
            # Strategy 2: Match town exactly, normalized location exactly
            if not location and town_name and normalized_location_detail:
                location = self.db.query(Location).filter(
                    Location.source_id == source.id,
                    Location.town.ilike(town_name),
                    Location.location.ilike(normalized_location_detail)
                ).first()
            
            # Strategy 3: Match town exactly, location with wildcards (original)
            if not location and town_name and location_detail:
                location = self.db.query(Location).filter(
                    Location.source_id == source.id,
                    Location.town.ilike(town_name),
                    Location.location.ilike(f"%{location_detail}%")
                ).first()
            
            # Strategy 4: Match town exactly, normalized location with wildcards
            if not location and town_name and normalized_location_detail:
                location = self.db.query(Location).filter(
                    Location.source_id == source.id,
                    Location.town.ilike(town_name),
                    Location.location.ilike(f"%{normalized_location_detail}%")
                ).first()
            
            # Strategy 5: Match town with wildcards, location exactly
            if not location and town_name and location_detail:
                location = self.db.query(Location).filter(
                    Location.source_id == source.id,
                    Location.town.ilike(f"%{town_name}%"),
                    Location.location.ilike(location_detail)
                ).first()
            
            # Strategy 6: Match town only (exact) - if location_detail is "unknown"
            if not location and town_name and (not location_detail or location_detail.lower() == 'unknown'):
                location = self.db.query(Location).filter(
                    Location.source_id == source.id,
                    Location.town.ilike(town_name),
                    Location.location.ilike('unknown')
                ).first()
            
            # Strategy 7: Match town only (exact) - any location
            if not location and town_name:
                location = self.db.query(Location).filter(
                    Location.source_id == source.id,
                    Location.town.ilike(town_name)
                ).first()
            
            # Strategy 8: Match town only (partial)
            if not location and town_name:
                location = self.db.query(Location).filter(
                    Location.source_id == source.id,
                    Location.town.ilike(f"%{town_name}%")
                ).first()
            
            # Strategy 6: Auto-create location for SFT if town is known
            if not location and town_name and location_detail and self.config.short_name == 'SFT':
                # Check if we should auto-create (only for known SFT towns)
                known_sft_towns = {'Vaughan', 'Midtown', 'Downtown', 'Etobicoke', 
                                  'Oakville', 'Mississauga', 'Brampton', 'North York',
                                  'Scarborough', 'Markham', 'Richmond Hill'}
                
                if town_name in known_sft_towns:
                    self.logger.info(
                        f"Auto-creating location '{town_name}' / '{location_detail}' "
                        f"for source {source.name} (ID: {source.id})"
                    )
                    try:
                        new_location = Location(
                            source_id=source.id,
                            town=town_name,
                            location=location_detail,
                            is_default=False
                        )
                        self.db.add(new_location)
                        self.db.flush()
                        location = new_location
                        self.logger.info(f"Created new location: {town_name} / {location_detail}")
                    except Exception as e:
                        self.logger.warning(f"Failed to auto-create location '{town_name}': {e}")
                        self.db.rollback()
            
            # If still not found, log warning and use default location
            if not location:
                self.logger.warning(
                    f"Location not found for '{location_str}' (town: '{town_name}') "
                    f"for source {source.name} (ID: {source.id}). Using default location."
                )
                # Use default location
                location = self.db.query(Location).filter(
                    Location.source_id == source.id,
                    Location.is_default == True
                ).first()
            
            # If no default location exists, log error
            if not location:
                self.logger.error(
                    f"No default location found for source {source.name} (ID: {source.id}). "
                    f"Cannot create schedule for location '{location_str}'."
                )

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

        # Batch commits for better performance
        self._pending_commits += 1
        if self._pending_commits >= self.COMMIT_BATCH_SIZE:
            self.db.commit()
            self._pending_commits = 0
        else:
            # Flush to get IDs but don't commit yet
            self.db.flush()

        return is_new

    def _flush_pending_commits(self):
        """Commit any pending changes. Call at end of scrape."""
        if self.db and self._pending_commits > 0:
            self.db.commit()
            self._pending_commits = 0

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

            # Group schedule items by profile URL to collect all schedules per profile
            profiles_schedules = {}
            for item in schedule_items:
                if item.profile_url not in profiles_schedules:
                    profiles_schedules[item.profile_url] = []
                profiles_schedules[item.profile_url].append(item)

            unique_profiles = list(profiles_schedules.keys())
            self.logger.info(f"Processing {len(unique_profiles)} unique profiles")

            # Step 2: Process each listing
            for idx, profile_url in enumerate(unique_profiles, 1):
                try:
                    # Get first schedule item for basic info (name, tier, etc.)
                    schedule_items_for_profile = profiles_schedules[profile_url]
                    first_item = schedule_items_for_profile[0]
                    self.logger.info(f"[{idx}/{len(unique_profiles)}] Scraping {first_item.name} ({profile_url}) - {len(schedule_items_for_profile)} schedule(s)")

                    # Scrape profile
                    profile_data = await self.scrape_profile(profile_url)

                    # Normalize - pass all schedule items
                    listing = self.normalize_listing(first_item, profile_data, schedule_items_for_profile)

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
                        'profile_url': profile_url,
                        'error': str(e),
                    })
                    self.logger.error(f"Error scraping {profile_url}: {e}")
                    # Continue to next profile instead of failing entire scrape

            # Flush any remaining pending commits
            self._flush_pending_commits()

            self.result.completed_at = datetime.now(timezone.utc)
            duration = self.result.duration_seconds or 0
            self.logger.info(
                f"✅ Scrape complete in {duration:.1f}s: {self.result.new} new, "
                f"{self.result.updated} updated, {self.result.errors} errors"
            )

            return self.result

        except Exception as e:
            self.result.errors += 1
            self.result.error_details.append({'error': str(e)})
            self.result.completed_at = datetime.now(timezone.utc)
            self.logger.error(f"Scrape failed: {e}")
            # Try to commit whatever we have on error
            try:
                self._flush_pending_commits()
            except Exception:
                pass
            raise
