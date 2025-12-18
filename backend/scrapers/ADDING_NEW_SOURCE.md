# Adding a New Scraper Source

This guide explains how to add a new scraper source to E-Search with all the built-in features.

## Quick Start

All scrapers inherit from `BaseScraper` which provides:
- ✅ **Color-coded logging** - Green for new/extracted, blue for updated, red for errors, gray for missing
- ✅ **Progress tracking** - Automatic progress updates with ❯❯❯ separators
- ✅ **Field extraction logging** - Shows what was scraped vs what's missing
- ✅ **Frontend status banner** - Real-time scraping progress in the UI
- ✅ **Error handling** - Automatic error capture and logging
- ✅ **Database management** - Automatic save/update logic

## Step 1: Create Your Scraper File

Create a new file in `backend/scrapers/sites/`:

```bash
touch backend/scrapers/sites/yoursite.py
```

## Step 2: Implement the Scraper

```python
"""
YourSite scraper.

Brief description of the site and how it works.
"""

from typing import List, Dict, Any
from bs4 import BeautifulSoup

from ..base import BaseScraper, ScheduleItem
from ..config import get_site_config
from ..crawlers.static import StaticCrawler  # or stealth.StealthCrawler
from ..utils.normalizers import (
    normalize_name,
    normalize_height,
    normalize_weight,
    normalize_measurements,
    normalize_bust_size,
)

class YourSiteScraper(BaseScraper):
    """Scraper for YourSite."""

    def __init__(self, db=None):
        config = get_site_config('yoursite')  # Define in config.py
        super().__init__(config, db)
        self.crawler = StaticCrawler()  # or StealthCrawler() for JS-heavy sites

    async def scrape_schedule(self) -> List[ScheduleItem]:
        """
        Scrape the schedule page to get all listings.

        Returns:
            List of ScheduleItem objects with basic info and schedules
        """
        soup = await self.crawler.fetch_soup(self.config.schedule_url)
        items = []

        # Example: Find all listing cards
        cards = soup.find_all('div', class_='listing-card')

        for card in cards:
            name = card.find('h3').get_text(strip=True)
            profile_url = card.find('a')['href']

            # Extract schedule info from the card
            day = card.find('span', class_='day').get_text(strip=True)
            time = card.find('span', class_='time').get_text(strip=True)
            location = card.find('span', class_='location').get_text(strip=True)

            items.append(ScheduleItem(
                name=normalize_name(name),
                profile_url=profile_url,
                tier=None,  # Extract if available
                schedules=[{
                    'day_of_week': day,
                    'location': location,
                    'start_time': time.split('-')[0].strip(),
                    'end_time': time.split('-')[1].strip() if '-' in time else None,
                }]
            ))

        return items

    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape an individual profile page.

        Args:
            profile_url: Profile slug or path (not full URL)

        Returns:
            Dictionary of profile data
        """
        full_url = f"{self.config.base_url}{profile_url}"
        soup = await self.crawler.fetch_soup(full_url)
        return self._parse_profile(soup, profile_url)

    def _parse_profile(self, soup: BeautifulSoup, profile_slug: str = "") -> Dict[str, Any]:
        """
        Parse profile page HTML.

        This is where you extract all the details about a listing.
        """
        profile = {}

        # Extract all available fields
        # Age
        age_text = soup.find('span', class_='age')
        if age_text:
            profile['age'] = int(age_text.get_text(strip=True))

        # Height
        height_text = soup.find('span', class_='height')
        if height_text:
            profile['height'] = normalize_height(height_text.get_text(strip=True))

        # Weight
        weight_text = soup.find('span', class_='weight')
        if weight_text:
            profile['weight'] = normalize_weight(weight_text.get_text(strip=True))

        # Bust
        bust_text = soup.find('span', class_='bust')
        if bust_text:
            profile['bust'] = normalize_bust_size(bust_text.get_text(strip=True))

        # Measurements
        measurements_text = soup.find('span', class_='measurements')
        if measurements_text:
            profile['measurements'] = normalize_measurements(measurements_text.get_text(strip=True))

        # Nationality
        nationality_text = soup.find('span', class_='nationality')
        if nationality_text:
            profile['nationality'] = nationality_text.get_text(strip=True).title()

        # Ethnicity
        ethnicity_text = soup.find('span', class_='ethnicity')
        if ethnicity_text:
            profile['ethnicity'] = ethnicity_text.get_text(strip=True).title()

        # Hair color
        hair_text = soup.find('span', class_='hair')
        if hair_text:
            profile['hair_color'] = hair_text.get_text(strip=True).title()

        # Eye color
        eyes_text = soup.find('span', class_='eyes')
        if eyes_text:
            profile['eye_color'] = eyes_text.get_text(strip=True).title()

        # Service type
        service_text = soup.find('span', class_='service')
        if service_text:
            profile['service_type'] = service_text.get_text(strip=True)

        # Tier
        tier_text = soup.find('span', class_='tier')
        if tier_text:
            profile['tier'] = tier_text.get_text(strip=True)

        # Images
        image_tags = soup.find_all('img', class_='gallery-image')
        if image_tags:
            profile['images'] = [img['src'] for img in image_tags]

        # Tags
        tag_elements = soup.find_all('span', class_='tag')
        if tag_elements:
            profile['tags'] = [tag.get_text(strip=True) for tag in tag_elements]

        # Schedules (if available on profile page)
        # ... extract schedule data if present ...

        # ⭐ IMPORTANT: This one line gives you all the logging features!
        # It will show what fields were extracted (green) vs missing (gray)
        self.log_profile_extraction(profile_slug, profile)

        return profile

    async def run(self):
        """Override run to ensure crawler cleanup."""
        try:
            return await super().run()
        finally:
            if hasattr(self.crawler, 'close'):
                try:
                    await self.crawler.close()
                except Exception as e:
                    self.logger.warning(f"Error during crawler cleanup: {e}")
```

