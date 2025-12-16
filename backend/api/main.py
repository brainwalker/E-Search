from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
import json
import logging
import asyncio
import time

from api.database import get_db, init_db, Listing, Schedule, Source, Tag, Location, Tier, listing_tags, engine
from sqlalchemy.orm import joinedload
from api.scraper import SexyFriendsTorontoScraper
from api.config import settings
from scrapers.manager import ScraperManager, SCRAPER_REGISTRY
from api import db_viewer
from pydantic import BaseModel

# Setup logging directory
settings.log_dir.mkdir(exist_ok=True)

# Configure logging using settings
# Use basicConfig but prevent duplicate logs by configuring child loggers
import re

# Custom formatter to strip ANSI color codes from file logs
class ColorStripFormatter(logging.Formatter):
    """Formatter that strips ANSI color codes from log messages."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    def format(self, record):
        message = super().format(record)
        return self.ansi_escape.sub('', message)

# Setup logging with color support for console, stripped for file
file_handler = logging.FileHandler(settings.log_file, encoding='utf-8')
file_handler.setFormatter(ColorStripFormatter(settings.log_format))

console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(settings.log_format))

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    handlers=[file_handler, console_handler],
    force=True  # Override any existing configuration
)

# Prevent scraper loggers from propagating to root to avoid duplicate logs
# They will still use root logger's handlers via propagation, but we prevent double-handling
scraper_logger = logging.getLogger('scraper')
scraper_logger.propagate = False
# Add handlers directly to scraper logger so messages appear once
# Only add handlers if not already present (prevents duplicates on module reload)
if not scraper_logger.handlers:
    # File handler with color stripping
    scraper_file_handler = logging.FileHandler(settings.log_file, encoding='utf-8')
    scraper_file_handler.setFormatter(ColorStripFormatter(settings.log_format))
    scraper_logger.addHandler(scraper_file_handler)

    # Console handler with colors
    scraper_console_handler = logging.StreamHandler()
    scraper_console_handler.setFormatter(logging.Formatter(settings.log_format))
    scraper_logger.addHandler(scraper_console_handler)
scraper_logger.setLevel(getattr(logging, settings.log_level.upper()))

logger = logging.getLogger(__name__)


# Filter to suppress noisy polling endpoint access logs
class PollingEndpointFilter(logging.Filter):
    # Endpoints that poll frequently and clutter logs
    SUPPRESSED_ENDPOINTS = ['/db/logs', '/api/sources']
    
    def filter(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg) % (record.args if hasattr(record, 'args') and record.args else ())
        # Suppress requests to polling endpoints
        for endpoint in self.SUPPRESSED_ENDPOINTS:
            if endpoint in msg:
                return False
        return True

# Apply filter to uvicorn access logger at module load time
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(PollingEndpointFilter())


# Global shutdown event
shutdown_event = asyncio.Event()

# Global caches with TTL
_tier_cache: dict = {}
_tier_cache_timestamp: float = 0
_sources_cache: list = []
_sources_cache_timestamp: float = 0
CACHE_TTL_SECONDS = 300  # 5 minutes for all caches


async def cleanup_resources():
    """Clean up all resources on shutdown."""
    logger.info("Cleaning up resources...")
    
    # Close database connections with timeout
    try:
        logger.info("Closing database connections...")
        # Run dispose in executor since it's synchronous
        await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: engine.dispose(close=True)
            ),
            timeout=2.0
        )
        logger.info("Database connections closed")
    except asyncio.TimeoutError:
        logger.warning("Database cleanup timed out, forcing close")
        # Force synchronous dispose if timeout
        try:
            engine.dispose(close=True)
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Error closing database connections: {e}")
    
    # Give a small delay for any pending operations
    await asyncio.sleep(0.1)
    logger.info("Resource cleanup complete")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("=" * 60)
    logger.info("E-Search Backend Starting Up")
    logger.info("=" * 60)
    logger.info(f"Log file: {settings.log_file}")
    logger.info(f"Database: {settings.database_url}")
    logger.info(f"CORS origins: {settings.cors_origins}")
    init_db()
    logger.info("Database initialized successfully")
    logger.info("Backend ready to accept requests")
    
    yield  # Application runs here
    
    # Shutdown
    logger.info("=" * 60)
    logger.info("E-Search Backend Shutting Down")
    logger.info("=" * 60)
    
    # Clean up resources with timeout
    try:
        await asyncio.wait_for(cleanup_resources(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("Shutdown cleanup timed out, forcing exit")
    except Exception as e:
        logger.error(f"Error during shutdown cleanup: {e}")
    
    logger.info("Shutdown complete")


app = FastAPI(
    title="E-Search API", 
    version="1.0.0",
    lifespan=lifespan
)

# Include database viewer router
app.include_router(db_viewer.router)

# CORS middleware - allow all origins for development
# Note: allow_credentials must be False when allow_origins is ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Return empty response for favicon requests"""
    return Response(status_code=204)


