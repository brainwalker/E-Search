# Site Implementation Checklist

## Overview

This checklist tracks the implementation progress for each of the 14 escort listing sources. Use this document to track what's done and what's next.

**Last Updated:** December 8, 2025
**Branch:** `Crawl4AI`

---

## Implementation Order

Sites are implemented in this order based on difficulty and priority:

1. **Phase 1: Foundation** - Set up infrastructure
2. **Phase 2: Easy Sites** - Static HTML (7 sites)
3. **Phase 3: Medium Sites** - JavaScript rendering (4 sites)
4. **Phase 4: Hard Sites** - Stealth/anti-bot (3 sites)

---

## Phase 1: Foundation

### Infrastructure Setup

- [ ] Install Crawlee and dependencies
  ```bash
  pip install crawlee[playwright] camoufox[geoip] browserforge redis rq
  ```
- [ ] Install Playwright browsers
  ```bash
  playwright install chromium firefox
  ```
- [ ] Download Camoufox browser
  ```bash
  python -c "from camoufox.sync_api import Camoufox; Camoufox(headless=True)"
  ```
- [ ] Create folder structure (`backend/scrapers/`)
- [ ] Create `base.py` - BaseScraper abstract class
- [ ] Create `config.py` - All 14 site configurations
- [ ] Create `manager.py` - ScraperManager
- [ ] Create `crawlers/static.py` - BeautifulSoupCrawler wrapper
- [ ] Create `crawlers/javascript.py` - PlaywrightCrawler wrapper
- [ ] Create `crawlers/stealth.py` - Camoufox wrapper
- [ ] Create `utils/extractors.py` - Common extraction helpers
- [ ] Create `utils/normalizers.py` - Data normalization
- [ ] Test infrastructure with SFT site

---

## Phase 2: Easy Sites (Static HTML)

### Site 1: SexyFriendsToronto (SFT) ✅ CURRENT
- **URL:** https://www.sexyfriendstoronto.com/toronto-escorts/schedule
- **Type:** Static HTML
- **Status:** Working (migrate to new system)

#### Checklist
- [ ] Create `sites/sft.py`
- [ ] Migrate schedule parsing logic
- [ ] Migrate profile parsing logic
- [ ] Test schedule scraping
- [ ] Test profile scraping
- [ ] Verify data matches current scraper
- [ ] Update API to use new scraper

---

### Site 2: SecretEscorts (SECRET)
- **URL:** https://secretescorts.ca/availability/
- **Type:** Static HTML
- **Notes:** Cookie-based age gate

#### Checklist
- [ ] Analyze page structure
- [ ] Create `sites/secret.py`
- [ ] Implement schedule parser
- [ ] Implement profile parser
- [ ] Handle age gate cookie
- [ ] Add to database (Source, Locations)
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

### Site 3: SelectCompanyEscorts (SELECT)
- **URL:** https://www.selectcompanyescorts.com/schedule/
- **Type:** Static HTML (table)
- **Notes:** HTML table with days as columns

#### Checklist
- [ ] Analyze page structure
- [ ] Create `sites/select_company.py`
- [ ] Implement table parser
- [ ] Implement profile parser
- [ ] Add to database
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

### Site 4: AllegraEscortsCollective (ALLEGRA)
- **URL:** https://allegraescortscollective.com/schedule-booking-rates/
- **Type:** Static HTML (DataTables)
- **Notes:** Location codes (DT=Downtown, NY=North York, ETB=Etobicoke)

#### Checklist
- [ ] Analyze page structure
- [ ] Create `sites/allegra.py`
- [ ] Implement table parser
- [ ] Map location codes
- [ ] Implement profile parser
- [ ] Add to database
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

### Site 5: HighSocietyGirls (HSG)
- **URL:** https://highsocietygirls.ca/
- **Type:** Static HTML (WooCommerce)
- **Notes:** No schedule page, just profiles

#### Checklist
- [ ] Analyze page structure
- [ ] Create `sites/high_society.py`
- [ ] Implement listing page parser
- [ ] Implement profile parser
- [ ] Determine availability handling
- [ ] Add to database
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

### Site 6: GardenOfEdenEscorts (EDEN)
- **URL:** https://gardenofedenescorts.com/schedule/
- **Type:** Static HTML (JS tabs)
- **Notes:** Tab-based days, content in DOM

#### Checklist
- [ ] Analyze page structure
- [ ] Create `sites/garden_eden.py`
- [ ] Implement tab content parser
- [ ] Implement profile parser
- [ ] Add to database
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

### Site 7: CupidsEscorts (CUPIDS)
- **URL:** https://www.cupidsescorts.ca/schedule/
- **Type:** Static HTML (table)
- **Notes:** Date-indexed grid, honeypot form

#### Checklist
- [ ] Analyze page structure
- [ ] Create `sites/cupids.py`
- [ ] Implement table parser
- [ ] Implement profile parser
- [ ] Add to database
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

## Phase 3: Medium Sites (JavaScript Rendering)

### Site 8: MirageEntertainment (MIRAGE)
- **URL:** https://mirage-entertainment.cc/toronto-escorts-schedule/
- **Type:** JavaScript (jQuery)
- **Notes:** Day filters, card flip animations

#### Checklist
- [ ] Analyze page structure with browser
- [ ] Create `sites/mirage.py`
- [ ] Use PlaywrightCrawler
- [ ] Wait for `.day-section` elements
- [ ] Implement schedule parser
- [ ] Implement profile parser
- [ ] Add to database
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