## Step 3: Add Site Configuration

In `backend/scrapers/config.py`, add your site config:

```python
'yoursite': SiteConfig(
    name='Your Site Name',
    short_name='YSN',
    base_url='https://yoursite.com',
    schedule_url='https://yoursite.com/schedule',
    scraper_type=ScraperType.STATIC,  # or STEALTH for anti-bot sites
)
```

## Step 4: Register the Scraper

In `backend/scrapers/__init__.py`, add your scraper:

```python
from .sites.yoursite import YourSiteScraper

SCRAPER_REGISTRY = {
    'sft': SexyFriendsTorontoScraper,
    'discreet': DiscreetDollsScraper,
    'yoursite': YourSiteScraper,  # Add this line
}
```

## Step 5: Add Database Source

Add a database migration or manually insert into the `sources` table:

```sql
INSERT INTO sources (name, short_name, base_url, is_active, created_at, updated_at)
VALUES ('Your Site Name', 'YSN', 'https://yoursite.com', 1, datetime('now'), datetime('now'));
```

## Step 6: Add to API Source Map

In `backend/api/main.py`, add mappings to `source_map`:

```python
source_map = {
    # ... existing mappings ...
    "yoursite": "yoursite",
    "ysn": "yoursite",  # short name alias
}
```

## Step 7: Add Default Location

Every source needs a default location for fallback. Run:

```sql
-- Get your source ID first
SELECT id FROM sources WHERE name = 'YSN';

-- Add default location (replace 7 with your source ID)
INSERT INTO locations (source_id, town, location, is_default)
VALUES (7, 'Unknown', 'Unknown', 1);

-- Add specific locations your site uses
INSERT INTO locations (source_id, town, location, is_default) VALUES
    (7, 'Downtown', 'Main Location', 0),
    (7, 'North York', 'North York', 0);
```

## That's It!

Your scraper now has:

### **Automatic Logging**

When you run the scraper:
```bash
curl -X POST http://localhost:8000/api/scrape/yoursite
```

You'll see beautiful logs like:
```
❯❯❯
[1/50] Processing Jane Doe (jane-doe) - 2 schedule(s)
   ➤ jane-doe: age, nationality, height, bust, measurements, hair_color, eye_color, tier, images, schedules
   [NEW] Jane Doe: created new listing

❯❯❯
[2/50] Processing Sarah Smith (sarah-smith) - 3 schedule(s)
   ➤ sarah-smith: age, height, bust, ethnicity, nationality, hair_color, images
   [UPD] Sarah Smith: updated existing listing

Progress: 10/50 profiles (8 new, 1 updated, 1 errors)
```

