# E-Search Quick Start Guide

## Starting the Application

### Method 1: One-Command Start (Recommended)
```bash
cd /Users/shah/E-Search
./start.sh
```

This script will:
- Kill any existing backend/frontend processes
- Start the backend on port 8000 with auto-reload
- Start the frontend on port 5500 (or open directly)
- Show logs in real-time

**Press Ctrl+C to exit** (servers will keep running in background)

### Method 2: Manual Start

#### Backend:
```bash
cd /Users/shah/E-Search/backend
lsof -ti:8000 | xargs kill -9 2>/dev/null
source .venv/bin/activate
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend:
```bash
cd /Users/shah/E-Search/frontend
lsof -ti:5500 | xargs kill -9 2>/dev/null

# Option A: Using http-server (if installed)
http-server -p 5500 -o

# Option B: Using Python
python3 -m http.server 5500

# Option C: Open directly in browser
open index.html
```

## Stopping the Application

```bash
# Stop backend
pkill -f 'uvicorn api.main:app'

# Stop frontend
lsof -ti:5500 | xargs kill -9

# Or stop both
lsof -ti:8000 | xargs kill -9
lsof -ti:5500 | xargs kill -9
```

## Accessing the Application

- **Frontend:** http://localhost:5500
- **Backend API:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

## Viewing Logs

```bash
# Backend logs
tail -f /tmp/esearch-backend.log

# Frontend logs (if using web server)
tail -f /tmp/esearch-frontend.log
```

## Troubleshooting

### Port already in use
The start.sh script automatically kills existing processes, but if needed:
```bash
# Check what's using port 8000
lsof -ti:8000

# Check what's using port 5500
lsof -ti:5500

# Kill them
lsof -ti:8000 | xargs kill -9
lsof -ti:5500 | xargs kill -9
```

### Backend won't start
```bash
cd /Users/shah/E-Search/backend
source .venv/bin/activate
pip install -r requirements.txt
```

### Frontend shows blank page
- Check browser console for errors
- Make sure backend is running: curl http://localhost:8000/health
- Try opening in a different browser
