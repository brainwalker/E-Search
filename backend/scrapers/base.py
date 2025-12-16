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

# ANSI color codes for terminal output
class Colors:
    """ANSI color codes for colorized logging."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'

    # Colors
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    GRAY = '\033[90m'

    @staticmethod
    def green(text):
        return f"{Colors.GREEN}{text}{Colors.RESET}"

    @staticmethod
    def yellow(text):
        return f"{Colors.YELLOW}{text}{Colors.RESET}"

    @staticmethod
    def red(text):
        return f"{Colors.RED}{text}{Colors.RESET}"

    @staticmethod
    def blue(text):
        return f"{Colors.BLUE}{text}{Colors.RESET}"

    @staticmethod
    def cyan(text):
        return f"{Colors.CYAN}{text}{Colors.RESET}"

    @staticmethod
    def gray(text):
        return f"{Colors.GRAY}{text}{Colors.RESET}"

    @staticmethod
    def bold(text):
        return f"{Colors.BOLD}{text}{Colors.RESET}"


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

    # Per-listing pricing (for sources with variable pricing like Mirage PLATINUM VIP)
    incall_30min: Optional[str] = None
    incall_45min: Optional[str] = None
    incall_1hr: Optional[str] = None
    outcall_1hr: Optional[str] = None
    min_booking: Optional[str] = None

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
        # Location cache: pre-loaded locations for this source (optimization)
        self._location_cache: dict = {}  # key: (town_lower, location_lower) -> Location object
        self._location_cache_loaded = False
    
    def _parse_sft_location_fallback(self, location_str: str) -> tuple:
        """
        Fallback SFT location parser if the main one isn't available.
        Tries to extract town name from common patterns.
        """
        from scrapers.config import KNOWN_TOWNS

        location_str = location_str.strip()
        location_lower = location_str.lower()

        # Sort by length (longest first) to match "North York" before "York"
        for town in sorted(KNOWN_TOWNS, key=len, reverse=True):
            if location_lower.startswith(town.lower()):
                # Extract location part
                town_end = len(town)
                while town_end < len(location_str) and location_str[town_end] == ' ':
                    town_end += 1
                location_part = location_str[town_end:].strip()
                return (town, location_part if location_part else "unknown")

        # No match found
        return (location_str, "unknown")

    def _load_location_cache(self, source_id: int):
        """
        Pre-load all locations for this source into memory cache.
        This avoids multiple DB queries per schedule during scraping.
        """
        if self._location_cache_loaded:
            return

        from api.database import Location
        locations = self.db.query(Location).filter(Location.source_id == source_id).all()

        for loc in locations:
            # Cache by multiple keys for flexible matching
            town_lower = (loc.town or '').lower().strip()
            location_lower = (loc.location or '').lower().strip()

            # Primary key: (town, location)
            self._location_cache[(town_lower, location_lower)] = loc

            # Also cache by town only for fallback matching
            if town_lower and town_lower not in self._location_cache:
                self._location_cache[('_town_only', town_lower)] = loc

            # Mark default location
            if loc.is_default:
                self._location_cache[('_default', '')] = loc

        self._location_cache_loaded = True
        self.logger.debug(f"Loaded {len(locations)} locations into cache")

    def _find_location_in_cache(self, town_name: str, location_detail: str, normalized_location: str = None) -> 'Location':
        """
        Find location in cache using multiple matching strategies.
        Returns None if not found.
        """
        town_lower = (town_name or '').lower().strip()
        location_lower = (location_detail or '').lower().strip()
        normalized_lower = (normalized_location or '').lower().strip()

        # Strategy 1: Exact match (town, location)
        key = (town_lower, location_lower)
        if key in self._location_cache:
            return self._location_cache[key]

        # Strategy 2: Exact match with normalized location
        if normalized_lower and normalized_lower != location_lower:
            key = (town_lower, normalized_lower)
            if key in self._location_cache:
                return self._location_cache[key]

        # Strategy 3: Town + 'unknown' location
        if town_lower:
            key = (town_lower, 'unknown')
            if key in self._location_cache:
                return self._location_cache[key]

        # Strategy 4: Town only match
        if town_lower:
            key = ('_town_only', town_lower)
            if key in self._location_cache:
                return self._location_cache[key]

        # Strategy 5: Partial town match (check if cache has any location starting with town)
        if town_lower:
            for cache_key, loc in self._location_cache.items():
                if isinstance(cache_key, tuple) and len(cache_key) == 2:
                    cached_town = cache_key[0]
                    if cached_town and (town_lower in cached_town or cached_town in town_lower):
                        return loc

        return None

    def _get_default_location(self) -> 'Location':
        """Get the default location from cache."""
        return self._location_cache.get(('_default', ''))

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

    def log_profile_extraction(self, profile_slug: str, profile_data: Dict, old_listing: Optional[Any] = None,
                                schedule_tier: Optional[str] = None, schedule_items: Optional[List] = None):
        """
        Log extracted profile fields with color coding.

        Args:
            profile_slug: Profile identifier
            profile_data: Newly extracted profile data
            old_listing: Existing listing from database (if updating)
            schedule_tier: Tier from schedule page (may not be in profile_data)
            schedule_items: Schedule items from schedule page (may not be in profile_data)
        """
        # Create a combined data dict that includes schedule page data
        combined_data = dict(profile_data)

        # Add tier from schedule if not in profile data
        if schedule_tier and not combined_data.get('tier'):
            combined_data['tier'] = schedule_tier

        # Add schedules from schedule items if not in profile data
        if schedule_items and not combined_data.get('schedules'):
            combined_data['schedules'] = [{'day_of_week': s.day_of_week} for s in schedule_items]

        # All possible fields we track
        all_fields = ['age', 'nationality', 'ethnicity', 'height', 'weight', 'bust', 'bust_type',
                      'measurements', 'hair_color', 'eye_color', 'service_type', 'tier', 'images',
                      'tags', 'schedules']

        extracted = []
        missing = []
        updated = []
        unchanged = []

        for field in all_fields:
            if field in combined_data and combined_data[field]:
                # Field was extracted
                if old_listing:
                    old_value = getattr(old_listing, field, None)
                    new_value = combined_data[field]

                    # Convert for comparison
                    if field == 'images' and isinstance(old_value, str):
                        try:
                            old_value = json.loads(old_value) if old_value else None
                        except:
                            old_value = None

                    if old_value != new_value and old_value is not None:
                        updated.append(Colors.green(field))  # Changed
                    elif old_value is None:
                        extracted.append(Colors.green(field))  # New field
                    else:
                        unchanged.append(field)  # Same value
                else:
                    extracted.append(Colors.green(field))  # New listing
            else:
                missing.append(Colors.gray(field))

        # Build output - captured fields on one line, missing on another
        captured = extracted + updated + unchanged
        if captured:
            # Strip color codes for plain text readability
            captured_plain = [f.replace(Colors.GREEN, '').replace(Colors.RESET, '') for f in captured]
            self.logger.info(f"   ➤ {profile_slug}: {', '.join(captured_plain)}")
        else:
            self.logger.info(f"   ➤ {profile_slug}: no data captured")

        if missing:
            # Strip color codes for plain text readability
            missing_plain = [f.replace(Colors.GRAY, '').replace(Colors.RESET, '') for f in missing]
            self.logger.info(f"   ✘ missing: {', '.join(missing_plain)}")

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

        # Prefer name from profile_data if available (might have proper spacing)
        # Fall back to schedule_item.name
        name = profile_data.get('name') or schedule_item.name
        
        return ScrapedListing(
            name=name,
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

    async def save_listing(self, listing: ScrapedListing) -> tuple[bool, Optional[Any]]:
        """
        Save or update a listing in the database.

        Override this method for custom database logic.
        Returns (is_new, old_listing) tuple.
        """
        if not self.db:
            self.logger.warning("No database session - skipping save")
            return (False, None)

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

        # Per-listing pricing (for sources with variable pricing)
        db_listing.incall_30min = listing.incall_30min
        db_listing.incall_45min = listing.incall_45min
        db_listing.incall_1hr = listing.incall_1hr
        db_listing.outcall_1hr = listing.outcall_1hr
        db_listing.min_booking = listing.min_booking

        self.db.flush()

        # Handle schedules
        # IMPORTANT: Delete all existing schedules first to avoid duplicates
        # Schedules change frequently (daily/weekly) and we want fresh data
        if not is_new:
            deleted_count = self.db.query(Schedule).filter_by(
                listing_id=db_listing.id
            ).delete(synchronize_session=False)
            if deleted_count > 0:
                self.logger.debug(f"Deleted {deleted_count} old schedule(s) for {listing.name}")
        
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

            # Use cached location lookup (much faster than 8 sequential DB queries)
            # Cache is loaded once per scrape run
            self._load_location_cache(source.id)
            location = self._find_location_in_cache(town_name, location_detail, normalized_location_detail)

            # Auto-create location for SFT if town is known and not in cache
            if not location and town_name and location_detail and self.config.short_name == 'SFT':
                from scrapers.config import KNOWN_TOWNS

                if town_name in KNOWN_TOWNS:
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
                        # Add to cache for future lookups in this run
                        town_lower = town_name.lower()
                        loc_lower = location_detail.lower()
                        self._location_cache[(town_lower, loc_lower)] = new_location
                        self.logger.info(f"Created new location: {town_name} / {location_detail}")
                    except Exception as e:
                        self.logger.warning(f"Failed to auto-create location '{town_name}': {e}")
                        self.db.rollback()

            # If still not found, use default location from cache
            if not location:
                location = self._get_default_location()
                if location:
                    self.logger.debug(
                        f"Using default location for '{location_str}' (town: '{town_name}')"
                    )
                else:
                    self.logger.warning(
                        f"Location not found for '{location_str}' (town: '{town_name}') "
                        f"for source {source.name} (ID: {source.id}). No default location available."
                    )

            location_id = location.id if location else None
            day_of_week = schedule_data.get('day_of_week')
            schedule_date = self._get_date_from_day_of_week(day_of_week) if day_of_week else None

            # Create new schedule (old schedules were deleted above)
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

        return (is_new, existing)

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

                    # New format: ❯❯❯ separator line
                    self.logger.info(f"\n{Colors.cyan('❯❯❯')}")
                    self.logger.info(f"{Colors.bold(f'[{idx}/{len(unique_profiles)}]')} Processing {Colors.bold(first_item.name)} {Colors.gray(f'({profile_url})')} - {len(schedule_items_for_profile)} schedule(s)")

                    # Scrape profile
                    profile_data = await self.scrape_profile(profile_url)

                    # Log extracted fields with schedule data included
                    # Pass tier and schedules from schedule page so they're counted as captured
                    self.log_profile_extraction(
                        profile_url,
                        profile_data,
                        schedule_tier=first_item.tier,
                        schedule_items=schedule_items_for_profile
                    )

                    # Normalize - pass all schedule items
                    listing = self.normalize_listing(first_item, profile_data, schedule_items_for_profile)

                    # Save
                    is_new, old_listing = await self.save_listing(listing)

                    if is_new:
                        self.result.new += 1
                        self.logger.info(f"   {Colors.green('[NEW]')} {first_item.name}: created new listing")
                    else:
                        self.result.updated += 1
                        self.logger.info(f"   {Colors.blue('[UPD]')} {first_item.name}: updated existing listing")

                    # Progress update every 10 profiles
                    if idx % 10 == 0:
                        self.logger.info(f"\n{Colors.bold('Progress')}: {idx}/{len(unique_profiles)} profiles ({Colors.green(f'{self.result.new} new')}, {Colors.blue(f'{self.result.updated} updated')}, {Colors.red(f'{self.result.errors} errors')})")

                except Exception as e:
                    self.result.errors += 1
                    self.result.error_details.append({
                        'profile_url': profile_url,
                        'error': str(e),
                    })
                    profile_name = schedule_items_for_profile[0].name if profile_url in profiles_schedules else profile_url
                    self.logger.error(f"   {Colors.red('[ERR]')} {profile_name}: {str(e)}")
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