# Pydantic models for API responses
class LocationResponse(BaseModel):
    id: int
    town: str
    location: str
    address: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True


class ScheduleResponse(BaseModel):
    id: int
    day_of_week: str
    start_time: Optional[str]
    end_time: Optional[str]
    location: Optional[LocationResponse]  # Changed to LocationResponse object
    is_expired: bool

    class Config:
        from_attributes = True


class TagResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class SourceResponse(BaseModel):
    id: int
    name: str
    url: str
    base_url: Optional[str]  # Base URL for profiles
    image_base_url: Optional[str]  # Base URL for images
    active: bool
    last_scraped: Optional[datetime]

    class Config:
        from_attributes = True


class TierRatesResponse(BaseModel):
    """Tier rates from the tiers table or listing-level pricing"""
    tier: Optional[str] = None  # Optional for listing-level pricing
    star: Optional[int] = None  # Optional for listing-level pricing
    incall_30min: Optional[str] = None
    incall_45min: Optional[str] = None
    incall_1hr: Optional[str] = None
    outcall_per_hr: Optional[str] = None
    min_booking: Optional[str] = None  # Minimum booking time (for variable pricing)
    source: Optional[str] = None  # "tier" or "listing" - indicates pricing source

    class Config:
        from_attributes = True


class ListingResponse(BaseModel):
    id: int
    source_id: int  # Include source_id
    name: str
    profile_url: Optional[str]  # Now stores only the slug/path
    tier: Optional[str]
    tier_rates: Optional[TierRatesResponse] = None  # Rates from tiers table
    age: Optional[int]
    nationality: Optional[str]
    ethnicity: Optional[str]
    height: Optional[str]
    weight: Optional[str]
    measurements: Optional[str]
    bust: Optional[str]
    bust_type: Optional[str]
    eye_color: Optional[str]
    hair_color: Optional[str]
    service_type: Optional[str]
    images: Optional[str]  # Now stores JSON array of filenames
    is_active: bool
    is_expired: bool
    created_at: datetime
    updated_at: datetime
    schedules: List[ScheduleResponse]
    tags: List[TagResponse]
    source: SourceResponse  # Include full source information

    class Config:
        from_attributes = True


# API Endpoints

@app.get("/")
async def root():
    return {"message": "E-Search API", "version": "1.0.0"}


@app.get("/api/sources", response_model=List[SourceResponse])
async def get_sources(db: Session = Depends(get_db)):
    """Get all scraping sources (cached for 5 minutes)"""
    global _sources_cache, _sources_cache_timestamp

    current_time = time.time()

    # Return cached version if still valid
    if _sources_cache and (current_time - _sources_cache_timestamp) < CACHE_TTL_SECONDS:
        return _sources_cache

    # Rebuild cache
    sources = db.query(Source).all()
    _sources_cache = sources
    _sources_cache_timestamp = current_time
    return sources


@app.post("/api/scrape/{source_name}")
async def scrape_source(
    source_name: str,
    use_new_scraper: bool = Query(True, description="Use new Crawlee-based scraper"),
    db: Session = Depends(get_db)
):
    """Trigger scraping for a specific source"""
    # Map source names to scraper registry keys
    source_map = {
        "sexyfriendstoronto": "sft",
        "sft": "sft",
        "dd": "discreet",
        "discreet": "discreet",
        "discreetdolls": "discreet",
        "mirage": "mirage",
        "select": "select",
        "selectcompany": "select",
    }

    source_key = source_map.get(source_name.lower())

    # Use new Crawlee-based scraper for all implemented sources
    if source_key and source_key in SCRAPER_REGISTRY:
        manager = ScraperManager(db)
        result = await manager.scrape_site(source_key)
        return result.to_dict()
    elif not use_new_scraper and source_name.lower() in ["sexyfriendstoronto", "sft"]:
        # Legacy fallback for SFT only
        scraper = SexyFriendsTorontoScraper(db)
        result = await scraper.scrape_and_save()
        return result
    else:
        raise HTTPException(status_code=404, detail=f"Scraper for {source_name} not found. Available: {list(SCRAPER_REGISTRY.keys())}")


