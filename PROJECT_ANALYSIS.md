# E-Search Project Analysis

## Executive Summary

**E-Search** is a full-stack web application that aggregates escort listings from multiple sources. The project uses FastAPI for the backend, SQLite for data storage, and vanilla HTML/CSS/JavaScript for the frontend. Currently, the database contains **2 configured sources** but **0 listings** (database appears to have been cleared or not yet populated).

---

## Project Architecture

### Technology Stack

**Backend:**
- FastAPI 0.109.0 - Modern async Python web framework
- SQLAlchemy 2.0.25 - ORM for database operations
- SQLite - Embedded database (easily upgradeable to PostgreSQL)
- BeautifulSoup4 4.12.3 - HTML parsing for web scraping
- httpx 0.26.0 - Async HTTP client
- Uvicorn 0.27.0 - ASGI server

**Frontend:**
- Vanilla HTML/CSS/JavaScript (no frameworks)
- Modern CSS Grid & Flexbox for responsive layouts
- Fetch API for backend communication

---

## Database Structure

### Tables Overview

The database contains **8 tables**:

1. **`sources`** - Scraping source configurations
   - Fields: `id`, `name`, `url`, `active`, `last_scraped`, `created_at`, `image_base_url`, `profile_url_base`
   - Currently contains: **2 sources** (SexyFriendsToronto, DiscreetDolls)

2. **`listings`** - Main listing data
   - Fields: `id`, `source_id`, `name`, `profile_url`, `tier`, `age`, `nationality`, `height`, `weight`, `bust`, `bust_type`, `eye_color`, `hair_color`, `service_type`, `images`, `is_active`, `is_expired`, `created_at`, `updated_at`
   - Currently contains: **0 listings**

3. **`schedules`** - Availability schedules
   - Fields: `id`, `listing_id`, `day_of_week`, `date`, `start_time`, `end_time`, `source_location_id`, `is_expired`, `created_at`
   - Currently contains: **0 schedules**

4. **`tags`** - Categorization tags
   - Fields: `id`, `name` (unique)
   - Currently contains: **8 tags** (NEW, BLONDE, BUSTY, EUROPEAN, LATINA, ASIAN, PETITE, BRUNETTE)

5. **`listing_tags`** - Many-to-many relationship between listings and tags
   - Fields: `listing_id`, `tag_id`
   - Currently contains: **0 relationships**

6. **`tiers`** - Tier definitions (VIP, Platinum VIP, etc.)
   - Fields: `id`, `source_id`, `name`, `stars`, `incall_30min`, `incall_45min`, `incall_1hr`, `outcall_1hr`, `created_at`, `updated_at`

7. **`source_locations`** - Location information for sources
   - Fields: `id`, `source_id`, `town`, `location`, `address`, `created_at`, `updated_at`, `notes`

8. **`listing_tags`** - Association table (already mentioned above)

### Database Indexes

The database has several indexes for performance:
- `idx_listing_source_id` - On `listings.source_id`
- `idx_listing_tier` - On `listings.tier`
- `idx_listing_is_expired` - On `listings.is_expired`
- `idx_listing_is_active` - On `listings.is_active`
- `idx_listing_updated_at` - On `listings.updated_at`
- `idx_listing_age` - On `listings.age`
- `idx_listing_nationality` - On `listings.nationality`
- `idx_listing_hair_color` - On `listings.hair_color`
- `idx_schedule_listing_id` - On `schedules.listing_id`
- `idx_schedule_date` - On `schedules.date`
- `idx_schedule_source_location_id` - On `schedules.source_location_id`
- `idx_schedule_day_of_week` - On `schedules.day_of_week`

---

## Scraping Implementation

### Current Scrapers

#### 1. **SexyFriendsTorontoScraper** (`backend/api/scraper.py`)

**Source:** `https://www.sexyfriendstoronto.com`

**Implementation Details:**

**Class Structure:**
- `__init__(db: Session)` - Initializes with database session
- `get_or_create_source()` - Gets or creates the source record
- `fetch_page(url)` - Async HTTP request using httpx
- `parse_time_range(time_str)` - Parses time ranges like "12PM-12AM"
- `extract_tier(text)` - Extracts tier (PLATINUM VIP, ULTRA VIP, ELITE, VIP)
- `parse_schedule_page(html)` - Main parsing logic for schedule page
- `scrape_profile(profile_url)` - Scrapes individual profile pages
- `scrape_and_save()` - Main orchestration method

