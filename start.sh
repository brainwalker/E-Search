#!/bin/bash

# E-Search Complete Startup Script
# Starts backend and frontend from any state

echo "======================================"
echo "   E-Search - Starting Application"
echo "======================================"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Kill any existing backend processes
echo "🔄 Stopping existing processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
pkill -f "uvicorn api.main:app" 2>/dev/null
lsof -ti:5500 | xargs kill -9 2>/dev/null
sleep 1

# Navigate to backend directory
cd "$SCRIPT_DIR/backend"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies if needed
echo "Checking dependencies..."
pip install -q -r requirements.txt

# Start backend server with reload
echo ""
echo "Starting backend server..."
echo "API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload > /tmp/esearch-backend.log 2>&1 &
BACKEND_PID=$!

# Wait for server to start
sleep 3

# Start frontend server
echo "Starting frontend server..."
cd "$SCRIPT_DIR/frontend"

# Try to use http-server or python
if command -v http-server &> /dev/null; then
    http-server -p 5500 -o > /tmp/esearch-frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "Frontend: http://localhost:5500 (http-server)"
elif command -v python3 &> /dev/null; then
    python3 -m http.server 5500 > /tmp/esearch-frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "Frontend: http://localhost:5500 (python http.server)"
    sleep 2
    open http://localhost:5500
else
    echo "⚠️  No web server found, opening index.html directly"
    open index.html
fi

echo ""
echo "======================================"
echo "   Application Started Successfully!"
echo "======================================"
echo ""
echo "Backend PID: $BACKEND_PID"
[ -n "$FRONTEND_PID" ] && echo "Frontend PID: $FRONTEND_PID"
echo ""
echo "📝 Logs:"
echo "   Backend:  tail -f /tmp/esearch-backend.log"
[ -n "$FRONTEND_PID" ] && echo "   Frontend: tail -f /tmp/esearch-frontend.log"
echo ""
echo "🛑 To stop:"
echo "   pkill -f 'uvicorn api.main:app'"
echo "   lsof -ti:5500 | xargs kill -9"
echo ""
echo "Press Ctrl+C to exit (servers will continue running)"
echo ""

# Keep script running to show it's active
tail -f /tmp/esearch-backend.log
