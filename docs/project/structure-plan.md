# Folder Structure Reorganization Plan

## Current Issues

### 1. Root Directory Clutter
- 10+ markdown documentation files in root
- Database file in wrong location (backend/ instead of backend/data/)
- Migration scripts mixed with application code
- No clear separation of concerns

### 2. Backend Structure
- Migration scripts in `backend/` root instead of dedicated folder
- Database file in `backend/` instead of `backend/data/`
- No separation of models, routes, services, and utilities
- Seed scripts in `api/` folder instead of dedicated scripts folder

### 3. Missing Standard Folders
- No `tests/` directory for unit/integration tests
- No `scripts/` directory for management scripts
- No `config/` directory for configuration files
- No `.env` file for environment variables

### 4. Documentation
- Too many docs in root directory
- No organized `docs/` folder
- Hard to find specific documentation

## Proposed New Structure

```
E-Search/
├── .git/
├── .github/                    # GitHub workflows (future)
│   └── workflows/
│
├── docs/                       # 📚 All documentation
│   ├── README.md              # Main documentation index
│   ├── api/                   # API documentation
│   │   ├── endpoints.md
│   │   └── responses.md
│   ├── database/              # Database documentation
│   │   ├── schema.md         # DATABASE_SCHEMA.md
│   │   ├── migrations.md     # Migration guide
│   │   └── locations.md      # LOCATIONS_UPDATE.md
│   ├── guides/               # User guides
│   │   ├── quickstart.md     # QUICKSTART.md
│   │   ├── git-workflow.md   # Git workflow docs
│   │   └── branching.md      # BRANCHING_STRATEGY.md
│   └── project/              # Project documentation
│       ├── analysis.md       # PROJECT_ANALYSIS.md
│       └── summary.md        # PROJECT_SUMMARY.md
│
├── backend/
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py           # FastAPI app entry
│   │   │
│   │   ├── models/           # 🆕 Database models
│   │   │   ├── __init__.py
│   │   │   ├── base.py       # Base model
│   │   │   ├── source.py     # Source model
│   │   │   ├── location.py   # Location model
│   │   │   ├── listing.py    # Listing model
│   │   │   ├── schedule.py   # Schedule model
│   │   │   └── tag.py        # Tag model
│   │   │
│   │   ├── routes/           # 🆕 API route handlers
│   │   │   ├── __init__.py
│   │   │   ├── listings.py   # Listing endpoints
│   │   │   ├── sources.py    # Source endpoints
│   │   │   ├── tags.py       # Tag endpoints
│   │   │   └── db_viewer.py  # Database viewer
│   │   │
│   │   ├── schemas/          # 🆕 Pydantic schemas
│   │   │   ├── __init__.py
│   │   │   ├── listing.py    # ListingResponse, etc.
│   │   │   ├── schedule.py   # ScheduleResponse
│   │   │   ├── location.py   # LocationResponse
│   │   │   └── source.py     # SourceResponse
│   │   │
│   │   ├── services/         # 🆕 Business logic
│   │   │   ├── __init__.py
│   │   │   └── scraper.py    # Scraper logic
│   │   │
│   │   ├── core/             # 🆕 Core utilities
│   │   │   ├── __init__.py
│   │   │   ├── config.py     # Configuration
│   │   │   ├── database.py   # DB connection
│   │   │   └── dependencies.py # FastAPI dependencies
│   │   │
│   │   └── utils/            # 🆕 Utility functions
│   │       ├── __init__.py
│   │       └── location_matcher.py # Location matching logic
│   │
│   ├── data/                 # 🆕 Database and data files
│   │   ├── .gitignore       # Ignore DB files
│   │   └── escort_listings.db
│   │
│   ├── scripts/              # 🆕 Management scripts
│   │   ├── __init__.py
│   │   ├── migrate.py       # Migration script
│   │   ├── seed_locations.py # Seed locations
│   │   └── dev_reset.py     # Reset DB for development
│   │
│   ├── tests/                # 🆕 Test suite
│   │   ├── __init__.py
│   │   ├── conftest.py      # Pytest configuration
│   │   ├── test_api/
│   │   │   ├── test_listings.py
│   │   │   └── test_sources.py
│   │   ├── test_models/
│   │   │   └── test_location.py
│   │   └── test_services/
│   │       └── test_scraper.py
│   │
│   ├── .env.example          # 🆕 Environment variables template
│   ├── requirements.txt
│   ├── requirements-dev.txt  # 🆕 Development dependencies
│   ├── run.sh
│   └── run.bat
│
├── frontend/
│   ├── assets/               # 🆕 Static assets
│   │   ├── css/
│   │   ├── js/
│   │   └── images/
│   ├── index.html
│   └── database.html
│
├── scripts/                  # 🆕 Project-level scripts
│   ├── setup.sh             # Initial setup script
│   ├── start.sh             # Start both frontend/backend
│   └── deploy.sh            # Deployment script
│
├── .gitignore
├── .env.example              # Environment variables
├── README.md                 # Main README (concise)
├── LICENSE                   # 🆕 License file
└── serve.py                  # Simple server for frontend
```