@app.get("/api/scrapers")
async def list_scrapers():
    """List all available scrapers and their implementation status"""
    manager = ScraperManager()
    return {
        "scrapers": manager.list_scrapers(),
        "implemented": manager.get_implemented_scrapers()
    }


@app.post("/api/scrape-all")
async def scrape_all_sources(
    use_new_scraper: bool = Query(True, description="Use new Crawlee-based scrapers"),
    db: Session = Depends(get_db)
):
    """Trigger scraping for all active sources"""
    # Use new Crawlee-based scraper manager (default)
    manager = ScraperManager(db)
    results = await manager.scrape_all()
    return {
        "results": [r.to_dict() for r in results.values()],
        "summary": manager.get_results_summary()
    }


def get_tier_rates_cache(db: Session) -> dict:
    """
    Build a cache of tier rates for efficient lookup.
    Uses global cache with TTL to avoid rebuilding on every request.
    """
    global _tier_cache, _tier_cache_timestamp

    current_time = time.time()

    # Return cached version if still valid
    if _tier_cache and (current_time - _tier_cache_timestamp) < CACHE_TTL_SECONDS:
        return _tier_cache

    # Rebuild cache
    tiers = db.query(Tier).all()
    cache = {}
    for tier in tiers:
        # Key by source_id and tier name (uppercase for case-insensitive matching)
        key = (tier.source_id, tier.tier.upper())
        cache[key] = {
            "tier": tier.tier,
            "star": tier.star,
            "incall_30min": tier.incall_30min,
            "incall_45min": tier.incall_45min,
            "incall_1hr": tier.incall_1hr,
            "outcall_per_hr": tier.outcall_per_hr,
        }

    # Update global cache
    _tier_cache = cache
    _tier_cache_timestamp = current_time

    return cache


def invalidate_tier_cache():
    """Invalidate the tier cache (call after tier updates)."""
    global _tier_cache, _tier_cache_timestamp
    _tier_cache = {}
    _tier_cache_timestamp = 0


def enrich_listing_with_tier_rates(listing: Listing, tier_cache: dict) -> dict:
    """Convert listing to dict with tier rates from cache or listing-level pricing"""
    # Build the base response
    result = {
        "id": listing.id,
        "source_id": listing.source_id,
        "name": listing.name,
        "profile_url": listing.profile_url,
        "tier": listing.tier,
        "tier_rates": None,
        "age": listing.age,
        "nationality": listing.nationality,
        "ethnicity": listing.ethnicity,
        "height": listing.height,
        "weight": listing.weight,
        "measurements": listing.measurements,
        "bust": listing.bust,
        "bust_type": listing.bust_type,
        "eye_color": listing.eye_color,
        "hair_color": listing.hair_color,
        "service_type": listing.service_type,
        "images": listing.images,
        "is_active": listing.is_active,
        "is_expired": listing.is_expired,
        "created_at": listing.created_at,
        "updated_at": listing.updated_at,
        "schedules": listing.schedules,
        "tags": listing.tags,
        "source": listing.source,
    }

    # Check for listing-level pricing first (for sources with variable pricing)
    has_listing_prices = any([
        listing.incall_30min,
        listing.incall_45min,
        listing.incall_1hr,
        listing.outcall_1hr
    ])

    if has_listing_prices:
        # Use listing-level pricing
        # Still populate tier and star from listing/tier_cache for display purposes
        tier_name = listing.tier
        star_count = None
        if listing.tier and listing.source_id:
            key = (listing.source_id, listing.tier.upper())
            if key in tier_cache:
                star_count = tier_cache[key].get("star")

        result["tier_rates"] = {
            "tier": tier_name,  # Use tier from listing
            "star": star_count,  # Lookup star from tier table
            "incall_30min": listing.incall_30min,
            "incall_45min": listing.incall_45min,
            "incall_1hr": listing.incall_1hr,
            "outcall_per_hr": listing.outcall_1hr,
            "min_booking": listing.min_booking,
            "source": "listing"  # Indicate pricing came from listing
        }
    elif listing.tier and listing.source_id:
        # Fall back to tier-based pricing
        key = (listing.source_id, listing.tier.upper())
        if key in tier_cache:
            tier_rates = tier_cache[key].copy()
            tier_rates["source"] = "tier"  # Indicate pricing came from tier table
            result["tier_rates"] = tier_rates

    return result