### **Frontend Status Banner**

The frontend will automatically show a status banner with:
- Source name
- Progress (X/Y)
- New listings count (green)
- Updated count (blue)
- Errors count (red)

### **Field Tracking**

All 15 standard fields are tracked:
- age
- nationality
- ethnicity
- height
- weight
- bust
- bust_type
- measurements
- hair_color
- eye_color
- service_type
- tier
- images
- tags
- schedules

Captured fields shown with `➤`, missing fields shown with `✘` on a separate line.

---

## Architecture Reference

### File Structure
```
backend/scrapers/
├── __init__.py          # SCRAPER_REGISTRY - register new scrapers here
├── base.py              # BaseScraper class and data classes
├── config.py            # SiteConfig definitions
├── manager.py           # ScraperManager orchestration
├── sites/
│   ├── sft.py           # SexyFriendsToronto scraper
│   ├── dd.py            # DiscreetDolls scraper
│   └── yoursite.py      # Your new scraper
├── crawlers/
│   ├── static.py        # StaticCrawler (BeautifulSoup)
│   └── stealth.py       # StealthCrawler (Camoufox)
└── utils/
    ├── extractors.py    # Field extraction helpers
    └── normalizers.py   # Data normalization helpers
```

### Database Schema

**Sources Table:**
```sql
CREATE TABLE sources (
    id INTEGER PRIMARY KEY,
    name VARCHAR UNIQUE,        -- Display name: 'SFT', 'DD'
    url VARCHAR,                -- Schedule page URL
    base_url VARCHAR,           -- Profile base URL
    image_base_url VARCHAR,     -- Image base URL (optional)
    active BOOLEAN DEFAULT 1,
    last_scraped DATETIME,
    created_at DATETIME
);
```

**Related Tables:**
- `listings` - Individual profiles (source_id → sources.id)
- `schedules` - Availability (listing_id → listings.id)
- `locations` - Service areas (source_id → sources.id)
- `tiers` - Pricing tiers (source_id → sources.id)
- `tags` - Profile tags (many-to-many via listing_tags)

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/scrape/{source_name}` | Trigger scrape for one source |
| POST | `/api/scrape-all` | Trigger scrape for all sources |
| GET | `/api/scrapers` | List all scrapers & status |
| GET | `/api/sources` | Get all sources from DB |

**API Mapping** (`backend/api/main.py`):
```python
source_map = {
    "sft": "sft",
    "sexyfriendstoronto": "sft",
    "dd": "discreet",
    "discreet": "discreet",
    # Add your mappings here
}
```

### Frontend Integration

The frontend automatically handles new sources:

1. **Source Buttons** - `GET /api/sources` populates filter buttons
2. **Scrape Buttons** - Database page shows scrape button per source
3. **Status Banner** - Real-time progress polling from logs
4. **Listings** - Filtered by source, uses `base_url` for profile links

No frontend changes needed for basic functionality.

---

## Tips

### Use Normalizers
Always use the built-in normalizers for consistent data:
- `normalize_name()` - Clean names (handles "S O F I A" → "Sofia", camelCase, etc.)
- `normalize_height()` - Convert to consistent format (5'9", 170cm)
- `normalize_weight()` - Handle lbs/kg conversion
- `normalize_bust_size()` - Standardize cup sizes ("34DD" → "34 DD")
- `normalize_measurements()` - Format as "34C-24-36"

### Clean Up Names from Profile Pages
Profile pages often have messy names. Clean them up:
```python
# Remove site name suffixes
name = re.sub(r'\s*[-,]\s*Site Name.*$', '', name, flags=re.IGNORECASE)
name = re.sub(r'\s*At\s+Site Name.*$', '', name, flags=re.IGNORECASE)
# Remove common prefixes
name = re.sub(r'^Elite\s+Companion\s*', '', name, flags=re.IGNORECASE)
```

### Choose the Right Crawler
- **StaticCrawler**: Fast, for simple HTML sites (most sites work with this)
- **StealthCrawler/CrawleeStealth**: For sites with anti-bot protection or heavy JavaScript
- **Note**: Many "JavaScript" sites actually serve HTML that works with StaticCrawler. Test first!

### Analyzing a New Site
Before writing a scraper:
1. **Check schedule page** - How is schedule data encoded? (CSS classes, data attributes, JSON)
2. **Check profile page** - What stats are available? What are the exact field names?
3. **Decide approach**:
   - **DOM-based**: Parse structured HTML elements (like DD scraper)
   - **Regex-based**: Extract from text patterns (like SFT scraper)
   - **CSS class parsing**: Data encoded in classes (like TDL scraper)

### Debug Logging
Add debug logs where helpful:
```python
self.logger.debug(f"Parsing profile for {profile_slug}")
self.logger.debug(f"Found {len(images)} images")
```

### Error Handling
The base class handles errors automatically, but you can add specific handling:
```python
try:
    age = int(age_text.get_text())
