# Database Schema

## Table Structures

### Sources Table
Stores scraping sources.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| id | Integer | Primary Key | ✓ |
| name | String | Unique, Not Null | - |
| url | String | Not Null | - |
| active | Boolean | Default: True | - |
| last_scraped | DateTime | Nullable | - |
| created_at | DateTime | Default: now() | - |

**Relationships:**
- One-to-Many with Listings
- One-to-Many with Locations

---

### Locations Table ⭐ NEW
Stores predefined locations for each source.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| id | Integer | Primary Key | ✓ |
| source_id | Integer | FK → sources.id, Not Null | ✓ |
| town | String | Not Null | ✓ |
| location | String | Not Null | - |
| address | String | Nullable | - |
| notes | Text | Nullable | - |
| is_default | Boolean | Default: False | ✓ |
| created_at | DateTime | Default: now() | - |

**Indexes:**
- `ix_location_source_town_location` (Composite: source_id, town, location)

**Relationships:**
- Many-to-One with Source
- One-to-Many with Schedules

**Example Data:**
```
1 | 1 | Downtown | University & Queen | null | null | false
2 | 1 | Midtown | Yonge & Eglinton | null | null | false
12 | 1 | Unknown | unknown | null | null | true (DEFAULT)
```

---

### Listings Table
Stores escort listings.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| id | Integer | Primary Key | ✓ |
| source_id | Integer | FK → sources.id | - |
| name | String | Not Null | - |
| profile_url | String | Nullable | - |
| tier | String | Nullable | - |
| age | Integer | Nullable | - |
| nationality | String | Nullable | - |
| height | String | Nullable | - |
| weight | String | Nullable | - |
| bust | String | Nullable | - |
| bust_type | String | Nullable | - |
| eye_color | String | Nullable | - |
| hair_color | String | Nullable | - |
| service_type | String | Nullable | - |
| incall_30min | Integer | Nullable | - |
| incall_45min | Integer | Nullable | - |
| incall_1hr | Integer | Nullable | - |
| outcall_1hr | Integer | Nullable | - |
| rate_notes | Text | Nullable | - |
| images | Text | Nullable (JSON array) | - |
| is_active | Boolean | Default: True | - |
| is_expired | Boolean | Default: False | - |
| created_at | DateTime | Default: now() | - |
| updated_at | DateTime | Default/Update: now() | - |

**Relationships:**
- Many-to-One with Source
- One-to-Many with Schedules (cascade delete)
- Many-to-Many with Tags

---

### Schedules Table ⭐ UPDATED
Stores availability schedules for listings.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| id | Integer | Primary Key | ✓ |
| listing_id | Integer | FK → listings.id | ✓ |
| location_id | Integer | FK → locations.id | ✓ (NEW) |
| day_of_week | String | Nullable | ✓ |
| date | DateTime | Nullable | - |
| start_time | String | Nullable | - |
| end_time | String | Nullable | - |
| is_expired | Boolean | Default: False | ✓ |
| created_at | DateTime | Default: now() | - |

**Changes from Previous Version:**
- ❌ Removed: `location` (String)
- ✅ Added: `location_id` (Integer, FK → locations.id)
- ✅ Added: Indexes on location_id, day_of_week, is_expired

**Relationships:**
- Many-to-One with Listing
- Many-to-One with Location (NEW)

---

### Tags Table
Stores tags for categorizing listings.

| Column | Type | Constraints | Index |
|--------|------|-------------|-------|
| id | Integer | Primary Key | ✓ |
| name | String | Unique, Not Null | - |

**Relationships:**
- Many-to-Many with Listings (via listing_tags)

---

### Listing_Tags Table (Junction)
Association table for Listings ↔ Tags relationship.

| Column | Type | Constraints |
|--------|------|-------------|
| listing_id | Integer | FK → listings.id |
| tag_id | Integer | FK → tags.id |

---

## Relationships Diagram

```
┌──────────┐
│ Sources  │
└────┬─────┘
     │
     ├─────────────┐
     │             │
     ▼             ▼
┌──────────┐  ┌────────────┐
│Locations │  │  Listings  │
└────┬─────┘  └─────┬──────┘
     │              │
     │              ├──────────────┐
     │              │              │
     │              ▼              ▼
     │         ┌──────────┐  ┌─────────────┐
     │         │Schedules │  │listing_tags │
     └────────→└──────────┘  └──────┬──────┘
                                    │
                                    ▼
                               ┌─────────┐
                               │  Tags   │
                               └─────────┘
```

## Query Examples

### Get Listings with Location Information
```sql
SELECT
    l.name,
    s.day_of_week,
    s.start_time,
    s.end_time,
    loc.town,
    loc.location
FROM listings l
JOIN schedules s ON l.id = s.listing_id
JOIN locations loc ON s.location_id = loc.id
WHERE s.day_of_week = 'Monday'
  AND loc.town = 'Downtown';
```

### Find All Schedules at a Specific Location
```sql
SELECT
    l.name,
    s.day_of_week,
    s.start_time,
    loc.town || ', ' || loc.location as full_location
FROM schedules s
JOIN listings l ON s.listing_id = l.id
JOIN locations loc ON s.location_id = loc.id
WHERE loc.id = 3
ORDER BY s.day_of_week;
```

### Count Listings per Location
```sql
SELECT
    loc.town,
    loc.location,
    COUNT(DISTINCT s.listing_id) as listing_count
FROM locations loc
LEFT JOIN schedules s ON loc.id = s.location_id
WHERE loc.source_id = 1
GROUP BY loc.id, loc.town, loc.location
ORDER BY listing_count DESC;
```

### Get Default Location for a Source
```sql
SELECT * FROM locations
WHERE source_id = 1 AND is_default = true;
```

## Performance Considerations

### Indexed Columns
Fast lookups on these columns:
- `locations.source_id` - Filter locations by source
- `locations.town` - Filter by town
- `locations.is_default` - Find default location
- `locations.(source_id, town, location)` - Composite for matching
- `schedules.listing_id` - Join schedules to listings
- `schedules.location_id` - Join schedules to locations
- `schedules.day_of_week` - Filter by day
- `schedules.is_expired` - Filter active schedules

### Cascade Behaviors
- Deleting a **Listing** → Auto-deletes all its **Schedules**
- Deleting a **Source** → Does NOT auto-delete **Locations** or **Listings**
- Deleting a **Location** → Will fail if referenced by **Schedules** (referential integrity)

### Best Practices
1. Always use location_id when creating schedules
2. Don't delete locations that are in use
3. Use the default location as fallback for unknown locations
4. Index foreign keys for better join performance
5. Use eager loading for relationships in API responses
