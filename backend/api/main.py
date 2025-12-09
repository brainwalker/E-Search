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

from api.database import get_db, init_db, Listing, Schedule, Source, Tag, Location, Tier, listing_tags
from api.scraper import SexyFriendsTorontoScraper
from api.config import settings
from scrapers.manager import ScraperManager, SCRAPER_REGISTRY
from api import db_viewer
from pydantic import BaseModel

# Setup logging directory
settings.log_dir.mkdir(exist_ok=True)

# Configure logging using settings
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format=settings.log_format,
    handlers=[
        logging.FileHandler(settings.log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


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
    logger.info("E-Search Backend Shutting Down")


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
    """Tier rates from the tiers table"""
    tier: str
    star: int
    incall_30min: Optional[str]
    incall_45min: Optional[str]
    incall_1hr: Optional[str]
    outcall_per_hr: Optional[str]

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
    """Get all scraping sources"""
    sources = db.query(Source).all()
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
    """Build a cache of tier rates for efficient lookup"""
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
    return cache


def enrich_listing_with_tier_rates(listing: Listing, tier_cache: dict) -> dict:
    """Convert listing to dict with tier rates from cache"""
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
    
    # Lookup tier rates if tier exists
    if listing.tier and listing.source_id:
        key = (listing.source_id, listing.tier.upper())
        if key in tier_cache:
            result["tier_rates"] = tier_cache[key]
    
    return result


@app.get("/api/listings", response_model=List[ListingResponse])
async def get_listings(
    source_ids: Optional[str] = Query(None, description="Comma-separated source IDs"),
    days_of_week: Optional[str] = Query(None, description="Comma-separated days (Monday,Tuesday,etc)"),
    hide_expired: bool = Query(False, description="Hide expired listings"),
    tier: Optional[str] = Query(None, description="Filter by tier (VIP, PLATINUM VIP, etc)"),
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
    query = db.query(Listing)

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

    # Filter by tags
    if tags:
        tag_list = [x.strip() for x in tags.split(",")]
        query = query.join(Listing.tags).filter(Tag.name.in_(tag_list))

    # Search by name
    if search:
        query = query.filter(Listing.name.ilike(f"%{search}%"))

    # Filter by days of week (through schedules)
    if days_of_week:
        day_list = [x.strip() for x in days_of_week.split(",")]
        query = query.join(Listing.schedules).filter(Schedule.day_of_week.in_(day_list))

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
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
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
    """Get statistics about the database"""
    total_listings = db.query(Listing).count()
    active_listings = db.query(Listing).filter(Listing.is_active == True).count()
    expired_listings = db.query(Listing).filter(Listing.is_expired == True).count()
    total_sources = db.query(Source).count()
    active_sources = db.query(Source).filter(Source.active == True).count()

    return {
        "total_listings": total_listings,
        "active_listings": active_listings,
        "expired_listings": expired_listings,
        "total_sources": total_sources,
        "active_sources": active_sources
    }


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
    
    # Get the scraper for this source
    scraper = SexyFriendsTorontoScraper(db)
    
    try:
        # Scrape with debug info
        debug_result = await scraper.scrape_profile_with_debug(listing.profile_url)
        
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
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if not listing.profile_url:
        raise HTTPException(status_code=400, detail="Listing has no profile URL")
    
    # Get the scraper for this source
    scraper = SexyFriendsTorontoScraper(db)
    
    try:
        # Scrape the profile
        profile_data = await scraper.scrape_profile(listing.profile_url)
        
        if not profile_data:
            raise HTTPException(status_code=500, detail="Failed to scrape profile")
        
        # Update the listing with new values
        update_fields = ['tier', 'age', 'nationality', 'ethnicity', 'height', 'weight', 
                        'measurements', 'bust', 'bust_type', 'eye_color', 'hair_color', 
                        'service_type', 'images']
        
        for field in update_fields:
            if field in profile_data:
                setattr(listing, field, profile_data[field])
        
        listing.updated_at = datetime.now()
        db.commit()
        db.refresh(listing)
        
        # Return the updated listing with tier rates
        tier_cache = get_tier_rates_cache(db)
        return enrich_listing_with_tier_rates(listing, tier_cache)
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error refreshing listing: {str(e)}")


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
    uvicorn.run(app, host="0.0.0.0", port=8000)
