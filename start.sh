#!/bin/bash

# E-Search Complete Startup Script

echo "======================================"
echo "   E-Search - Starting Application"
echo "======================================"
echo ""

# Navigate to backend directory
cd backend

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

# Start backend server
echo ""
echo "Starting backend server..."
echo "API: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo ""
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 > /dev/null 2>&1 &
BACKEND_PID=$!

# Wait for server to start
sleep 3

# Open frontend
echo "Opening frontend in browser..."
cd ../frontend
open index.html

echo ""
echo "======================================"
echo "   Application Started Successfully!"
echo "======================================"
echo ""
echo "Backend PID: $BACKEND_PID"
echo "To stop the backend: kill $BACKEND_PID"
echo ""
echo "Press Ctrl+C to stop monitoring (backend will continue running)"
echo ""

# Keep script running
wait