**Scraping Flow:**

1. **Schedule Page Parsing** (`parse_schedule_page`):
   - Fetches: `https://www.sexyfriendstoronto.com/toronto-escorts/schedule`
   - Parses HTML structure:
     - `h5` tags = Location headers (e.g., "NORTH YORK YONGE & SHEPPARD INCALL")
     - `h6` tags = Day headers (e.g., "Monday", "Tuesday")
     - `a` tags = Individual listings
   - Extracts from each listing:
     - Name (cleaned from tier markers and time strings)
     - Tier (PLATINUM VIP, ULTRA VIP, ELITE, VIP)
     - Profile URL slug
     - Location (from current h5 context)
     - Day of week (from current h6 context)
     - Start/end times (parsed from various formats)

2. **Profile Page Scraping** (`scrape_profile`):
   - Fetches individual profile pages
   - Extracts detailed information using regex patterns:
     - **Age**: `Age:\s*(\d+)`
     - **Nationality**: `Nationality:\s*([A-Za-z\s]+?)`
     - **Bust**: `Bust:\s*([\dA-Z\-]+)\s*(Natural|Enhanced)?`
     - **Height**: `Height:\s*(\d+['′''`´']\d*[\"″]?)`
     - **Weight**: `Weight:\s*([\d\s]+lbs?)`
     - **Eye Color**: `Eyes?:\s*([A-Za-z\s]+?)`
     - **Hair Color**: `Hair:\s*([A-Za-z\s]+?)`
     - **Tier**: `(ULTRA VIP|PLATINUM VIP|ELITE|VIP)`
     - **Service Type**: `(GF ENTERTAINER|PSE|MASSAGE|FETISH FRIENDLY|DOMINATRIX)`
     - **Rates**:
       - Incall 30min: `30\s*mins?\s*/\s*(\d+)`
       - Incall 45min: `45\s*mins?\s*/\s*(\d+)`
       - Incall 1hr: `1\s*hr?\s*/\s*(\d+)`
       - Outcall 1hr: `(\d+)\s*\+\s*/\s*HR`
     - **Images**: All `<img>` tags with class `p_gallery_img`
     - **Tags**: Keywords like NEW, BLONDE, BRUNETTE, BUSTY, PETITE, ASIAN, EUROPEAN, LATINA

3. **Data Persistence** (`scrape_and_save`):
   - Checks for existing listings by name and source_id
   - Creates new listings or updates existing ones
   - Always scrapes full profile data (line 308-326)
   - Creates schedule entries for each day/location combination
   - Associates tags with listings
   - Updates source `last_scraped` timestamp

**Time Parsing Logic:**

The scraper handles multiple time formats:
- Standard: `12PM-12AM`, `11:30AM-3:30PM`
- Missing M: `7P-11PM`, `1M-5PM` (auto-corrected)
- LATE: `11AM-LATE`, `1PM-LATE`
- Semicolon typo: `3;30PM` (converted to `3:30PM`)
- Single time: `3PM`, `3P`

**Error Handling:**
- Profile scraping errors are caught and logged (line 327-328)
- Continues processing other listings even if one fails

**Data Quality:**
- Skips invalid listings (name < 2 characters)
- Skips non-listing links (Design credits, Contact, etc.)
- Cleans tier markers from names
- Normalizes tier names

#### 2. **DiscreetDolls** (Configured but NOT Implemented)

**Status:** Source exists in database but **no scraper implementation found**

- Source name: `DiscreetDolls`
- URL: `https://discreetdolls.com`
- Last scraped: `2025-11-30 23:56:56.650937`
- **No scraper class exists** - This source is configured but not functional

---

## API Endpoints

### Backend API (`backend/api/main.py`)

**Base URL:** `http://localhost:8000`

#### Core Endpoints:

1. **`GET /`** - Root endpoint
   - Returns: `{"message": "E-Search API", "version": "1.0.0"}`

