# Crawlee Migration Plan

## Overview

This document outlines the complete plan to migrate E-Search from the current `httpx + BeautifulSoup` scraper to a `Crawlee + Camoufox` based architecture that can handle 14 escort listing sources with varying levels of anti-bot protection.

**Branch:** `Crawl4AI`
**Created:** December 8, 2025
**Status:** Planning Complete - Ready for Implementation

---

## Table of Contents

1. [Current State](#current-state)
2. [Target Architecture](#target-architecture)
3. [Source Sites Analysis](#source-sites-analysis)
4. [Implementation Phases](#implementation-phases)
5. [Phase 1: Foundation](#phase-1-foundation)
6. [Phase 2: Easy Sites](#phase-2-easy-sites)
7. [Phase 3: Medium Sites](#phase-3-medium-sites)
8. [Phase 4: Hard Sites](#phase-4-hard-sites)
9. [Phase 5: Docker & Deployment](#phase-5-docker--deployment)
10. [Phase 6: Cloud Migration](#phase-6-cloud-migration-optional)
11. [Testing Strategy](#testing-strategy)
12. [Rollback Plan](#rollback-plan)

---

## Current State

### Existing Stack
- **HTTP Client:** httpx (async)
- **Parser:** BeautifulSoup4
- **Extraction:** 50+ regex patterns
- **Database:** SQLite with SQLAlchemy
- **Sources:** 1 (SexyFriendsToronto)

### Limitations
- No JavaScript rendering
- No anti-bot bypass
- Brittle regex-based extraction
- Sequential scraping only
- No job queue or scheduling

---

## Target Architecture

### New Stack
```
┌─────────────────────────────────────────────────────────┐
│                    NAS / Network PC                      │
├─────────────────────────────────────────────────────────┤
│  Docker Compose                                          │
│  ┌─────────────────┐  ┌─────────────────┐               │
│  │   E-Search      │  │   PostgreSQL    │               │
│  │   Backend       │◄─┤   Database      │               │
│  │   (FastAPI)     │  │                 │               │
│  └────────┬────────┘  └─────────────────┘               │
│           │                                              │
│  ┌────────▼────────┐                                    │
│  │  Scraper Worker │                                    │
│  │  ┌────────────┐ │  ┌─────────────────┐               │
│  │  │  Crawlee   │ │  │   Redis         │               │
│  │  │  + Camoufox│ │◄─┤   (Job Queue)   │               │
│  │  │  + Playwright│ │  └─────────────────┘               │
│  │  └────────────┘ │                                    │
│  └─────────────────┘                                    │
│                                                          │
│  ┌─────────────────┐                                    │
│  │   Frontend      │  (Static files)                    │
│  └─────────────────┘                                    │
└─────────────────────────────────────────────────────────┘
```

### Components
| Component | Technology | Purpose |
|-----------|------------|---------|
| **Static Scraper** | Crawlee BeautifulSoupCrawler | Fast scraping for simple sites |
| **JS Scraper** | Crawlee PlaywrightCrawler | JavaScript-rendered sites |
| **Stealth Scraper** | Camoufox + Playwright API | Anti-bot protected sites |
| **Job Queue** | Redis + RQ | Background job processing |
| **Database** | PostgreSQL | Production database |
| **Scheduler** | APScheduler or Cron | Automated daily scrapes |

---

## Source Sites Analysis

### Site Difficulty Matrix

| # | Site | Short Name | Difficulty | Scraper Type | Priority |
|---|------|------------|------------|--------------|----------|
| 1 | sexyfriendstoronto.com | SFT | Easy | Static | Current |
| 2 | discreetdolls.com | DD | Hard | Stealth | P1 |
| 3 | mirage-entertainment.cc | MIRAGE | Medium | JavaScript | P2 |
| 4 | hiddengemescorts.ca | HGE | Hard | Stealth | P3 |
| 5 | secretescorts.ca | SECRET | Easy | Static | P4 |
| 6 | topdrawerladies.com | TDL | Medium | JavaScript | P5 |
| 7 | selectcompanyescorts.com | SELECT | Easy | Static | P6 |
| 8 | hotpinklist.com | HPL | Medium | JavaScript | P7 |
| 9 | torontogirlfriends.com | TGF | Hard | Stealth | P8 |
| 10 | torontopassions.com | PASSIONS | Medium | JavaScript | P9 |
| 11 | allegraescortscollective.com | ALLEGRA | Easy | Static | P10 |
| 12 | highsocietygirls.ca | HSG | Easy | Static | P11 |
| 13 | gardenofedenescorts.com | EDEN | Easy | Static | P12 |
| 14 | cupidsescorts.ca | CUPIDS | Easy | Static | P13 |

### By Scraper Type
- **Static (7 sites):** SFT, SECRET, SELECT, ALLEGRA, HSG, EDEN, CUPIDS
- **JavaScript (4 sites):** MIRAGE, TDL, HPL, PASSIONS
- **Stealth (3 sites):** DD, HGE, TGF

---

## Implementation Phases

### Overview Timeline

| Phase | Description | Sites | Estimated Effort |
|-------|-------------|-------|------------------|
| **Phase 1** | Foundation & Infrastructure | - | 1-2 sessions |
| **Phase 2** | Easy Sites (Static) | 7 sites | 3-4 sessions |
| **Phase 3** | Medium Sites (JavaScript) | 4 sites | 2-3 sessions |
| **Phase 4** | Hard Sites (Stealth) | 3 sites | 2-3 sessions |
| **Phase 5** | Docker & Deployment | - | 1-2 sessions |
| **Phase 6** | Cloud Migration (Optional) | - | 1 session |

---

## Phase 1: Foundation

### 1.1 Install Dependencies

**File:** `backend/requirements.txt`

```txt
# Add these new dependencies:

# Scraping - Crawlee
crawlee[playwright]>=0.5.0
camoufox[geoip]>=0.4.0
browserforge>=1.2.0

# Job Queue
redis>=5.0.0
rq>=1.16.0

# Database (PostgreSQL support)
psycopg2-binary>=2.9.9

# Scheduling
apscheduler>=3.10.0
```

**Commands:**
```bash
cd backend
source .venv/bin/activate
pip install crawlee[playwright] camoufox[geoip] browserforge redis rq
playwright install chromium firefox
python -c "from camoufox.sync_api import Camoufox; Camoufox(headless=True)"
```

### 1.2 Create Folder Structure

```
backend/
├── api/                    # Existing API code
│   ├── main.py
│   ├── database.py
│   ├── scraper.py          # OLD - keep for reference
│   └── ...
│
├── scrapers/               # NEW - Crawlee scrapers
│   ├── __init__.py
│   ├── base.py             # BaseScraper abstract class
│   ├── manager.py          # ScraperManager orchestration
│   ├── config.py           # Site configurations
│   │
│   ├── crawlers/           # Crawler implementations
│   │   ├── __init__.py
│   │   ├── static.py       # BeautifulSoupCrawler wrapper
│   │   ├── javascript.py   # PlaywrightCrawler wrapper
│   │   └── stealth.py      # Camoufox wrapper
│   │
│   ├── sites/              # Per-site scrapers
│   │   ├── __init__.py
│   │   ├── sft.py
│   │   ├── discreet_dolls.py
│   │   └── ... (one file per site)
│   │
│   └── utils/
│       ├── __init__.py
│       ├── extractors.py   # Common extraction helpers
│       ├── normalizers.py  # Data normalization
│       └── validators.py   # Data validation
│
├── worker.py               # Background job worker
├── scheduler.py            # Cron-like scheduler
└── requirements.txt
```

### 1.3 Create Base Classes

**File:** `backend/scrapers/base.py`

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

class ScraperType(Enum):
    STATIC = "static"           # httpx + BeautifulSoup
    JAVASCRIPT = "javascript"   # Playwright
    STEALTH = "stealth"         # Camoufox

@dataclass
class SiteConfig:
    """Configuration for a scraping source"""
    name: str                           # Full name
    short_name: str                     # Database identifier
    schedule_url: str                   # Schedule page URL
    base_url: str                       # Base URL for profiles
    scraper_type: ScraperType           # Which crawler to use
    image_base_url: Optional[str] = None
    requires_age_gate: bool = False
    rate_limit_seconds: float = 1.0
    selectors: Dict[str, str] = field(default_factory=dict)
    enabled: bool = True

@dataclass
class ScrapedListing:
    """Standardized listing data"""
    name: str
    profile_url: str
    source: str
    tier: Optional[str] = None
    age: Optional[int] = None
    nationality: Optional[str] = None
    ethnicity: Optional[str] = None
    height: Optional[str] = None
    weight: Optional[str] = None
    bust: Optional[str] = None
    bust_type: Optional[str] = None
    measurements: Optional[str] = None
    hair_color: Optional[str] = None
    eye_color: Optional[str] = None
    service_type: Optional[str] = None
    images: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    schedules: List[Dict] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

class BaseScraper(ABC):
    """Abstract base class for all site scrapers"""

    def __init__(self, config: SiteConfig, db_session):
        self.config = config
        self.db = db_session
        self.stats = {
            'started_at': None,
            'completed_at': None,
            'total': 0,
            'new': 0,
            'updated': 0,
            'errors': 0,
            'error_details': []
        }

    @abstractmethod
    async def scrape_schedule(self) -> List[Dict]:
        """Scrape schedule page, return raw listing data"""
        pass

    @abstractmethod
    async def scrape_profile(self, profile_url: str) -> Dict:
        """Scrape individual profile, return profile data"""
        pass

    def normalize_listing(self, raw_data: Dict) -> ScrapedListing:
        """Convert raw scraped data to standardized format"""
        # Subclasses can override for site-specific normalization
        return ScrapedListing(
            name=raw_data.get('name', ''),
            profile_url=raw_data.get('profile_url', ''),
            source=self.config.short_name,
            **{k: v for k, v in raw_data.items()
               if k in ScrapedListing.__dataclass_fields__ and k not in ['name', 'profile_url', 'source']}
        )

    async def run(self) -> Dict:
        """Main entry point - orchestrates the scraping"""
        self.stats['started_at'] = datetime.utcnow()

        try:
            # Step 1: Scrape schedule page
            schedule_items = await self.scrape_schedule()
            self.stats['total'] = len(schedule_items)

            # Step 2: Scrape each profile
            for item in schedule_items:
                try:
                    profile_data = await self.scrape_profile(item['profile_url'])
                    merged = {**item, **profile_data}
                    listing = self.normalize_listing(merged)
                    await self.save_listing(listing)
                except Exception as e:
                    self.stats['errors'] += 1
                    self.stats['error_details'].append({
                        'url': item.get('profile_url'),
                        'error': str(e)
                    })

            self.stats['completed_at'] = datetime.utcnow()
            return self.stats

        except Exception as e:
            self.stats['errors'] += 1
            self.stats['error_details'].append({'error': str(e)})
            raise

    async def save_listing(self, listing: ScrapedListing):
        """Save or update listing in database"""
        # Implementation will use existing database.py models
        pass
```

### 1.4 Create Site Configuration

**File:** `backend/scrapers/config.py`

```python
from .base import SiteConfig, ScraperType

# All 14 sites configured
SITES = {
    # ========== EASY (Static HTML) ==========
    'sft': SiteConfig(
        name='SexyFriendsToronto',
        short_name='SFT',
        schedule_url='https://www.sexyfriendstoronto.com/toronto-escorts/schedule',
        base_url='https://www.sexyfriendstoronto.com/toronto-escorts/',
        image_base_url='https://www.sexyfriendstoronto.com/toronto-escorts/thumbnails/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
    ),
    'secret': SiteConfig(
        name='SecretEscorts',
        short_name='SECRET',
        schedule_url='https://secretescorts.ca/availability/',
        base_url='https://secretescorts.ca/',
        scraper_type=ScraperType.STATIC,
        requires_age_gate=True,
        rate_limit_seconds=1.0,
    ),
    'select': SiteConfig(
        name='SelectCompanyEscorts',
        short_name='SELECT',
        schedule_url='https://www.selectcompanyescorts.com/schedule/',
        base_url='https://www.selectcompanyescorts.com/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
    ),
    'allegra': SiteConfig(
        name='AllegraEscortsCollective',
        short_name='ALLEGRA',
        schedule_url='https://allegraescortscollective.com/schedule-booking-rates/',
        base_url='https://allegraescortscollective.com/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
    ),
    'highsociety': SiteConfig(
        name='HighSocietyGirls',
        short_name='HSG',
        schedule_url='https://highsocietygirls.ca/',
        base_url='https://highsocietygirls.ca/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
    ),
    'garden': SiteConfig(
        name='GardenOfEdenEscorts',
        short_name='EDEN',
        schedule_url='https://gardenofedenescorts.com/schedule/',
        base_url='https://gardenofedenescorts.com/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
    ),
    'cupids': SiteConfig(
        name='CupidsEscorts',
        short_name='CUPIDS',
        schedule_url='https://www.cupidsescorts.ca/schedule/',
        base_url='https://www.cupidsescorts.ca/',
        scraper_type=ScraperType.STATIC,
        rate_limit_seconds=1.0,
    ),

    # ========== MEDIUM (JavaScript Rendering) ==========
    'mirage': SiteConfig(
        name='MirageEntertainment',
        short_name='MIRAGE',
        schedule_url='https://mirage-entertainment.cc/toronto-escorts-schedule/',
        base_url='https://mirage-entertainment.cc/',
        scraper_type=ScraperType.JAVASCRIPT,
        rate_limit_seconds=2.0,
    ),
    'topdrawer': SiteConfig(
        name='TopDrawerLadies',
        short_name='TDL',
        schedule_url='https://www.topdrawerladies.com/pages/schedule',
        base_url='https://www.topdrawerladies.com/',
        scraper_type=ScraperType.JAVASCRIPT,
        rate_limit_seconds=2.0,
    ),
    'hotpink': SiteConfig(
        name='HotPinkList',
        short_name='HPL',
        schedule_url='https://hotpinklist.com/schedule/',
        base_url='https://hotpinklist.com/',
        scraper_type=ScraperType.JAVASCRIPT,
        rate_limit_seconds=2.0,
    ),
    'passions': SiteConfig(
        name='TorontoPassions',
        short_name='PASSIONS',
        schedule_url='https://www.torontopassions.com/toronto-escorts-availability',
        base_url='https://www.torontopassions.com/',
        scraper_type=ScraperType.JAVASCRIPT,
        rate_limit_seconds=2.0,
    ),

    # ========== HARD (Stealth Required) ==========
    'discreet': SiteConfig(
        name='DiscreetDolls',
        short_name='DD',
        schedule_url='https://discreetdolls.com/daily-schedule/',
        base_url='https://discreetdolls.com/',
        scraper_type=ScraperType.STEALTH,
        rate_limit_seconds=3.0,
    ),
    'hiddengem': SiteConfig(
        name='HiddenGemEscorts',
        short_name='HGE',
        schedule_url='https://hiddengemescorts.ca/toronto-escorts-schedule/',
        base_url='https://hiddengemescorts.ca/',
        scraper_type=ScraperType.STEALTH,
        rate_limit_seconds=3.0,
    ),
    'torontogf': SiteConfig(
        name='TorontoGirlfriends',
        short_name='TGF',
        schedule_url='https://torontogirlfriends.com/schedule/',
        base_url='https://torontogirlfriends.com/',
        scraper_type=ScraperType.STEALTH,
        rate_limit_seconds=3.0,
    ),
}

def get_site_config(site_key: str) -> SiteConfig:
    """Get configuration for a site by key"""
    if site_key not in SITES:
        raise ValueError(f"Unknown site: {site_key}. Valid sites: {list(SITES.keys())}")
    return SITES[site_key]

def get_sites_by_type(scraper_type: ScraperType) -> dict:
    """Get all sites of a specific scraper type"""
    return {k: v for k, v in SITES.items() if v.scraper_type == scraper_type}

def get_enabled_sites() -> dict:
    """Get all enabled sites"""
    return {k: v for k, v in SITES.items() if v.enabled}
```

### 1.5 Create Crawler Wrappers

**File:** `backend/scrapers/crawlers/static.py`

```python
"""Static HTML crawler using Crawlee's BeautifulSoupCrawler"""
import asyncio
from typing import Optional
from crawlee.beautifulsoup_crawler import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from crawlee import ConcurrencySettings, HttpHeaders

class StaticCrawler:
    """Wrapper for Crawlee BeautifulSoupCrawler"""

    def __init__(self, rate_limit: float = 1.0):
        self.rate_limit = rate_limit
        self.results = {}

    async def fetch(self, url: str, wait_seconds: float = 0) -> str:
        """Fetch a single URL and return HTML"""
        html_content = None

        async def handler(context: BeautifulSoupCrawlingContext):
            nonlocal html_content
            html_content = str(context.soup)

        crawler = BeautifulSoupCrawler(
            concurrency_settings=ConcurrencySettings(max_concurrency=1),
            request_handler=handler,
        )

        if wait_seconds:
            await asyncio.sleep(wait_seconds)

        await crawler.run([url])
        return html_content

    async def fetch_many(self, urls: list[str]) -> dict[str, str]:
        """Fetch multiple URLs with rate limiting"""
        results = {}

        async def handler(context: BeautifulSoupCrawlingContext):
            results[context.request.url] = str(context.soup)
            await asyncio.sleep(self.rate_limit)

        crawler = BeautifulSoupCrawler(
            concurrency_settings=ConcurrencySettings(max_concurrency=1),
            request_handler=handler,
        )

        await crawler.run(urls)
        return results
```

**File:** `backend/scrapers/crawlers/javascript.py`

```python
"""JavaScript-rendering crawler using Crawlee's PlaywrightCrawler"""
import asyncio
from typing import Optional
from crawlee.playwright_crawler import PlaywrightCrawler, PlaywrightCrawlingContext
from crawlee import ConcurrencySettings

class JavaScriptCrawler:
    """Wrapper for Crawlee PlaywrightCrawler"""

    def __init__(self, rate_limit: float = 2.0, headless: bool = True):
        self.rate_limit = rate_limit
        self.headless = headless

    async def fetch(self, url: str, wait_selector: Optional[str] = None) -> str:
        """Fetch a URL with JavaScript rendering"""
        html_content = None

        async def handler(context: PlaywrightCrawlingContext):
            nonlocal html_content

            if wait_selector:
                await context.page.wait_for_selector(wait_selector, timeout=10000)
            else:
                await context.page.wait_for_load_state('networkidle')

            html_content = await context.page.content()

        crawler = PlaywrightCrawler(
            concurrency_settings=ConcurrencySettings(max_concurrency=1),
            request_handler=handler,
            headless=self.headless,
        )

        await crawler.run([url])
        return html_content

    async def fetch_with_interaction(
        self,
        url: str,
        actions: list[dict] = None,
        wait_selector: Optional[str] = None
    ) -> str:
        """Fetch with custom page interactions (clicks, scrolls, etc.)"""
        html_content = None

        async def handler(context: PlaywrightCrawlingContext):
            nonlocal html_content
            page = context.page

            # Execute custom actions
            if actions:
                for action in actions:
                    if action['type'] == 'click':
                        await page.click(action['selector'])
                    elif action['type'] == 'scroll':
                        await page.evaluate('window.scrollBy(0, window.innerHeight)')
                    elif action['type'] == 'wait':
                        await asyncio.sleep(action.get('seconds', 1))

            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=10000)

            html_content = await page.content()

        crawler = PlaywrightCrawler(
            concurrency_settings=ConcurrencySettings(max_concurrency=1),
            request_handler=handler,
            headless=self.headless,
        )

        await crawler.run([url])
        return html_content
```

**File:** `backend/scrapers/crawlers/stealth.py`

```python
"""Stealth crawler using Camoufox for anti-bot bypass"""
import asyncio
import random
from typing import Optional
from camoufox.async_api import AsyncCamoufox
from browserforge.fingerprints import Screen, Fingerprint

class StealthCrawler:
    """Camoufox-based crawler for maximum stealth"""

    def __init__(self, rate_limit: float = 3.0):
        self.rate_limit = rate_limit
        self.browser = None
        self.context = None

    async def __aenter__(self):
        # Generate realistic fingerprint
        fingerprint = Fingerprint(
            screen=Screen(max_width=1920, max_height=1080),
            os=('windows', 'macos'),
        )

        self.browser = await AsyncCamoufox(
            headless=True,
            fingerprint=fingerprint,
            geoip=True,
        ).__aenter__()

        self.context = await self.browser.new_context()
        return self

    async def __aexit__(self, *args):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.__aexit__(*args)

    async def fetch(
        self,
        url: str,
        wait_selector: Optional[str] = None,
        simulate_human: bool = True
    ) -> str:
        """Fetch page with stealth browser"""
        page = await self.context.new_page()

        try:
            # Random delay before request
            if simulate_human:
                await asyncio.sleep(random.uniform(0.5, 2.0))

            await page.goto(url, wait_until='networkidle')

            if wait_selector:
                await page.wait_for_selector(wait_selector, timeout=15000)

            # Simulate human behavior
            if simulate_human:
                await self._simulate_human(page)

            return await page.content()
        finally:
            await page.close()
            await asyncio.sleep(self.rate_limit)

    async def _simulate_human(self, page):
        """Simulate human-like behavior"""
        # Random mouse movement
        await page.mouse.move(
            random.randint(100, 500),
            random.randint(100, 500)
        )

        # Small random delay
        await asyncio.sleep(random.uniform(0.3, 1.0))

        # Random scroll
        await page.evaluate(f'window.scrollBy(0, {random.randint(100, 300)})')

        await asyncio.sleep(random.uniform(0.2, 0.5))

    async def handle_age_gate(self, page, button_selector: str = None):
        """Handle age verification popups"""
        common_selectors = [
            'button:has-text("Enter")',
            'button:has-text("I am 18")',
            'button:has-text("Yes")',
            '.age-gate-enter',
            '#age-verify-yes',
        ]

        if button_selector:
            common_selectors.insert(0, button_selector)

        for selector in common_selectors:
            try:
                button = await page.query_selector(selector)
                if button:
                    await button.click()
                    await asyncio.sleep(1)
                    return True
            except:
                continue

        return False
```

### 1.6 Migrate SFT Scraper

**File:** `backend/scrapers/sites/sft.py`

```python
"""SexyFriendsToronto scraper - migrated to Crawlee"""
import re
from typing import List, Dict
from bs4 import BeautifulSoup

from ..base import BaseScraper, ScrapedListing
from ..crawlers.static import StaticCrawler
from ..config import get_site_config

class SFTScraper(BaseScraper):
    """Scraper for SexyFriendsToronto"""

    def __init__(self, db_session):
        config = get_site_config('sft')
        super().__init__(config, db_session)
        self.crawler = StaticCrawler(rate_limit=config.rate_limit_seconds)

    async def scrape_schedule(self) -> List[Dict]:
        """Scrape the schedule page"""
        html = await self.crawler.fetch(self.config.schedule_url)
        return self._parse_schedule(html)

    def _parse_schedule(self, html: str) -> List[Dict]:
        """Parse schedule HTML into listing dicts"""
        soup = BeautifulSoup(html, 'html.parser')
        listings = []

        content = soup.find('div', class_='content') or soup.find('body') or soup

        current_location = None
        current_day = None

        for element in content.find_all(['h5', 'h6', 'a']):
            text = element.get_text(strip=True)

            if element.name == 'h5':
                current_location = text.replace('INCALL', '').strip()

            elif element.name == 'h6':
                current_day = text

            elif element.name == 'a' and current_day and current_location:
                profile_slug = element.get('href', '').strip('/')
                if not profile_slug or profile_slug.startswith('http'):
                    continue

                full_text = element.get_text(strip=True)

                # Skip non-listing links
                skip_patterns = ['P100.ca', 'Design', 'Website', 'Contact', 'About']
                if any(p.lower() in full_text.lower() for p in skip_patterns):
                    continue

                # Extract tier
                tier = self._extract_tier(full_text)

                # Extract name and time
                name, start_time, end_time = self._parse_listing_text(full_text)

                if len(name) < 2:
                    continue

                listings.append({
                    'name': self._normalize_name(name),
                    'profile_url': profile_slug,
                    'tier': tier,
                    'location': current_location,
                    'day_of_week': current_day,
                    'start_time': start_time,
                    'end_time': end_time,
                })

        return listings

    async def scrape_profile(self, profile_url: str) -> Dict:
        """Scrape individual profile page"""
        full_url = f"{self.config.base_url}{profile_url}"
        html = await self.crawler.fetch(full_url)
        return self._parse_profile(html)

    def _parse_profile(self, html: str) -> Dict:
        """Parse profile HTML into data dict"""
        soup = BeautifulSoup(html, 'html.parser')
        content = soup.find('div', class_='content') or soup.find('body') or soup
        text = content.get_text()

        profile = {}

        # Age
        age_match = re.search(r'Age[:\s]+(\d+)', text, re.IGNORECASE)
        if age_match:
            profile['age'] = int(age_match.group(1))

        # Nationality
        nat_match = re.search(
            r'Nationality(?:\s*\([^)]+\))?(?:/(?:Ethnicity|Race))?:\s*([A-Za-z\s/&,]+?)(?:Ethnicity|Race|Bust|Height|Weight|Eyes|Hair|Measurement|Age|Enhancement|\n|$)',
            text, re.IGNORECASE
        )
        if nat_match:
            profile['nationality'] = nat_match.group(1).strip().rstrip(',')

        # Height
        height_match = re.search(r'Height:\s*(\d+[\u2019\u2018\u0027\u2032\u0060\u00b4\u2033"\',]+\d+)', text, re.IGNORECASE)
        if height_match:
            profile['height'] = re.sub(r'[\u2019\u2018\u2032\u0060\u00b4\u2033"\',]', "'", height_match.group(1))

        # Weight - convert to kg
        weight_match = re.search(r'Weight:\s*(\d+)\s*(?:lbs?|pounds?)?', text, re.IGNORECASE)
        if weight_match:
            lbs = int(weight_match.group(1))
            kg = round(lbs * 0.453592)
            profile['weight'] = f"{kg} kg"

        # Hair color
        hair_match = re.search(r'Hair\s+(?:color|colour)(?:\s+is|[:\s]+)\s*([A-Za-z\s/]+?)(?:Eye|GF|PSE|MASSAGE|INCALL|OUTCALL|Details|Height|Bust|Weight|\n|$)', text, re.IGNORECASE)
        if hair_match:
            profile['hair_color'] = hair_match.group(1).strip()

        # Eye color
        eyes_match = re.search(r'Eye(?:s)?\s*(?:color|colour)?[:\s]+\s*([A-Za-z\s/]+?)(?:Hair|GF|PSE|MASSAGE|Details|\n|$)', text, re.IGNORECASE)
        if eyes_match:
            profile['eye_color'] = eyes_match.group(1).strip()

        # Images
        images = []
        for img in soup.find_all('img', class_='p_gallery_img'):
            src = img.get('src', '')
            if src:
                filename = src.split('/')[-1] if src.startswith('http') else src
                images.append(filename)
        profile['images'] = images

        # Tags
        tags = []
        tag_keywords = ['NEW', 'BLONDE', 'BRUNETTE', 'BUSTY', 'PETITE', 'ASIAN', 'EUROPEAN', 'LATINA']
        for tag in tag_keywords:
            if tag.lower() in text.lower():
                tags.append(tag)
        profile['tags'] = tags

        return profile

    # Helper methods (simplified from original)
    def _extract_tier(self, text: str) -> str:
        tiers = ['PLATINUM VIP', 'ULTRA VIP', 'VIP', 'ELITE']
        text_upper = text.upper()
        for tier in tiers:
            if tier in text_upper:
                return self._normalize_tier(tier)
        return None

    def _normalize_tier(self, tier: str) -> str:
        tier_map = {
            'ELITE': 'Elite',
            'VIP': 'VIP',
            'ULTRA VIP': 'Ultra VIP',
            'PLATINUM VIP': 'Platinum VIP'
        }
        return tier_map.get(tier.upper(), tier.title())

    def _normalize_name(self, name: str) -> str:
        return name.strip().title()

    def _parse_listing_text(self, text: str) -> tuple:
        """Extract name and time from listing text"""
        # Remove tier markers
        clean_text = text
        for t in ['*PLATINUM VIP*', '*ULTRA VIP*', '*ELITE*', '*VIP*']:
            clean_text = clean_text.replace(t, '').strip()

        # Extract time
        time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:AM|PM)\s*-\s*\d{1,2}(?::\d{2})?\s*(?:AM|PM))', clean_text, re.IGNORECASE)

        start_time = None
        end_time = None

        if time_match:
            time_str = time_match.group(1)
            clean_text = clean_text.replace(time_str, '').strip()
            parts = time_str.split('-')
            if len(parts) == 2:
                start_time = parts[0].strip()
                end_time = parts[1].strip()

        # Clean name
        name = re.sub(r'[;,\s]+$', '', clean_text).strip()
        name = re.sub(r'\d+:?\d*\s*(?:AM|PM)\s*-?\s*$', '', name, flags=re.IGNORECASE).strip()

        return name, start_time, end_time
```

### 1.7 Create Scraper Manager

**File:** `backend/scrapers/manager.py`

```python
"""Scraper orchestration and management"""
import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from .config import SITES, get_site_config, ScraperType
from .base import BaseScraper

# Import all site scrapers
from .sites.sft import SFTScraper
# from .sites.discreet_dolls import DiscreetDollsScraper
# ... more imports as sites are implemented

# Registry of implemented scrapers
SCRAPER_REGISTRY = {
    'sft': SFTScraper,
    # 'discreet': DiscreetDollsScraper,
    # Add more as implemented
}

class ScraperManager:
    """Manages and orchestrates all scrapers"""

    def __init__(self, db_session):
        self.db = db_session
        self.results = {}

    def get_scraper(self, site_key: str) -> Optional[BaseScraper]:
        """Get scraper instance for a site"""
        if site_key not in SCRAPER_REGISTRY:
            return None

        scraper_class = SCRAPER_REGISTRY[site_key]
        return scraper_class(self.db)

    async def scrape_site(self, site_key: str) -> Dict:
        """Run scraper for a single site"""
        scraper = self.get_scraper(site_key)
        if not scraper:
            return {
                'site': site_key,
                'error': f'Scraper not implemented for {site_key}',
                'status': 'not_implemented'
            }

        try:
            result = await scraper.run()
            return {
                'site': site_key,
                'status': 'success',
                **result
            }
        except Exception as e:
            return {
                'site': site_key,
                'status': 'error',
                'error': str(e)
            }

    async def scrape_all(self, site_keys: List[str] = None) -> Dict:
        """Run all scrapers (or specified subset)"""
        if site_keys is None:
            site_keys = list(SCRAPER_REGISTRY.keys())

        results = {
            'started_at': datetime.utcnow().isoformat(),
            'sites': {}
        }

        # Group by scraper type for efficient resource usage
        for site_key in site_keys:
            result = await self.scrape_site(site_key)
            results['sites'][site_key] = result

        results['completed_at'] = datetime.utcnow().isoformat()
        results['summary'] = {
            'total': len(site_keys),
            'success': sum(1 for r in results['sites'].values() if r.get('status') == 'success'),
            'errors': sum(1 for r in results['sites'].values() if r.get('status') == 'error'),
        }

        return results

    def list_available_scrapers(self) -> Dict:
        """List all configured sites and their implementation status"""
        status = {}
        for key, config in SITES.items():
            status[key] = {
                'name': config.name,
                'short_name': config.short_name,
                'scraper_type': config.scraper_type.value,
                'implemented': key in SCRAPER_REGISTRY,
                'enabled': config.enabled,
            }
        return status
```

---

## Phase 2: Easy Sites

Implement scrapers for static HTML sites (in order):

### 2.1 SexyFriendsToronto (SFT) - Already Done in Phase 1

### 2.2 SecretEscorts (SECRET)
- **URL:** https://secretescorts.ca/availability/
- **Structure:** h2 headers for days, anchor tags for listings
- **Notes:** Cookie-based age gate

### 2.3 SelectCompanyEscorts (SELECT)
- **URL:** https://www.selectcompanyescorts.com/schedule/
- **Structure:** HTML table with days as columns
- **Notes:** Pure static, no JS needed

### 2.4 AllegraEscortsCollective (ALLEGRA)
- **URL:** https://allegraescortscollective.com/schedule-booking-rates/
- **Structure:** TablePress/DataTables grid
- **Notes:** Location codes (DT, NY, ETB)

### 2.5 HighSocietyGirls (HSG)
- **URL:** https://highsocietygirls.ca/
- **Structure:** WooCommerce product grid
- **Notes:** No schedule page, just profiles

### 2.6 GardenOfEdenEscorts (EDEN)
- **URL:** https://gardenofedenescorts.com/schedule/
- **Structure:** Tab-based days, static HTML
- **Notes:** JS tabs but content in DOM

### 2.7 CupidsEscorts (CUPIDS)
- **URL:** https://www.cupidsescorts.ca/schedule/
- **Structure:** Date-indexed table grid
- **Notes:** Honeypot form field (ignore)

---

## Phase 3: Medium Sites

Implement scrapers for JavaScript-rendered sites:

### 3.1 MirageEntertainment (MIRAGE)
- **URL:** https://mirage-entertainment.cc/toronto-escorts-schedule/
- **Rendering:** jQuery day filters, card flip animations
- **Wait For:** `.day-section` elements

### 3.2 TopDrawerLadies (TDL)
- **URL:** https://www.topdrawerladies.com/pages/schedule
- **Rendering:** Infinite scroll, class-based filters
- **Wait For:** `li.monday` etc.

### 3.3 HotPinkList (HPL)
- **URL:** https://hotpinklist.com/schedule/
- **Rendering:** WordPress/Astra templates
- **Wait For:** Content load

### 3.4 TorontoPassions (PASSIONS)
- **URL:** https://www.torontopassions.com/toronto-escorts-availability
- **Rendering:** Elementor + AJAX filters
- **Wait For:** `.staff-schedule` elements

---

## Phase 4: Hard Sites

Implement scrapers for anti-bot protected sites:

### 4.1 DiscreetDolls (DD)
- **URL:** https://discreetdolls.com/daily-schedule/
- **Protection:** Active bot blocking (403 on regular requests)
- **Strategy:** Camoufox with fingerprint spoofing
- **Rate Limit:** 3+ seconds between requests

### 4.2 HiddenGemEscorts (HGE)
- **URL:** https://hiddengemescorts.ca/toronto-escorts-schedule/
- **Protection:** reCAPTCHA v3 + age gate popup
- **Strategy:** Camoufox + human simulation
- **Data:** JSON in `var app` object

### 4.3 TorontoGirlfriends (TGF)
- **URL:** https://torontogirlfriends.com/schedule/
- **Protection:** Vue.js + reCAPTCHA + CSRF
- **Strategy:** Camoufox + AJAX interception
- **Data:** Loaded via Jet Engine AJAX

---

## Phase 5: Docker & Deployment

### 5.1 Create Docker Files

**File:** `Dockerfile`
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    wget curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ /app/
COPY frontend/ /app/frontend/

EXPOSE 8000 8080

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**File:** `Dockerfile.scraper`
```dockerfile
FROM python:3.11-slim

# System deps for Camoufox
RUN apt-get update && apt-get install -y \
    wget xvfb libgtk-3-0 libdbus-glib-1-2 \
    libxt6 libx11-xcb1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir crawlee[playwright] camoufox[geoip]
RUN playwright install chromium firefox

COPY backend/ /app/

# Virtual display for headless Camoufox
CMD ["xvfb-run", "--auto-servernum", "python", "worker.py"]
```

**File:** `docker-compose.yml`
```yaml
version: '3.8'

services:
  backend:
    build: .
    ports:
      - "8000:8000"
      - "8080:8080"
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=postgresql://esearch:password@db:5432/esearch
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    restart: unless-stopped

  scraper:
    build:
      context: .
      dockerfile: Dockerfile.scraper
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=postgresql://esearch:password@db:5432/esearch
      - REDIS_URL=redis://redis:6379
    depends_on:
      - db
      - redis
    shm_size: '2gb'
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_USER=esearch
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=esearch
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

### 5.2 Database Migration

Create script to migrate from SQLite to PostgreSQL.

### 5.3 Scheduler Setup

Configure APScheduler or cron for automated daily scrapes.

---

## Phase 6: Cloud Migration (Optional)

### 6.1 Apify Deployment
- Push code to GitHub
- Connect to Apify
- Configure Actor

### 6.2 Alternative: DigitalOcean/AWS
- Use Docker Compose on a VPS
- Configure domain/SSL

---

## Testing Strategy

### Unit Tests
- Test each scraper's parse methods
- Test data normalization
- Test database operations

### Integration Tests
- Test full scrape cycle per site
- Test API endpoints
- Test frontend integration

### Manual Verification
- Compare scraped data with website
- Verify all fields populated
- Check image URLs work

---

## Rollback Plan

1. **Keep old scraper:** Don't delete `api/scraper.py`
2. **Feature flag:** Add `USE_NEW_SCRAPER` env variable
3. **Database backup:** Before any migration
4. **Git branches:** Each phase in separate commits

---

## Checklist

### Phase 1: Foundation
- [ ] Install new dependencies
- [ ] Create folder structure
- [ ] Create base classes
- [ ] Create site configurations
- [ ] Create crawler wrappers
- [ ] Migrate SFT scraper
- [ ] Create scraper manager
- [ ] Test SFT with new system

### Phase 2: Easy Sites
- [ ] SECRET scraper
- [ ] SELECT scraper
- [ ] ALLEGRA scraper
- [ ] HSG scraper
- [ ] EDEN scraper
- [ ] CUPIDS scraper

### Phase 3: Medium Sites
- [ ] MIRAGE scraper
- [ ] TDL scraper
- [ ] HPL scraper
- [ ] PASSIONS scraper

### Phase 4: Hard Sites
- [ ] DD scraper
- [ ] HGE scraper
- [ ] TGF scraper

### Phase 5: Docker
- [ ] Create Dockerfiles
- [ ] Create docker-compose.yml
- [ ] Database migration script
- [ ] Scheduler setup
- [ ] Test on NAS/network PC

### Phase 6: Cloud (Optional)
- [ ] Apify setup
- [ ] Or VPS deployment

---

## Next Steps

1. **Start Phase 1:** Run `pip install crawlee[playwright] camoufox[geoip]`
2. **Create folder structure:** Set up `backend/scrapers/`
3. **Implement base classes:** Copy code from this document
4. **Test SFT migration:** Verify it works before proceeding