### Site 9: TopDrawerLadies (TDL)
- **URL:** https://www.topdrawerladies.com/pages/schedule
- **Type:** JavaScript (infinite scroll)
- **Notes:** Class-based filters

#### Checklist
- [ ] Analyze page structure with browser
- [ ] Create `sites/topdrawer.py`
- [ ] Use PlaywrightCrawler
- [ ] Handle infinite scroll
- [ ] Wait for `li.monday` etc.
- [ ] Implement schedule parser
- [ ] Implement profile parser
- [ ] Add to database
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

### Site 10: HotPinkList (HPL)
- **URL:** https://hotpinklist.com/schedule/
- **Type:** JavaScript (WordPress/Astra)
- **Notes:** Content loads via templates

#### Checklist
- [ ] Analyze page structure with browser
- [ ] Create `sites/hotpink.py`
- [ ] Use PlaywrightCrawler
- [ ] Wait for content load
- [ ] Implement schedule parser
- [ ] Implement profile parser
- [ ] Add to database
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

### Site 11: TorontoPassions (PASSIONS)
- **URL:** https://www.torontopassions.com/toronto-escorts-availability
- **Type:** JavaScript (Elementor + AJAX)
- **Notes:** AJAX filters for schedule

#### Checklist
- [ ] Analyze page structure with browser
- [ ] Create `sites/toronto_passions.py`
- [ ] Use PlaywrightCrawler
- [ ] Wait for `.staff-schedule` elements
- [ ] Handle AJAX filter interactions
- [ ] Implement schedule parser
- [ ] Implement profile parser
- [ ] Add to database
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

## Phase 4: Hard Sites (Stealth Required)

### Site 12: DiscreetDolls (DD)
- **URL:** https://discreetdolls.com/daily-schedule/
- **Type:** Stealth (bot blocking)
- **Notes:** Returns 403 on regular requests

#### Checklist
- [ ] Test with Camoufox
- [ ] Create `sites/discreet_dolls.py`
- [ ] Use StealthCrawler
- [ ] Configure fingerprint spoofing
- [ ] Set 3+ second rate limit
- [ ] Implement schedule parser
- [ ] Implement profile parser
- [ ] Add to database
- [ ] Test full scrape cycle (carefully!)
- [ ] Add to API sources

---

### Site 13: HiddenGemEscorts (HGE)
- **URL:** https://hiddengemescorts.ca/toronto-escorts-schedule/
- **Type:** Stealth (reCAPTCHA v3)
- **Notes:** Age gate popup, data in `var app` JSON

#### Checklist
- [ ] Test with Camoufox
- [ ] Create `sites/hidden_gem.py`
- [ ] Use StealthCrawler
- [ ] Handle age gate popup
- [ ] Extract JSON from `var app`
- [ ] Implement schedule parser
- [ ] Implement profile parser
- [ ] Add to database
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

### Site 14: TorontoGirlfriends (TGF)
- **URL:** https://torontogirlfriends.com/schedule/
- **Type:** Stealth (Vue + reCAPTCHA + CSRF)
- **Notes:** Data via Jet Engine AJAX

#### Checklist
- [ ] Test with Camoufox
- [ ] Create `sites/toronto_gf.py`
- [ ] Use StealthCrawler
- [ ] Handle AJAX data loading
- [ ] Extract from Jet Engine response
- [ ] Implement schedule parser
- [ ] Implement profile parser
- [ ] Add to database
- [ ] Test full scrape cycle
- [ ] Add to API sources

---

## Phase 5: Docker & Deployment

### Docker Setup

- [ ] Create `Dockerfile` for backend
- [ ] Create `Dockerfile.scraper` for worker
- [ ] Create `docker-compose.yml`
- [ ] Test containers locally
- [ ] Configure PostgreSQL
- [ ] Configure Redis
- [ ] Database migration script
- [ ] Test full stack in Docker

### Scheduler Setup

- [ ] Configure APScheduler or cron
- [ ] Set daily scrape times
- [ ] Configure per-site schedules
- [ ] Add monitoring/alerts

### Deployment

- [ ] Deploy to NAS/network PC
- [ ] Configure auto-restart
- [ ] Set up log rotation
- [ ] Monitor resource usage

---

## Progress Summary

| Phase | Total | Done | Remaining |
|-------|-------|------|-----------|
| Phase 1: Foundation | 12 | 0 | 12 |
| Phase 2: Easy Sites | 7 | 0 | 7 |
| Phase 3: Medium Sites | 4 | 0 | 4 |
| Phase 4: Hard Sites | 3 | 0 | 3 |
| Phase 5: Docker | 10 | 0 | 10 |
| **Total** | **36** | **0** | **36** |

---

## Quick Commands

### Test a scraper
```bash
cd backend
python -m scrapers.test sft
```

### Run all scrapers
```bash
cd backend
python -m scrapers.run_all
```

### Start Docker stack
```bash
docker-compose up -d
docker-compose logs -f scraper
```

### Check scraper status
```bash
curl http://localhost:8000/api/scrapers/status
```

---

## Notes

- Always test new scrapers with `rate_limit_seconds` set high (3-5s)
- Monitor for 403/429 errors - increase rate limit if needed
- Hard sites may require multiple attempts to get right
- Keep old scraper code until new system is fully tested
- Back up database before major changes