2. **`GET /api/sources`** - Get all scraping sources
   - Response: List of `SourceResponse` objects

3. **`POST /api/scrape/{source_name}`** - Scrape a specific source
   - Currently only supports: `sexyfriendstoronto`
   - Returns scraping results

4. **`POST /api/scrape-all`** - Scrape all active sources
   - Currently only calls `SexyFriendsTorontoScraper`
   - Returns: `{"results": [result1, result2, ...]}`

5. **`GET /api/listings`** - Get listings with filters
   - Query Parameters:
     - `source_ids` - Comma-separated source IDs
     - `days_of_week` - Comma-separated days (Monday,Tuesday,etc)
     - `hide_expired` - Boolean
     - `tier` - Filter by tier (VIP, PLATINUM VIP, etc)
     - `min_age` - Minimum age
     - `max_age` - Maximum age
     - `nationality` - Filter by nationality
     - `hair_color` - Filter by hair color
     - `tags` - Comma-separated tags
     - `search` - Search by name
     - `skip` - Pagination offset (default: 0)
     - `limit` - Pagination limit (default: 100, max: 500)
   - Response: List of `ListingResponse` objects

6. **`GET /api/listings/{listing_id}`** - Get single listing
   - Response: `ListingResponse` object

7. **`DELETE /api/listings/{listing_id}`** - Delete a listing

8. **`PUT /api/listings/{listing_id}/expire`** - Mark listing as expired

9. **`GET /api/tags`** - Get all available tags
   - Response: List of `TagResponse` objects

10. **`GET /api/stats`** - Get database statistics
    - Returns: `total_listings`, `active_listings`, `expired_listings`, `total_sources`, `active_sources`

11. **`DELETE /api/sources/{source_id}/data`** - Delete all listings for a source

### Database Viewer Endpoints (`backend/api/db_viewer.py`)

**Prefix:** `/db`

1. **`GET /db/tables`** - Get list of all tables with column info
2. **`GET /db/table/{table_name}`** - Get paginated table data
3. **`GET /db/query`** - Execute custom SQL (SELECT only)
4. **`GET /db/stats`** - Get database statistics

---

## Data Model Analysis

### Listing Data Structure

Each listing contains:

**Basic Info:**
- `name` - Escort name
- `profile_url` - Link to original profile
- `tier` - VIP level (VIP, PLATINUM VIP, ULTRA VIP, ELITE)

**Personal Details:**
- `age` - Integer
- `nationality` - String (e.g., "European", "Latina", "Asian")
- `height` - String (e.g., "5'9\"")
- `weight` - String (e.g., "138 lbs")
- `bust` - String (e.g., "34D-24-36")
- `bust_type` - String ("Natural" or "Enhanced")
- `eye_color` - String (e.g., "Green", "Brown")
- `hair_color` - String (e.g., "Blonde", "Brunette", "Black")
- `service_type` - String (e.g., "GF ENTERTAINER", "PSE", "MASSAGE")

**Rates:**
- `incall_30min` - Integer (price in dollars)
- `incall_45min` - Integer
- `incall_1hr` - Integer
- `outcall_1hr` - Integer
- `rate_notes` - Text (additional rate information)

**Media:**
- `images` - JSON array of image URLs (stored as Text)

**Metadata:**
- `is_active` - Boolean
- `is_expired` - Boolean
- `created_at` - DateTime
- `updated_at` - DateTime

**Relationships:**
- `source` - Many-to-one with Source
- `schedules` - One-to-many with Schedule
- `tags` - Many-to-many with Tag

### Schedule Data Structure

Each schedule entry represents availability:

- `day_of_week` - String (Monday, Tuesday, etc.)
- `date` - DateTime (optional, for specific dates)
- `start_time` - String (e.g., "12PM")
- `end_time` - String (e.g., "12AM" or "LATE")
- `source_location_id` - Foreign key to source_locations (optional)
- `is_expired` - Boolean
- `created_at` - DateTime

### Tag System

Tags are used for categorization:
- Examples: NEW, BLONDE, BUSTY, EUROPEAN, LATINA, ASIAN, PETITE, BRUNETTE
- Many-to-many relationship with listings
- Tags are extracted from profile text using keyword matching

---