@app.get("/api/listings", response_model=List[ListingResponse])
async def get_listings(
    source_ids: Optional[str] = Query(None, description="Comma-separated source IDs"),
    days_of_week: Optional[str] = Query(None, description="Comma-separated days (Monday,Tuesday,etc)"),
    hide_expired: bool = Query(False, description="Hide expired listings"),
    tier: Optional[str] = Query(None, description="Filter by tier (VIP, PLATINUM VIP, etc)"),
    stars: Optional[str] = Query(None, description="Comma-separated star ratings (1-5)"),
    cities: Optional[str] = Query(None, description="Comma-separated cities (Toronto, Mississauga, etc)"),
    towns: Optional[str] = Query(None, description="Comma-separated towns (Downtown, Midtown, etc)"),
    min_age: Optional[int] = Query(None, description="Minimum age"),
    max_age: Optional[int] = Query(None, description="Maximum age"),
    nationality: Optional[str] = Query(None, description="Filter by nationality"),
    hair_color: Optional[str] = Query(None, description="Filter by hair color"),
    tags: Optional[str] = Query(None, description="Comma-separated tags"),
    search: Optional[str] = Query(None, description="Search by name"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get listings with various filters"""
    # Use eager loading to prevent N+1 query problem
    query = db.query(Listing).options(
        joinedload(Listing.schedules).joinedload(Schedule.location),
        joinedload(Listing.tags),
        joinedload(Listing.source)
    )

    # Filter by source
    if source_ids:
        source_id_list = [int(x.strip()) for x in source_ids.split(",")]
        query = query.filter(Listing.source_id.in_(source_id_list))

    # Filter by expired status
    if hide_expired:
        query = query.filter(Listing.is_expired == False)

    # Filter by tier
    if tier:
        query = query.filter(Listing.tier == tier)

    # Filter by star rating (through tier table)
    if stars:
        star_list = [int(x.strip()) for x in stars.split(",")]
        # Join with Tier table to filter by star rating
        # Match on source_id and tier name (case-insensitive)
        from sqlalchemy import func
        query = query.join(
            Tier,
            and_(
                Tier.source_id == Listing.source_id,
                func.upper(Tier.tier) == func.upper(Listing.tier)
            )
        ).filter(Tier.star.in_(star_list))

    # Combined filter for cities/towns AND days (through schedules -> locations)
    # This ensures both filters work together on the same schedule records
    if cities or towns or days_of_week:
        # Build schedule subquery with all location and day filters
        schedule_filters = []

        # Add location filters
        if cities or towns:
            location_filters = []

            if cities:
                city_list = [x.strip() for x in cities.split(",")]
                location_filters.append(Location.city.in_(city_list))

            if towns:
                town_list = [x.strip() for x in towns.split(",")]
                location_filters.append(Location.town.in_(town_list))

            schedule_filters.append(or_(*location_filters))

        # Add day filter
        if days_of_week:
            day_list = [x.strip() for x in days_of_week.split(",")]
            schedule_filters.append(Schedule.day_of_week.in_(day_list))

        # Create subquery that combines all schedule-related filters
        subquery = db.query(Schedule.listing_id).join(Schedule.location)
        if schedule_filters:
            subquery = subquery.filter(and_(*schedule_filters))

        query = query.filter(Listing.id.in_(subquery.subquery()))

    # Filter by age
    if min_age:
        query = query.filter(Listing.age >= min_age)
    if max_age:
        query = query.filter(Listing.age <= max_age)

    # Filter by nationality
    if nationality:
        query = query.filter(Listing.nationality.ilike(f"%{nationality}%"))

    # Filter by hair color
    if hair_color:
        query = query.filter(Listing.hair_color.ilike(f"%{hair_color}%"))

    # Filter by tags (distinct to avoid duplicates when listing has multiple matching tags)
    if tags:
        tag_list = [x.strip() for x in tags.split(",")]
        query = query.join(Listing.tags).filter(Tag.name.in_(tag_list)).distinct()

    # Search by name
    if search:
        query = query.filter(Listing.name.ilike(f"%{search}%"))

    # Order by updated_at descending
    query = query.order_by(Listing.updated_at.desc())

    # Apply pagination
    listings = query.offset(skip).limit(limit).all()

    # Build tier cache and enrich listings with tier rates
    tier_cache = get_tier_rates_cache(db)
    return [enrich_listing_with_tier_rates(listing, tier_cache) for listing in listings]


@app.get("/api/listings/{listing_id}", response_model=ListingResponse)
async def get_listing(listing_id: int, db: Session = Depends(get_db)):
    """Get a single listing by ID"""
    # Use eager loading to prevent N+1 query problem
    listing = db.query(Listing).options(
        joinedload(Listing.schedules).joinedload(Schedule.location),
        joinedload(Listing.tags),
        joinedload(Listing.source)
    ).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Build tier cache and enrich with tier rates
    tier_cache = get_tier_rates_cache(db)
    return enrich_listing_with_tier_rates(listing, tier_cache)


@app.get("/api/tags", response_model=List[TagResponse])
async def get_tags(db: Session = Depends(get_db)):
    """Get all available tags"""
    tags = db.query(Tag).all()
    return tags


# Pydantic model for Tier response
class TierResponse(BaseModel):
    id: int
    source_id: int
    tier: str
    star: int
    incall_30min: Optional[str]
    incall_45min: Optional[str]
    incall_1hr: Optional[str]
    outcall_per_hr: Optional[str]

    class Config:
        from_attributes = True


@app.get("/api/tiers", response_model=List[TierResponse])
async def get_tiers(
    source_id: Optional[int] = Query(None, description="Filter by source ID"),
    db: Session = Depends(get_db)
):
    """Get all available tiers, optionally filtered by source"""
    query = db.query(Tier)
    if source_id:
        query = query.filter(Tier.source_id == source_id)
    tiers = query.order_by(Tier.star).all()
    return tiers


@app.get("/api/stats")
async def get_stats(db: Session = Depends(get_db)):
    """Get statistics about the database - optimized single query"""
    from sqlalchemy import func, case

    # Single query for all listing stats
    listing_stats = db.query(
        func.count(Listing.id).label('total'),
        func.sum(case((Listing.is_active == True, 1), else_=0)).label('active'),
        func.sum(case((Listing.is_expired == True, 1), else_=0)).label('expired')
    ).first()

    # Single query for all source stats
    source_stats = db.query(
        func.count(Source.id).label('total'),
        func.sum(case((Source.active == True, 1), else_=0)).label('active')
    ).first()

    return {
        "total_listings": listing_stats.total or 0,
        "active_listings": listing_stats.active or 0,
        "expired_listings": listing_stats.expired or 0,
        "total_sources": source_stats.total or 0,
        "active_sources": source_stats.active or 0
    }


@app.get("/api/cities")
async def get_cities(db: Session = Depends(get_db)):
    """Get all unique cities from locations"""
    cities = db.query(Location.city).distinct().order_by(Location.city).all()
    return [c[0] for c in cities if c[0]]


@app.get("/api/towns")
async def get_towns(city: Optional[str] = Query(None, description="Filter towns by city"), db: Session = Depends(get_db)):
    """Get all unique towns from locations, optionally filtered by city"""
    query = db.query(Location.town).distinct()
    if city:
        query = query.filter(Location.city == city)
    towns = query.order_by(Location.town).all()
    return [t[0] for t in towns if t[0]]


@app.delete("/api/listings/{listing_id}")
async def delete_listing(listing_id: int, db: Session = Depends(get_db)):
    """Delete a listing"""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    db.delete(listing)
    db.commit()
    return {"message": "Listing deleted successfully"}


@app.put("/api/listings/{listing_id}/expire")
async def expire_listing(listing_id: int, db: Session = Depends(get_db)):
    """Mark a listing as expired"""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    listing.is_expired = True
    db.commit()
    return {"message": "Listing marked as expired"}


@app.get("/api/listings/{listing_id}/debug-extraction")
async def debug_listing_extraction(listing_id: int, db: Session = Depends(get_db)):
    """
    Rescrape a listing's profile and return detailed extraction debug info.
    Shows what patterns matched, what text was extracted, and final values.
    """
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if not listing.profile_url:
        raise HTTPException(status_code=400, detail="Listing has no profile URL")
    
    # Get the source for this listing
    source = db.query(Source).filter(Source.id == listing.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found for listing")
    
    # Map source name to scraper registry key (same logic as refresh endpoint)
    source_name_to_key = {
        'SFT': 'sft',
        'DD': 'discreet',
        'Mirage': 'mirage',
        'SELECT': 'select',
        'SexyFriendsToronto': 'sft',  # Legacy support
        'DiscreetDolls': 'discreet',  # Legacy support
        'MirageEntertainment': 'mirage',  # Legacy support
        'SelectCompanyEscorts': 'select',  # Legacy support
    }
    
    # Try exact match first, then case-insensitive
    scraper_key = source_name_to_key.get(source.name)
    if not scraper_key:
        # Try case-insensitive lookup
        source_name_lower = source.name.lower() if source.name else ''
        for key, value in source_name_to_key.items():
            if key.lower() == source_name_lower:
                scraper_key = value
                break
    
    if not scraper_key:
        available = list(source_name_to_key.keys())
        raise HTTPException(status_code=400, detail=f"No scraper available for source: '{source.name}'. Available: {available}")
    
    if scraper_key not in SCRAPER_REGISTRY:
        raise HTTPException(
            status_code=500,
            detail=f"Scraper '{scraper_key}' not found in registry. Available: {list(SCRAPER_REGISTRY.keys())}"
        )
    
    # Get the scraper for this source
    manager = ScraperManager(db)
    scraper = manager.get_scraper(scraper_key)
    if not scraper:
        raise HTTPException(status_code=500, detail=f"Failed to initialize scraper for {source.name}")
    
    # Build full profile URL from source base_url + listing profile_url slug
    full_profile_url = f"{source.base_url}{listing.profile_url}" if source.base_url else listing.profile_url
    
    try:
        # Check if scraper has scrape_profile_with_debug method (legacy SFT scraper)
        if hasattr(scraper, 'scrape_profile_with_debug'):
            # Use debug method if available (legacy scraper)
            debug_result = await scraper.scrape_profile_with_debug(listing.profile_url)
            # Override profile_url with full URL
            debug_result['profile_url'] = full_profile_url
        else:
            # For new scrapers, use scrape_profile and format as debug result
            profile_data = await scraper.scrape_profile(listing.profile_url)
            # Format as debug result structure
            # Build extractions dict with raw_text field populated from profile_data
            fields = ['tier', 'age', 'nationality', 'ethnicity', 'height', 'weight',
                      'measurements', 'bust', 'eye_color', 'hair_color', 'service_type']
            extractions = {}
            text_snippets = {}
            for field in fields:
                value = profile_data.get(field)
                matched = value is not None
                extractions[field] = {
                    'matched': matched,
                    'final_value': value,
                    'raw_text': str(value) if value is not None else None,  # Show what was extracted
                }
                if matched and value:
                    text_snippets[field] = str(value)

            # Add images and tags extractions
            extractions['images'] = {
                'matched': bool(profile_data.get('images')),
                'final_value': profile_data.get('images', []),
                'count': len(profile_data.get('images', [])),
            }
            extractions['tags'] = {
                'matched': bool(profile_data.get('tags')),
                'final_value': profile_data.get('tags', []),
            }

            # Add schedules extraction
            schedules = profile_data.get('schedules', [])
            extractions['schedules'] = {
                'matched': bool(schedules),
                'final_value': schedules,
                'count': len(schedules),
            }

            debug_result = {
                'profile_url': full_profile_url,
                'profile_data': profile_data,
                'extractions': extractions,
                'text_snippets': text_snippets,
            }
        
        # Add current database values for comparison
        debug_result['current_db_values'] = {
            'id': listing.id,
            'name': listing.name,
            'tier': listing.tier,
            'age': listing.age,
            'nationality': listing.nationality,
            'ethnicity': listing.ethnicity,
            'height': listing.height,
            'weight': listing.weight,
            'measurements': listing.measurements,
            'bust': listing.bust,
            'bust_type': listing.bust_type,
            'eye_color': listing.eye_color,
            'hair_color': listing.hair_color,
            'service_type': listing.service_type,
        }
        
        # Add tier rates info
        tier_cache = get_tier_rates_cache(db)
        if listing.tier and listing.source_id:
            key = (listing.source_id, listing.tier.upper())
            debug_result['tier_rates'] = tier_cache.get(key, None)
        
        return debug_result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scraping profile: {str(e)}")


@app.post("/api/listings/{listing_id}/refresh")
async def refresh_listing(listing_id: int, db: Session = Depends(get_db)):
    """
    Rescrape a listing's profile and update the database with new values.
    """
    logging.info(f"{'='*60}")
    logging.info(f"REFRESH ENDPOINT CALLED: listing_id={listing_id}")
    logging.info(f"{'='*60}")
    
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if not listing.profile_url:
        raise HTTPException(status_code=400, detail="Listing has no profile URL")
    
    # Get the source for this listing
    source = db.query(Source).filter(Source.id == listing.source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found for listing")
    
    logging.info(f"Source found: name='{source.name}', id={source.id}")
    
    # Map source name to scraper registry key
    # Source names in DB use short_name from config (e.g., 'SFT', 'DD')
    # Scraper registry uses lowercase keys (e.g., 'sft', 'discreet')
    source_name_to_key = {
        'SFT': 'sft',
        'DD': 'discreet',
        'Mirage': 'mirage',
        'SELECT': 'select',
        'SexyFriendsToronto': 'sft',  # Legacy support
        'DiscreetDolls': 'discreet',  # Legacy support
        'MirageEntertainment': 'mirage',  # Legacy support
        'SelectCompanyEscorts': 'select',  # Legacy support
    }
    
    # Log for debugging
    logging.info(f"Refreshing listing {listing_id}: source.name='{source.name}', profile_url='{listing.profile_url}'")
    
    # Try exact match first, then case-insensitive
    scraper_key = source_name_to_key.get(source.name)
    if not scraper_key:
        # Try case-insensitive lookup
        source_name_lower = source.name.lower() if source.name else ''
        for key, value in source_name_to_key.items():
            if key.lower() == source_name_lower:
                scraper_key = value
                logging.info(f"Matched source '{source.name}' to scraper key '{scraper_key}' (case-insensitive)")
                break
    
    if not scraper_key:
        available = list(source_name_to_key.keys())
        error_msg = f"No scraper available for source: '{source.name}'. Available: {available}"
        logging.error(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    
    if scraper_key not in SCRAPER_REGISTRY:
        raise HTTPException(
            status_code=500,
            detail=f"Scraper '{scraper_key}' not found in registry. Available: {list(SCRAPER_REGISTRY.keys())}"
        )
    
    # Get the scraper for this source
    manager = ScraperManager(db)
    scraper = manager.get_scraper(scraper_key)
    if not scraper:
        raise HTTPException(status_code=500, detail=f"Failed to initialize scraper for {source.name}")
    
    # Log which scraper class is being used
    scraper_class_name = scraper.__class__.__name__
    
    try:
        logging.info(f"🔄 Refreshing listing {listing_id} using {scraper_class_name} for profile_url='{listing.profile_url}'")
        
        # Scrape the profile
        profile_data = await scraper.scrape_profile(listing.profile_url)
        
        if not profile_data:
            raise HTTPException(status_code=500, detail="Failed to scrape profile")
        
        logging.info(f"✅ Successfully scraped profile data: {list(profile_data.keys())}")
        
        # Update the listing with new values
        update_fields = ['tier', 'age', 'nationality', 'ethnicity', 'height', 'weight', 
                        'measurements', 'bust', 'bust_type', 'eye_color', 'hair_color', 
                        'service_type', 'images']
        
        updated_count = 0
        for field in update_fields:
            if field in profile_data:
                old_value = getattr(listing, field, None)
                new_value = profile_data[field]
                
                # Convert images list to JSON string if needed
                if field == 'images' and isinstance(new_value, list):
                    new_value = json.dumps(new_value) if new_value else None
                    # Compare with existing JSON string
                    try:
                        old_value_parsed = json.loads(old_value) if old_value else []
                    except (json.JSONDecodeError, TypeError):
                        old_value_parsed = []
                    if old_value_parsed == profile_data[field]:
                        continue  # Skip if same
                
                if old_value != new_value:
                    setattr(listing, field, new_value)
                    updated_count += 1
                    logging.debug(f"  Updated {field}: {old_value} -> {new_value}")
        
        # Update schedules if available in profile_data
        # Note: For refresh, we UPDATE existing schedules by day_of_week only (not location)
        # This prevents creating duplicates. We don't create NEW schedules on refresh.
        schedules_updated = 0
        if 'schedules' in profile_data and profile_data['schedules']:
            logging.info(f"Found {len(profile_data['schedules'])} schedule(s) in profile_data")

            for schedule_data in profile_data['schedules']:
                day_of_week = schedule_data.get('day_of_week')
                if not day_of_week:
                    continue

                # Calculate date from day of week
                today = datetime.now()
                day_map = {
                    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
                    'Friday': 4, 'Saturday': 5, 'Sunday': 6
                }
                target_day = day_map.get(day_of_week)
                schedule_date = None
                if target_day is not None:
                    current_day = today.weekday()
                    days_ahead = target_day - current_day
                    if days_ahead <= 0:
                        days_ahead += 7
                    schedule_date = (today + timedelta(days=days_ahead)).replace(hour=0, minute=0, second=0, microsecond=0)

                # Find existing schedule by day only (not location) to avoid duplicates
                existing_schedule = db.query(Schedule).filter_by(
                    listing_id=listing.id,
                    day_of_week=day_of_week
                ).first()

                if existing_schedule:
                    # Update existing schedule's times and date
                    existing_schedule.date = schedule_date
                    existing_schedule.start_time = schedule_data.get('start_time')
                    existing_schedule.end_time = schedule_data.get('end_time')
                    existing_schedule.is_expired = False
                    schedules_updated += 1
                # Don't create new schedules on refresh - only update existing ones
                # New schedules should only be created during full scrape

            if schedules_updated > 0:
                logging.info(f"✅ Updated {schedules_updated} schedule(s) for listing {listing_id}")

        listing.updated_at = datetime.now()
        db.commit()

        logging.info(f"✅ Updated {updated_count} fields for listing {listing_id}")

        # Re-fetch listing with eager loading for relationships
        listing = db.query(Listing).options(
            joinedload(Listing.schedules).joinedload(Schedule.location),
            joinedload(Listing.tags),
            joinedload(Listing.source)
        ).filter(Listing.id == listing_id).first()

        # Return the updated listing with tier rates
        tier_cache = get_tier_rates_cache(db)
        result = enrich_listing_with_tier_rates(listing, tier_cache)
        
        # Add debug info to response (for development/debugging)
        # This helps verify which scraper is being used
        result['_debug_info'] = {
            'scraper_used': scraper_class_name,
            'source_name': source.name,
            'scraper_key': scraper_key,
            'fields_updated': updated_count
        }
        
        return result
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error refreshing listing: {str(e)}")
    finally:
        # Clean up scraper resources if needed (e.g., DD scraper's browser)
        if hasattr(scraper, 'crawler') and hasattr(scraper.crawler, 'close'):
            try:
                await scraper.crawler.close()
            except Exception as cleanup_error:
                # Log but don't fail the request if cleanup fails
                logging.warning(f"Error cleaning up scraper resources: {cleanup_error}")


@app.delete("/api/sources/{source_id}/data")
async def delete_source_data(source_id: int, db: Session = Depends(get_db)):
    """
    Delete all data for a specific source.
    Deletes: listings, schedules, tags, listing_tags
    Preserves: sources, locations, tiers (configuration data)
    """
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Get listing IDs for this source
    listing_ids = [l.id for l in db.query(Listing.id).filter(Listing.source_id == source_id).all()]
    
    deleted_schedules = 0
    deleted_listing_tags = 0
    deleted_listings = 0
    deleted_tags = 0
    
    if listing_ids:
        # Delete schedules for these listings
        deleted_schedules = db.query(Schedule).filter(Schedule.listing_id.in_(listing_ids)).delete(synchronize_session=False)
        
        # Delete listing_tags associations
        deleted_listing_tags = db.execute(
            listing_tags.delete().where(listing_tags.c.listing_id.in_(listing_ids))
        ).rowcount
        
        # Delete listings
        deleted_listings = db.query(Listing).filter(Listing.source_id == source_id).delete(synchronize_session=False)
    
    # Delete orphaned tags (tags not associated with any listing)
    orphaned_tags = db.query(Tag).filter(
        ~Tag.id.in_(
            db.query(listing_tags.c.tag_id).distinct()
        )
    ).all()
    deleted_tags = len(orphaned_tags)
    for tag in orphaned_tags:
        db.delete(tag)
    
    db.commit()

    return {
        "message": f"Deleted all data for {source.name}",
        "source_name": source.name,
        "deleted_listings": deleted_listings,
        "deleted_schedules": deleted_schedules,
        "deleted_tags": deleted_tags,
        "deleted_listing_tags": deleted_listing_tags
    }


if __name__ == "__main__":
    import uvicorn
    
    # Configure uvicorn for faster shutdown
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        access_log=True,
        log_config=None,  # Use default but our filter will handle it
        timeout_keep_alive=5,  # Reduce keep-alive timeout
        timeout_graceful_shutdown=5.0,  # Graceful shutdown timeout (5 seconds)
    )