## Benefits of New Structure

### 1. **Better Organization**
- Clear separation of concerns (models, routes, schemas, services)
- Easy to find specific components
- Follows industry best practices (similar to Django, Flask patterns)

### 2. **Improved Maintainability**
- Smaller, focused files instead of monolithic ones
- Easy to add new features without touching existing code
- Clear dependencies between modules

### 3. **Better Performance**
- Lazy loading of modules
- Easier to cache and optimize specific components
- Database in dedicated `data/` folder with proper indexing

### 4. **Testing & Development**
- Dedicated `tests/` directory
- Easy to mock specific services
- Development scripts separated from application code

### 5. **Documentation**
- All docs in one place (`docs/`)
- Easy to generate API docs
- Clear navigation structure

### 6. **Security & Configuration**
- Environment variables in `.env` file
- Sensitive data not in code
- Config separated from logic

## Migration Steps

### Phase 1: Create New Structure (No Breaking Changes)
1. Create new directories
2. Create new organized files
3. Keep old files temporarily

### Phase 2: Move Backend Code
1. Split `database.py` into separate model files
2. Split `main.py` into routes
3. Extract schemas to dedicated files
4. Move scraper to services
5. Move utilities to utils/

### Phase 3: Move Documentation
1. Create `docs/` folder
2. Move and organize all .md files
3. Create docs index/README

### Phase 4: Move Data & Scripts
1. Create `data/` folder
2. Move database file
3. Update database path in config
4. Move migration scripts to `scripts/`

### Phase 5: Add Configuration
1. Create `.env.example`
2. Create `config.py`
3. Update code to use config

### Phase 6: Add Tests
1. Create test structure
2. Add pytest configuration
3. Write initial tests

### Phase 7: Cleanup
1. Remove old files
2. Update imports
3. Update documentation
4. Test everything

## File Breakdown

### Current Files → New Location

**Root Documentation Files:**
- `DATABASE_SCHEMA.md` → `docs/database/schema.md`
- `LOCATIONS_UPDATE.md` → `docs/database/locations.md`
- `MIGRATION_COMPLETE.md` → `docs/database/migrations.md`
- `QUICKSTART.md` → `docs/guides/quickstart.md`
- `BRANCHING_STRATEGY.md` → `docs/guides/branching.md`
- `PROJECT_ANALYSIS.md` → `docs/project/analysis.md`
- `PROJECT_SUMMARY.md` → `docs/project/summary.md`
- `README.md` → Keep, but simplify

**Backend Files:**
- `backend/api/database.py` → Split into `backend/api/models/*.py` + `backend/api/core/database.py`
- `backend/api/main.py` → Keep, but split routes to `backend/api/routes/*.py`
- `backend/api/scraper.py` → `backend/api/services/scraper.py`
- `backend/api/db_viewer.py` → `backend/api/routes/db_viewer.py`
- `backend/api/seed_locations.py` → `backend/scripts/seed_locations.py`
- `backend/migrate_auto.py` → `backend/scripts/migrate.py`
- `backend/migrate_to_locations.py` → Remove (replaced by migrate.py)
- `backend/escort_listings.db` → `backend/data/escort_listings.db`

## Configuration Files to Add

### `.env.example`
```env
# Database
DATABASE_URL=sqlite:///./data/escort_listings.db

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

### `backend/api/core/config.py`
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./data/escort_listings.db"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    class Config:
        env_file = ".env"

settings = Settings()
```

## Immediate Priorities

1. **High Priority** (Do Now):
   - Move database to `backend/data/`
   - Move migration scripts to `backend/scripts/`
   - Organize documentation into `docs/`

2. **Medium Priority** (Do Soon):
   - Split models into separate files
   - Split routes into separate files
   - Add configuration management

3. **Low Priority** (Do Later):
   - Add comprehensive tests
   - Add CI/CD workflows
   - Add advanced monitoring

## Backward Compatibility

During migration:
- Keep old paths working with symlinks or imports
- Update paths gradually
- Test after each change
- Document breaking changes

## Expected Improvements

### Code Quality
- ✅ Easier code review
- ✅ Better code reuse
- ✅ Clearer dependencies
- ✅ Easier refactoring

### Performance
- ✅ Faster imports (smaller modules)
- ✅ Better caching
- ✅ Easier optimization

### Development
- ✅ Faster onboarding for new developers
- ✅ Easier to add features
- ✅ Better IDE support
- ✅ Easier debugging

### Deployment
- ✅ Clear separation of code and data
- ✅ Easier to containerize (Docker)
- ✅ Environment-specific configs
- ✅ Better security
