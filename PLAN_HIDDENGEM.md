# HiddenGem Scraper Implementation Plan

## Site Overview

**Website:** https://hiddengemescorts.ca/
**Schedule URL:** https://hiddengemescorts.ca/toronto-escorts-schedule/
**Profile URL Pattern:** https://hiddengemescorts.ca/gem/{name}/
**Scraper Type:** STEALTH (JavaScript rendering required)

## Site Structure Analysis

### Schedule Page
- Uses JavaScript rendering for schedule data (Daily/Weekly tabs)
- Content loaded dynamically, requires browser execution
- Need to use CrawleeStealth or StealthCrawler

### Profile Page Structure
Stats are in `<p class="obj-title-box">` / `<p class="obj-box-value">` pairs:
- **Tier**: Pearl, Sapphire, Diamond, etc.
- **Age**: Number (e.g., "26")
- **Stats**: Measurements (e.g., "34C-26-35")
- **Height**: Imperial (e.g., "5'9\"")
- **Weight**: Imperial (e.g., "130 lbs")
- **Eyes**: Color (e.g., "Brown")
- **Hair**: Color (e.g., "Brunette")
- **Build**: Body type (e.g., "Slim, Tall, Athletic")
- **Background**: Ethnicity (e.g., "Eastern European/Indian")
- **Body**: Natural/Enhanced
- **Habits**: e.g., "Non-Smoker"
- **Talents**: Service type (e.g., "GFE+")

### Profile List Page
- `/meet-our-toronto-escorts-gems/` has all profiles with links
- Links pattern: `/gem/{name}/` (e.g., `/gem/maya/`, `/gem/abira/`)
- ~33 escorts visible

## Implementation Plan

### 1. Create HiddenGem scraper file
**File:** `/Users/shah/E-Search/backend/scrapers/sites/hiddengem.py`

Based on DD scraper pattern (also STEALTH type):
- Use CrawleeStealth crawler for anti-bot bypass
- Parse schedule from Daily/Weekly tabs
- Parse profile stats from `obj-title-box`/`obj-box-value` pairs

### 2. Update config
**File:** `/Users/shah/E-Search/backend/scrapers/config.py`

Update the existing `hiddengem` config to:
- Enable it (`enabled=True`)
- Verify base_url is `/gem/` (currently `https://hiddengemescorts.ca/`)

### 3. Register scraper in API
**File:** `/Users/shah/E-Search/backend/api/main.py`

Add HiddenGem to the scraper imports and registration.

### 4. Scraper Implementation Details

#### Schedule Parsing Strategy
Since schedule uses JS tabs (Daily/Weekly), we need to:
1. Fetch the schedule page with browser rendering
2. Look for day cards with escort info
3. Alternative: Scrape the `/meet-our-toronto-escorts-gems/` page for profiles list, then check each profile's schedule section

#### Profile Parsing
Stats structure:
```html
<p class="obj-title-box text-uppercase">Age</p>
<p class="obj-box-value">26</p>
```

Field mappings:
| Site Field | DB Field |
|------------|----------|
| Tier | tier |
| Age | age |
| Stats | measurements, bust (extract) |
| Height | height |
| Weight | weight |
| Eyes | eye_color |
| Hair | hair_color |
| Build | (tags or skip) |
| Background | ethnicity |
| Body | bust_type |
| Talents | service_type |

#### Expected Fields (for missing field warnings)
```python
expected_fields = [
    'age', 'ethnicity', 'height', 'weight', 'bust', 'bust_type',
    'measurements', 'hair_color', 'eye_color', 'tier', 'images', 'schedules'
]
```
(No nationality, service_type optional via Talents, no tags)

### 5. Tier Mapping
HGE tiers (visible from profiles):
- Pearl
- Sapphire
- Diamond

### 6. Images
Profile images are in `<figure class="obj-figure">` with `<img>` tags
URL pattern: `wp-content/uploads/YYYY/MM/filename.jpg`

## Files to Create/Modify

1. **CREATE:** `backend/scrapers/sites/hiddengem.py` - New scraper
2. **MODIFY:** `backend/scrapers/config.py` - Enable site, update base_url
3. **MODIFY:** `backend/api/main.py` - Register scraper

## Testing

After implementation:
1. Test schedule scraping: `PYTHONPATH=. python3 -c "from scrapers.sites.hiddengem import HiddenGemScraper; ..."`
2. Test profile scraping for individual profile
3. Full scrape test via API endpoint
