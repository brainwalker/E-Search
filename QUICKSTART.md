# E-Search - Quick Start Guide

## Instant Setup (macOS/Linux)

### ⚡ Option 1: Auto-Start Everything (RECOMMENDED)
```bash
cd /Users/shah/E-Search
python3 serve.py
```

This will:
- ✅ Auto-start the backend API
- ✅ Serve the frontend on port 8080
- ✅ Open your browser automatically
- ✅ Detect if backend is already running
- ✅ Install dependencies if needed

**Press `Ctrl+C` to stop all servers**

### Option 2: Bash Script (Backend only)
```bash
cd /Users/shah/E-Search
./start.sh
```

This will:
- Set up the virtual environment (if needed)
- Install dependencies
- Start the backend API
- Open the frontend in your browser

### Option 3: Manual Start

#### 1. Start Backend
```bash
cd /Users/shah/E-Search/backend
./run.sh
```

#### 2. Open Frontend
Simply open `frontend/index.html` in your browser:
```bash
open /Users/shah/E-Search/frontend/index.html
```

**Note:** The frontend now auto-detects if the backend is offline and shows helpful instructions!

## Windows Users

```cmd
cd \Users\shah\E-Search\backend
run.bat
```

Then open `frontend\index.html` in your browser.

## First Time Usage

### 1. Start the Application
Use one of the methods above to start the backend and open the frontend.

### 2. Scrape Data
- Click the **"Scrape All Sources"** button in the UI
- Wait 30-60 seconds for the scraping to complete
- You'll see a success notification when done

### 3. Browse Listings
- The listings will automatically load and display
- You should see 100+ listings from SexyFriendsToronto

## Using the Filters

### Source Selection
- All sources are selected by default
- Uncheck sources you want to exclude

### Day of Week Filter
- Check specific days to see only listings available on those days
- Leave all unchecked to see listings for all days

### Hide Expired Listings
- Check this box to hide listings that are no longer active

### Search by Name
- Type a name in the search box
- Example: "Polina", "Angelina", etc.

### Filter by Tier
- Select from dropdown: VIP, Platinum VIP, Ultra VIP, or Elite
- Leave as "All Tiers" to see everyone

### Filter by Nationality
- Type a nationality: "Latina", "Asian", "European", etc.

### Filter by Hair Color
- Type hair color: "Blonde", "Brunette", "Black", etc.

### Apply Filters
- Click **"Apply Filters"** to refresh with your filter settings
- Click **"Clear All"** to reset all filters

## Features Overview

### Listing Cards Show:
- ✓ Name and Tier (VIP, Platinum VIP, etc.)
- ✓ Profile images (up to 5 thumbnails)
- ✓ Personal details (age, nationality, height, measurements, etc.)
- ✓ Rates (Incall/Outcall for different durations)
- ✓ Schedule (availability by day and location)
- ✓ Tags (NEW, BLONDE, BUSTY, etc.)
- ✓ "View Full Profile" button (opens original profile page)

### Statistics Dashboard
At the top you'll see:
- Total Listings count
- Active Listings count
- Number of Sources configured

## API Access

The backend API is available at: `http://localhost:8000`

### API Documentation
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Common Endpoints
```bash
# Get all listings
curl http://localhost:8000/api/listings

# Get stats
curl http://localhost:8000/api/stats

# Scrape all sources
curl -X POST http://localhost:8000/api/scrape-all

# Filter listings by day
curl "http://localhost:8000/api/listings?days_of_week=Friday,Saturday"

# Search by name
curl "http://localhost:8000/api/listings?search=Polina"

# Filter by tier
curl "http://localhost:8000/api/listings?tier=PLATINUM%20VIP"

# Hide expired
curl "http://localhost:8000/api/listings?hide_expired=true"
```

## Database Location

SQLite database is created at:
```
/Users/shah/E-Search/backend/escort_listings.db
```

You can view it with any SQLite browser tool.

## Troubleshooting

### Backend won't start
```bash
# Make sure port 8000 is not in use
lsof -i :8000
# If something is using it:
kill <PID>
```

### No listings showing
1. Make sure backend is running (`http://localhost:8000` should return JSON)
2. Click "Scrape All Sources" button
3. Check browser console for errors (F12)

### CORS errors in browser
- Make sure you're accessing the frontend via `file://` protocol or a local server
- Backend must be running on `http://localhost:8000`

### Scraping returns 0 listings
- Check your internet connection
- The website might be temporarily down
- Try again in a few minutes

## Stopping the Application

### Stop Backend
```bash
# Find the process
ps aux | grep uvicorn

# Kill it
pkill -f uvicorn
```

Or use the PID shown when you started with `./start.sh`

## Performance Notes

- First scrape takes 30-60 seconds (depending on internet speed)
- Subsequent scrapes are faster (only updates changed listings)
- Profile details are only scraped for new listings (to be respectful)
- 100+ listings load instantly in the UI
- Filtering is real-time

## Next Steps

1. **Add More Sources**: Edit `backend/api/scraper.py` to add scrapers for other websites
2. **Schedule Automatic Scraping**: Set up a cron job to run scraping periodically
3. **Deploy Online**: Use services like Heroku, Railway, or DigitalOcean
4. **Customize UI**: Edit `frontend/index.html` styles and layout

## Need Help?

Check the main `README.md` for:
- Complete API documentation
- Database schema details
- How to add new sources
- Deployment instructions
- Architecture overview

---

**Built with**: Python, FastAPI, SQLAlchemy, BeautifulSoup4, Vanilla JS