except (ValueError, AttributeError) as e:
    self.logger.warning(f"Could not parse age for {profile_slug}: {e}")
```

## Testing Your Scraper

```bash
# Test scraping
curl -X POST http://localhost:8000/api/scrape/yoursite

# View logs
tail -f /tmp/esearch-backend.log

# Check database
sqlite3 backend/data/escort_listings.db "SELECT * FROM listings WHERE source_id = (SELECT id FROM sources WHERE short_name = 'YSN');"

# Check schedules have locations
sqlite3 data/escort_listings.db "SELECT l.name, s.day_of_week, loc.town, loc.location FROM schedules s JOIN listings l ON s.listing_id = l.id JOIN locations loc ON s.location_id = loc.id WHERE l.source_id = 7 LIMIT 10"
```

## Common Pitfalls

### 1. "Location not found" Error
Every source needs a default location with `is_default=1`. If you see this error, add:
```sql
INSERT INTO locations (source_id, town, location, is_default) VALUES (YOUR_SOURCE_ID, 'Unknown', 'Unknown', 1);
```

### 2. Scraper Not Found After Adding
**Server must be restarted** to pick up new scrapers. Kill and restart uvicorn.

### 3. Greedy Regex Capturing Wrong Values
When parsing text like "Hair Color: Brunette Body Size: 34C", a greedy regex might capture "Brunette Body". Solutions:
- Use non-greedy quantifiers: `([A-Za-z]+?)`
- Filter invalid values: `if hair.lower() not in ('body', 'size')`
- Return early with specific patterns

### 4. Protocol-Relative URLs
Image URLs like `//cdn.example.com/img.jpg` need protocol added:
```python
if url.startswith('//'):
    url = 'https:' + url
```

### 5. Name Cleanup
Profile page titles often include site name. Always clean:
```python
name = re.sub(r'\s*[-–|]\s*Site Name.*$', '', name, flags=re.IGNORECASE)
```

### 6. base_url Should Be the Profile Page Base
`base_url` is used to construct profile page URLs, **not** the site root. If profiles are at:
- `https://example.com/escorts/jane` → `base_url = 'https://example.com/escorts/'`
- `https://example.com/collections/all/products/jane` → `base_url = 'https://example.com/collections/all/products/'`

Then in your scraper, simply: `full_url = f"{self.config.base_url}{profile_slug}"`

### 7. Tier Information in URL Slugs
Some sites encode tier in the URL slug (e.g., `disha-vip`, `eliza-ultra-vip`). Check slugs before page content:
```python
slug_lower = profile_slug.lower()
if 'ultra-vip' in slug_lower:
    profile['tier'] = 'Ultra VIP'
elif '-vip' in slug_lower:
    profile['tier'] = 'VIP'
```

### 8. Don't Forget to Add Tiers
If the site has pricing tiers, add them to the `tiers` table:
```sql
INSERT INTO tiers (source_id, tier, star, incall_30min, incall_1hr, outcall_per_hr, created_at) VALUES
    (YOUR_SOURCE_ID, 'Normal', 1, '$160', '$260', '$300', datetime('now')),
    (YOUR_SOURCE_ID, 'VIP', 2, '$200', '$300', '$350', datetime('now'));
```

## Need Help?

- Check existing scrapers: `backend/scrapers/sites/sft.py` and `backend/scrapers/sites/dd.py`
- Review base scraper: `backend/scrapers/base.py`
- See normalizers: `backend/scrapers/utils/normalizers.py`
- Check extractors: `backend/scrapers/utils/extractors.py`

Happy scraping! 🎉
