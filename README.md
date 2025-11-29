# E-Search - Multi-Source Escort Listing Aggregator

A web application that scrapes escort listings from multiple sources, stores them in a database, and displays them in a beautiful, organized interface with powerful filtering capabilities.

## Features

- **Multi-Source Scraping**: Automatically scrape listings from multiple websites
- **Smart Data Extraction**: Extracts detailed information including:
  - Personal details (age, nationality, measurements, etc.)
  - Rates (incall/outcall, different durations)
  - Schedules (availability by day)
  - Images from profile galleries
  - Tags and tier information

- **Powerful Filtering**:
  - Filter by source
  - Filter by day of the week
  - Hide expired listings
  - Search by name
  - Filter by tier (VIP, Platinum VIP, Ultra VIP, Elite)
  - Filter by nationality, hair color
  - View detailed profiles with images

- **Beautiful UI**: Modern, responsive design with gradient backgrounds and smooth animations

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: SQL toolkit and ORM
- **SQLite**: Database (easily upgradable to PostgreSQL)
- **BeautifulSoup4**: HTML parsing for web scraping
- **httpx**: Async HTTP client

### Frontend
- **Vanilla HTML/CSS/JavaScript**: No framework dependencies
- **Modern CSS Grid & Flexbox**: Responsive layouts
- **Fetch API**: For backend communication

## Project Structure

```
E-Search/
├── backend/
│   ├── api/
│   │   ├── main.py          # FastAPI application and endpoints
│   │   ├── database.py      # Database models and configuration
│   │   └── scraper.py       # Web scraping logic
│   ├── requirements.txt     # Python dependencies
│   └── escort_listings.db   # SQLite database (created on first run)
├── frontend/
│   └── index.html          # Single-page application
└── README.md
```

## Installation

### 1. Clone the repository
```bash
cd /Users/shah/E-Search
```

### 2. Set up Python virtual environment
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

## Usage

### ⚡ Quick Start (Recommended - Auto-starts everything!)

**One command to start backend + frontend:**
```bash
python3 serve.py
```

This will:
- ✅ Auto-start the backend API on port 8000
- ✅ Serve the frontend on port 8080
- ✅ Open your browser automatically
- ✅ Handle all setup for you

Press `Ctrl+C` to stop all servers.

---

### Alternative: Manual Start

#### Option 1: Bash Script
```bash
./start.sh
```

#### Option 2: Start Backend Manually
```bash
cd backend
./run.sh
```

Then open `frontend/index.html` in your browser or:
```bash
open frontend/index.html
```

---

### 3. Initial Data Import
Click the "Scrape All Sources" button in the UI to start scraping data from all configured sources.

**Note:** The frontend now automatically detects if the backend is offline and shows helpful startup instructions.

## API Endpoints

### Sources
- `GET /api/sources` - Get all scraping sources
- `POST /api/scrape/{source_name}` - Scrape a specific source
- `POST /api/scrape-all` - Scrape all sources

### Listings
- `GET /api/listings` - Get all listings with filters
  - Query parameters:
    - `source_ids`: Comma-separated source IDs
    - `days_of_week`: Comma-separated days
    - `hide_expired`: Boolean
    - `tier`: Filter by tier
    - `nationality`: Filter by nationality
    - `hair_color`: Filter by hair color
    - `search`: Search by name
- `GET /api/listings/{id}` - Get single listing
- `DELETE /api/listings/{id}` - Delete a listing
- `PUT /api/listings/{id}/expire` - Mark as expired

### Other
- `GET /api/tags` - Get all tags
- `GET /api/stats` - Get database statistics

## Database Schema

### Tables
1. **sources** - Scraping source configurations
2. **listings** - Main listing data
3. **schedules** - Availability schedules
4. **tags** - Tags for categorization
5. **listing_tags** - Many-to-many relationship

## Adding New Sources

To add a new scraping source:

1. Create a new scraper class in `backend/api/scraper.py` following the pattern of `SexyFriendsTorontoScraper`
2. Implement the required methods:
   - `parse_schedule_page()` - Parse the listing page
   - `scrape_profile()` - Extract detailed profile data
   - `scrape_and_save()` - Main scraping logic
3. Add the new scraper to the `/api/scrape-all` endpoint in `main.py`

## Customization

### Frontend Styling
All styles are in the `<style>` section of `frontend/index.html`. Key color variables:
- Primary gradient: `#667eea` to `#764ba2`
- Success: `#10b981`
- Warning: `#ffc107`

### Database
To switch from SQLite to PostgreSQL, update the connection string in `backend/api/database.py`:
```python
engine = create_engine('postgresql://user:password@localhost/dbname', echo=False)
```

## Current Data Sources

1. **SexyFriendsToronto** (`sexyfriendstoronto.com`)
   - Schedule page scraping
   - Profile detail extraction
   - Image gallery support

## Notes

- The scraper is respectful of the target website (adds delays, uses proper user agents)
- Images are linked, not downloaded (reduces storage requirements)
- Expired listings can be hidden via filter
- All timestamps are in UTC
- The system supports adding unlimited sources

## Troubleshooting

### CORS Errors
If you see CORS errors, make sure:
1. The backend is running on `http://localhost:8000`
2. You're accessing the frontend from the same domain or using a local server

### Scraping Errors
- Check your internet connection
- Some websites may block automated requests
- Add delays between requests if needed

### Database Locked
If you get "database is locked" errors, make sure only one instance of the backend is running.

## Future Enhancements

- [ ] Add more scraping sources
- [ ] Implement automatic scheduled scraping
- [ ] Add user authentication
- [ ] Export listings to CSV/JSON
- [ ] Advanced search with multiple criteria
- [ ] Favorite/bookmark listings
- [ ] Email notifications for new listings
- [ ] Mobile app version

## License

This project is for educational purposes only. Please respect the terms of service of any websites you scrape.
