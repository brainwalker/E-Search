# E-Search Project Instructions

## ⚠️ IMPORTANT: Git Branch

**Default branch: `Cursed-Cursor`** - Use for general development.
**Scraper migration branch: `Crawl4AI`** - Use for Crawlee/Camoufox migration work.

Before making any changes:
1. Verify you're on the correct branch: `git branch --show-current`
2. For scraper work, use `Crawl4AI` branch
3. For other work, use `Cursed-Cursor` branch

## 🚀 Current Project: Crawlee Migration

We are migrating the scraper system from `httpx + BeautifulSoup` to `Crawlee + Camoufox` to support 14 escort listing sources.

**Full Plan:** [docs/guides/crawlee-migration-plan.md](docs/guides/crawlee-migration-plan.md)

### Target Sources (14 total)

| # | Site | Short | Type | Status |
|---|------|-------|------|--------|
| 1 | sexyfriendstoronto.com | SFT | Static | ✅ Current |
| 2 | discreetdolls.com | DD | Stealth | ⏳ Pending |
| 3 | mirage-entertainment.cc | MIRAGE | JavaScript | ⏳ Pending |
| 4 | hiddengemescorts.ca | HGE | Stealth | ⏳ Pending |
| 5 | secretescorts.ca | SECRET | Static | ⏳ Pending |
| 6 | topdrawerladies.com | TDL | JavaScript | ⏳ Pending |
| 7 | selectcompanyescorts.com | SELECT | Static | ⏳ Pending |
| 8 | hotpinklist.com | HPL | JavaScript | ⏳ Pending |
| 9 | torontogirlfriends.com | TGF | Stealth | ⏳ Pending |
| 10 | torontopassions.com | PASSIONS | JavaScript | ⏳ Pending |
| 11 | allegraescortscollective.com | ALLEGRA | Static | ⏳ Pending |
| 12 | highsocietygirls.ca | HSG | Static | ⏳ Pending |
| 13 | gardenofedenescorts.com | EDEN | Static | ⏳ Pending |
| 14 | cupidsescorts.ca | CUPIDS | Static | ⏳ Pending |

### Scraper Types
- **Static (7):** Fast, uses BeautifulSoupCrawler
- **JavaScript (4):** Uses PlaywrightCrawler for JS rendering
- **Stealth (3):** Uses Camoufox for anti-bot bypass

## Project Structure

This project follows a well-organized folder structure. **ALL new files must follow this structure.**

```
E-Search/
├── docs/                    # 📚 ALL documentation
│   ├── database/           # Database-related docs
│   ├── guides/             # User guides and tutorials
│   │   └── crawlee-migration-plan.md  # 🆕 Scraper migration plan
│   ├── project/            # Project information
│   └── api/                # API documentation
│
├── backend/
│   ├── api/
│   │   ├── main.py         # FastAPI application
│   │   ├── database.py     # Database models
│   │   ├── scraper.py      # OLD scraper (keep for reference)
│   │   ├── config.py       # Configuration
│   │   └── db_viewer.py    # DB viewer routes
│   │
│   ├── scrapers/           # 🆕 NEW Crawlee-based scrapers
│   │   ├── __init__.py
│   │   ├── base.py         # BaseScraper abstract class
│   │   ├── manager.py      # ScraperManager orchestration
│   │   ├── config.py       # Site configurations (14 sites)
│   │   │
│   │   ├── crawlers/       # Crawler implementations
│   │   │   ├── static.py   # BeautifulSoupCrawler (fast)
│   │   │   ├── javascript.py # PlaywrightCrawler (JS)
│   │   │   └── stealth.py  # Camoufox (anti-bot)
│   │   │
│   │   ├── sites/          # Per-site scrapers
│   │   │   ├── sft.py      # SexyFriendsToronto
│   │   │   ├── discreet_dolls.py
│   │   │   ├── mirage.py
│   │   │   └── ... (14 total)
│   │   │
│   │   └── utils/          # Shared utilities
│   │       ├── extractors.py
│   │       └── normalizers.py
│   │
│   ├── data/               # Database files
│   │   └── escort_listings.db
│   │
│   ├── scripts/            # Management scripts
│   │   ├── migrate.py
│   │   └── seed_locations.py
│   │
│   ├── tests/              # Test suite
│   ├── worker.py           # 🆕 Background job worker
│   └── requirements.txt
│
├── frontend/
│   ├── index.html
│   └── database.html
│
├── docker-compose.yml      # 🆕 Docker orchestration
├── Dockerfile              # 🆕 Backend container
├── Dockerfile.scraper      # 🆕 Scraper worker container
├── .env.example
└── README.md
```

## File Placement Rules

### Documentation Files
- **Location:** `docs/` folder ONLY
- **Categories:**
  - `docs/database/` - Database schema, migrations, locations
  - `docs/guides/` - Tutorials, quickstart, workflows
  - `docs/project/` - Project analysis, summaries, plans
  - `docs/api/` - API documentation
- **Naming:** Use lowercase with hyphens (e.g., `quick-start.md`)

### Backend Code
- **Models:** `backend/api/database.py` (future: split to `backend/api/models/`)
- **Routes:** `backend/api/main.py` (future: split to `backend/api/routes/`)
- **Services:** `backend/api/scraper.py` (future: move to `backend/api/services/`)
- **Scripts:** `backend/scripts/` - ALL management/migration scripts
- **Database:** `backend/data/` - Database files ONLY

### Frontend Code
- **HTML:** `frontend/*.html`
- **Assets:** `frontend/assets/` (future: CSS, JS, images)

### Configuration
- **Environment:** `.env.example` in root (copy to `.env` for local use)
- **Python deps:** `backend/requirements.txt`

## Database Configuration

