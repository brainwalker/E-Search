from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import List, Optional
from datetime import datetime, timedelta
import json

from api.database import get_db, init_db, Listing, Schedule, Source, Tag, Location
from api.scraper import SexyFriendsTorontoScraper
from api import db_viewer
from pydantic import BaseModel

app = FastAPI(title="E-Search API", version="1.0.0")

# Include database viewer router
app.include_router(db_viewer.router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()


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


class ListingResponse(BaseModel):
    id: int
    source_id: int  # Include source_id
    name: str
    profile_url: Optional[str]  # Now stores only the slug/path
    tier: Optional[str]
    age: Optional[int]
    nationality: Optional[str]
    height: Optional[str]
    weight: Optional[str]
    bust: Optional[str]
    bust_type: Optional[str]
    eye_color: Optional[str]
    hair_color: Optional[str]
    service_type: Optional[str]
    incall_30min: Optional[int]
    incall_45min: Optional[int]
    incall_1hr: Optional[int]
    outcall_1hr: Optional[int]
    rate_notes: Optional[str]
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
async def scrape_source(source_name: str, db: Session = Depends(get_db)):
    """Trigger scraping for a specific source"""
    if source_name.lower() == "sexyfriendstoronto":
        scraper = SexyFriendsTorontoScraper(db)
        result = await scraper.scrape_and_save()
        return result
    else:
        raise HTTPException(status_code=404, detail=f"Scraper for {source_name} not found")


@app.post("/api/scrape-all")
async def scrape_all_sources(db: Session = Depends(get_db)):
    """Trigger scraping for all active sources"""
    results = []

    # SexyFriendsToronto
    scraper = SexyFriendsTorontoScraper(db)
    result = await scraper.scrape_and_save()
    results.append(result)

    return {"results": results}


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

    # Get total count
    total = query.count()

    # Apply pagination
    listings = query.offset(skip).limit(limit).all()

    return listings


@app.get("/api/listings/{listing_id}", response_model=ListingResponse)
async def get_listing(listing_id: int, db: Session = Depends(get_db)):
    """Get a single listing by ID"""
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


@app.get("/api/tags", response_model=List[TagResponse])
async def get_tags(db: Session = Depends(get_db)):
    """Get all available tags"""
    tags = db.query(Tag).all()
    return tags


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


@app.delete("/api/sources/{source_id}/data")
async def delete_source_data(source_id: int, db: Session = Depends(get_db)):
    """
    Delete all listings and schedules for a specific source.
    Preserves: Source, Locations, and Tags (they can be reused).
    """
    source = db.query(Source).filter(Source.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    # Delete all listings for this source (cascades to schedules)
    # Note: This does NOT delete the source itself, locations, or tags
    deleted_count = db.query(Listing).filter(Listing.source_id == source_id).delete()
    db.commit()

    return {
        "message": f"Deleted {deleted_count} listings from {source.name}",
        "source_name": source.name,
        "deleted_listings": deleted_count
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