## Key Findings

### Strengths

1. **Well-Structured Architecture**
   - Clean separation of concerns (scraper, database, API)
   - Proper use of SQLAlchemy ORM
   - Async/await for HTTP requests

2. **Robust Parsing Logic**
   - Handles multiple time formats
   - Cleans and normalizes data
   - Error handling for individual profile failures

3. **Comprehensive API**
   - Multiple filtering options
   - Pagination support
   - Database viewer endpoints for debugging

4. **Database Design**
   - Proper normalization
   - Indexes for performance
   - Foreign key relationships
   - Many-to-many tag system

### Issues & Gaps

1. **Missing Scraper Implementation**
   - `DiscreetDolls` source is configured but has no scraper class
   - Only `SexyFriendsTorontoScraper` is implemented

2. **Empty Database**
   - Currently 0 listings in database
   - May need to run scraping to populate

3. **Hardcoded Source Logic**
   - `/api/scrape-all` endpoint hardcodes `SexyFriendsTorontoScraper`
   - Not easily extensible for new sources

4. **No Rate Limiting**
   - Scraper doesn't implement delays between requests
   - Could be blocked by target websites

5. **Schema Mismatch (CRITICAL)**
   - **Database Model** (`database.py` line 85): `Schedule` model has `location = Column(String)`
   - **Actual Database Table**: Has `source_location_id INTEGER` instead of `location`
   - **Scraper Code** (line 344): Tries to set `location=item['location']` when creating Schedule
   - **Impact**: This will cause a SQLAlchemy error when scraping runs - the scraper tries to set a field that doesn't exist in the actual database table
   - **Root Cause**: Database was likely created with a different schema than the current model definition
   - **Fix Required**: Either:
     - Add `location` column to database: `ALTER TABLE schedules ADD COLUMN location VARCHAR;`
     - OR update scraper to use `source_location_id` and create location records first
     - OR update database model to match actual schema

---

## Recommendations

### Immediate Fixes

1. **Fix Schedule Location Field**
   - Either add `location` column to `schedules` table
   - Or use `source_location_id` and create location records

2. **Implement DiscreetDolls Scraper**
   - Create `DiscreetDollsScraper` class following the same pattern
   - Add to `/api/scrape-all` endpoint

3. **Add Rate Limiting**
   - Add delays between HTTP requests
   - Respect robots.txt

### Enhancements

1. **Dynamic Scraper Registration**
   - Use a registry pattern for scrapers
   - Auto-discover scrapers from a directory
   - Make `/api/scrape-all` iterate over registered scrapers

2. **Error Logging**
   - Add proper logging (currently uses print statements)
   - Log to file with rotation

3. **Data Validation**
   - Add Pydantic models for scraped data
   - Validate before saving to database

4. **Scheduled Scraping**
   - Add cron job or scheduled task support
   - Configurable intervals per source

5. **Monitoring**
   - Track scraping success/failure rates
   - Alert on scraping failures
   - Dashboard for scraping health

---

## Code Quality Assessment

### Positive Aspects

- ✅ Clean code structure
- ✅ Type hints used
- ✅ Async/await properly implemented
- ✅ Error handling present
- ✅ Database relationships properly defined
- ✅ API follows REST conventions

### Areas for Improvement

- ⚠️ Some hardcoded values
- ⚠️ Missing comprehensive error handling
- ⚠️ No logging framework
- ⚠️ Schema mismatch between code and database
- ⚠️ Limited test coverage (no tests found)

---

## Conclusion

The E-Search project is a well-architected web scraping application with a solid foundation. The main scraper (`SexyFriendsTorontoScraper`) is well-implemented with robust parsing logic. However, there are some gaps:

1. Only one scraper is fully implemented (out of 2 configured sources)
2. Database schema mismatch needs to be fixed
3. Database is currently empty (needs scraping to populate)
4. Missing rate limiting and better error handling

The project demonstrates good software engineering practices and is extensible for adding new sources. With the recommended fixes, it should be production-ready.

---

**Analysis Date:** December 1, 2025
**Database Status:** Empty (0 listings, 0 schedules)
**Active Sources:** 2 (1 implemented, 1 not implemented)
**Tags:** 8 tags defined

