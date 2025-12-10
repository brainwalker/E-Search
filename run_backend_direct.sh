#!/bin/bash
# Run backend directly to see logs in terminal

cd /Users/shah/E-Search/backend

# Activate virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
else
    echo "Virtual environment not found. Run: python3 -m venv .venv"
    exit 1
fi

# Run uvicorn with logs visible
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
