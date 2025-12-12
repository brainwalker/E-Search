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
- `normalize_name()` - Clean names
- `normalize_height()` - Convert to consistent format
- `normalize_weight()` - Handle lbs/kg
- `normalize_bust_size()` - Standardize cup sizes
- `normalize_measurements()` - Format as "34C-24-36"

### Choose the Right Crawler
- **StaticCrawler**: Fast, for simple HTML sites
- **StealthCrawler**: For sites with anti-bot protection or JavaScript

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
```

## Need Help?

- Check existing scrapers: `backend/scrapers/sites/sft.py` and `backend/scrapers/sites/dd.py`
- Review base scraper: `backend/scrapers/base.py`
- See normalizers: `backend/scrapers/utils/normalizers.py`
- Check extractors: `backend/scrapers/utils/extractors.py`

Happy scraping! 🎉
