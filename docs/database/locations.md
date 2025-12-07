# Locations Table Update

## Overview

This update introduces a dedicated `locations` table to improve data structure, performance, and maintainability.

## Changes Made

### 1. Database Schema Changes

#### New `Location` Table
- **Fields:**
  - `id` (Primary Key)
  - `source_id` (Foreign Key to sources table) - indexed
  - `town` (String, e.g., "Downtown", "Vaughan") - indexed
  - `location` (String, e.g., "Yonge & Eglinton")
  - `address` (Optional String) - for full addresses if available
  - `notes` (Optional Text) - for additional location info
  - `is_default` (Boolean) - marks default fallback location - indexed
  - `created_at` (DateTime)

- **Indexes:**
  - `source_id` - for faster source-based lookups
  - `town` - for filtering by town
  - `is_default` - for quick default location lookup
  - Composite index on `(source_id, town, location)` - for efficient location matching

#### Updated `Schedule` Table
- **Changed:**
  - `location` (String) → `location_id` (Foreign Key to locations table) - indexed
- **Added:**
  - Relationship to `Location` model
- **Indexes:**
  - `location_id` - for joining with locations table
  - `listing_id` - existing, improved performance
  - `day_of_week` - for day-based filtering
  - `is_expired` - for filtering expired schedules

### 2. Predefined Locations

The following locations have been seeded for **SexyFriendsToronto**:

| ID | Town | Location | Default |
|----|------|----------|---------|
| 1 | Vaughan | unknown | No |
| 2 | Midtown | Yonge & Eglinton | No |
| 3 | Downtown | University & Queen | No |
| 4 | Downtown | Bay & Gerrard St W | No |
| 5 | Downtown | Dundas & Jarvis | No |
| 6 | Downtown | University & Adelaide | No |
| 7 | Downtown | Front & Spadina | No |
| 8 | Etobicoke | HWY-427 & Burnhamthorpe Rd | No |
| 9 | Oakville | Trafalgar & Uppermiddle Rd E | No |
| 10 | Mississauga | SQ1 | No |
| 11 | Brampton | Unknown | No |
| 12 | Unknown | unknown | **Yes** |

### 3. Scraper Updates

The `SexyFriendsTorontoScraper` has been updated with:
- **New method:** `match_location(location_string, source_id)`
  - Matches scraped location strings to location IDs
  - Supports both exact matching and fuzzy matching
  - Falls back to default location if no match found
  - Auto-creates default location if missing

- **Updated schedule creation:**
  - Now uses `location_id` instead of storing location string directly
  - More efficient storage and querying

### 4. API Response Updates

#### New Response Model: `LocationResponse`
```python
{
    "id": int,
    "town": str,
    "location": str,
    "address": str | null,
    "notes": str | null
}
```

#### Updated `ScheduleResponse`
```python
{
    "id": int,
    "day_of_week": str,
    "start_time": str | null,
    "end_time": str | null,
    "location": LocationResponse | null,  # Changed from string to object
    "is_expired": bool
}
```

### 5. Delete All Data Behavior

The "Delete All Data" button (`/api/sources/{source_id}/data`) now explicitly:

**Deletes:**
- All listings for the source
- All schedules (cascaded from listings)

**Preserves:**
- The source itself
- All locations
- All tags

This allows you to clear data and re-scrape without losing location definitions or source configuration.

## Benefits

### Performance Improvements
1. **Indexed lookups** - Faster queries on location, source, and day filters
2. **Normalized data** - No duplicate location strings
3. **Efficient joins** - Direct foreign key relationships
4. **Composite indexes** - Optimized for common query patterns

### Data Integrity
1. **Referential integrity** - Foreign key constraints prevent orphaned records
2. **Centralized location management** - Single source of truth for locations
3. **Default fallback** - Ensures every schedule has a valid location

### Maintainability
1. **Easy updates** - Change location info in one place
2. **Reusable locations** - Same location used across multiple schedules
3. **Extendable** - Easy to add address, notes, or other location metadata

## Migration Instructions

### Option 1: Fresh Start (Recommended)

If you're okay with clearing all existing data:

```bash
cd backend
python migrate_to_locations.py
```

This will:
1. Backup your current database
2. Recreate tables with new schema
3. Seed locations for SexyFriendsToronto
4. Prepare database for new scrapes

### Option 2: Seed Locations Only

If you already have the new schema and just need locations:

```bash
cd backend
python -m api.seed_locations
```

## Usage Examples

### Filtering by Location (Future Enhancement)

You can extend the API to filter by location:

```python
# Get all listings in Downtown
GET /api/listings?location_town=Downtown

# Get all listings at a specific location
GET /api/listings?location_id=2
```

### Adding New Locations

Add locations via SQL or a management interface:

```python
new_location = Location(
    source_id=1,
    town="North York",
    location="Yonge & Finch",
    address="123 Yonge St",
    notes="Near subway station",
    is_default=False
)
db.add(new_location)
db.commit()
```

## Technical Notes

### Location Matching Algorithm

The scraper's `match_location()` method uses this strategy:

1. **Exact Match**: Try to match "Town - Location" or "Town, Location" format
2. **Fuzzy Match**: Search for locations where both town and location appear in string
3. **Default Fallback**: Use location with `is_default=True`
4. **Auto-create Default**: If no default exists, create one

This ensures every schedule gets a valid location_id.

### Database Structure

```
sources (1) ──┬─→ locations (*)
              └─→ listings (*)
                     └─→ schedules (*) ─→ locations (*)
```

## Files Changed

1. `backend/api/database.py` - Added Location model, updated Schedule model, added indexes
2. `backend/api/scraper.py` - Added location matching logic
3. `backend/api/main.py` - Updated API responses, clarified delete behavior
4. `backend/api/seed_locations.py` - Script to seed locations
5. `backend/migrate_to_locations.py` - Full migration script

## Testing

After migration:

1. **Test scraping:**
   ```bash
   # Visit http://localhost:8000/api/scrape/SexyFriendsToronto
   ```

2. **Verify locations:**
   ```bash
   # Check database viewer: http://localhost:3000/database.html
   # View locations table
   ```

3. **Test delete:**
   ```bash
   # Use "Delete All Data" button in database viewer
   # Verify locations and source are preserved
   ```

## Future Enhancements

Potential improvements for the locations system:

1. **Location Management UI** - Add/edit/delete locations from frontend
2. **Location-based Filtering** - Filter listings by town or specific location
3. **Geocoding** - Add latitude/longitude for map display
4. **Distance Calculations** - Find listings near a specific location
5. **Location Analytics** - Track popular locations over time
6. **Multi-source Locations** - Share locations across different sources