**Database Path:** `sqlite:///./data/escort_listings.db`

When creating database connections:
```python
engine = create_engine('sqlite:///./data/escort_listings.db', echo=False)
```

When working with database files in scripts:
```python
db_path = "./data/escort_listings.db"
backup_path = f"./data/escort_listings_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
```

## Locations Table

The project uses a normalized locations table:

```python
# When creating schedules, use location_id (NOT location string)
location_id = self.match_location(location_string, source.id)
schedule = Schedule(
    listing_id=listing.id,
    location_id=location_id,  # Foreign key to locations table
    day_of_week="Monday",
    # ...
)
```

**Available locations for SexyFriendsToronto:**
1. Vaughan, unknown
2. Midtown, Yonge & Eglinton
3. Downtown, University & Queen
4. Downtown, Bay & Gerrard St W
5. Downtown, Dundas & Jarvis
6. Downtown, University & Adelaide
7. Downtown, Front & Spadina
8. Etobicoke, HWY-427 & Burnhamthorpe Rd
9. Oakville, Trafalgar & Uppermiddle Rd E
10. Mississauga, SQ1
11. Brampton, Unknown
12. Unknown, unknown (DEFAULT)

## Creating New Files

### Python Files
```python
# backend/api/new_module.py
from api.database import get_db, Location, Source
from api.core.config import settings  # Future

# Use relative imports within api/
from .database import Listing
from .utils.helpers import some_helper  # Future
```

### Documentation Files
```markdown
# docs/category/new-doc.md

Always include:
- Clear title
- Table of contents for long docs
- Code examples
- Links to related docs
```

### Scripts
```python
# backend/scripts/new_script.py
from api.database import SessionLocal, Source, Location
from datetime import datetime

def main():
    """Main function"""
    db = SessionLocal()
    try:
        # Your code
        pass
    finally:
        db.close()

if __name__ == "__main__":
    main()
```

## "Sync" Command

When the user says "sync", perform these actions in order:

### 1. Compact & Organize
- Move any loose files to appropriate folders
- Ensure all docs are in `docs/`
- Ensure all scripts are in `backend/scripts/`
- Ensure database is in `backend/data/`

### 2. Update Documentation
- Update any outdated documentation
- Update README.md if structure changed
- Update docs/README.md index

### 3. Git Operations
```bash
# Add all changes
git add .

# Create descriptive commit message based on changes
git commit -m "type: descriptive message

- Detail 1
- Detail 2

🤖 Generated with Claude Code"

# Push changes
git push
```

### 4. Verify & Report
- List files moved/changed
- Show git status
- Confirm all changes applied
- Show new folder structure

### 5. Compact Reminder ⭐
After successful sync, remind the user about compacting:

**Message to show:**
```
✅ Sync complete! All changes pushed to git.

💡 Tip: Consider clicking the 'Compact' button to free up conversation memory.
   This will summarize our work and reduce context usage.
   All your work is safely saved in git!
```

**IMPORTANT:**
- Only remind, don't try to compact automatically (not possible)
- User can click the Compact button in Claude UI if they want
- Keep reminder brief and non-intrusive
- Compacting is optional, just a helpful suggestion

## Commit Message Format

```
type: brief description (50 chars or less)

Detailed explanation of changes:
- Bullet point 1
- Bullet point 2
- Bullet point 3

🤖 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:**
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `test:` - Adding tests
- `chore:` - Maintenance tasks
- `style:` - Code style changes

## Delete All Data Behavior

The "Delete All Data" button (`/api/sources/{source_id}/data`) behavior:

**Deletes:**
- All listings for the source
- All schedules (cascaded from listings)

**Preserves:**
- The source itself
- All locations
- All tags

This allows clearing data and re-scraping without losing configuration.

## Best Practices

### Code Organization
- Keep files focused and single-purpose
- Use meaningful names
- Follow existing naming conventions
- Add docstrings to functions/classes

### Documentation
- Update docs when changing functionality
- Include examples in documentation
- Keep README.md concise, detailed docs in `docs/`

### Database
- Always use `location_id` for schedules (not location strings)
- Use indexes for frequently queried fields
- Run migrations via `backend/scripts/migrate.py`

### Git
- Commit related changes together
- Write descriptive commit messages
- Don't commit database files (in .gitignore)
- Don't commit .env files (use .env.example)

## Common Tasks

### Add a New Location
```bash
cd backend
python3 -m scripts.seed_locations
# Or manually add to database
```

### Run Database Migration
```bash
cd backend
python3 -m scripts.migrate
```

### Start the Server
```bash
# From root
python3 serve.py

# Or manually
cd backend
python3 -m api.main
```

### Access Documentation
```bash
# View docs index
open docs/README.md

# Or specific docs
open docs/database/schema.md
open docs/guides/quickstart.md
```

## Environment Variables

Copy `.env.example` to `.env` and customize:

```env
# Database
DATABASE_URL=sqlite:///./backend/data/escort_listings.db

# API
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=False

# Frontend
FRONTEND_URL=http://localhost:3000

# Scraping
SCRAPER_TIMEOUT=30
SCRAPER_MAX_RETRIES=3
```

## Testing

When tests are added (future):
```bash
cd backend
pytest tests/
```

## Important Notes

1. **Never create files in root** unless it's a project-level file (like .env, README.md)
2. **All documentation goes in docs/** - no exceptions
3. **Database must be in backend/data/** - update code if needed
4. **Scripts go in backend/scripts/** - not in api/
5. **Follow the structure** - consistency is key

## Questions?

See:
- [Project Structure Plan](docs/project/structure-plan.md)
- [Database Schema](docs/database/schema.md)
- [Quick Start Guide](docs/guides/quickstart.md)
