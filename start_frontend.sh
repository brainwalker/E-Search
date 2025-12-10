#!/bin/bash
# Start frontend server on port 8080

cd /Users/shah/E-Search/frontend

echo "Starting frontend server on http://localhost:8080"
echo "Serving from: $(pwd)"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python3 -m http.server 8080
