#!/usr/bin/env python3
"""
E-Search Auto-Start Server
This script automatically starts the backend and serves the frontend
"""

import subprocess
import sys
import time
import webbrowser
import os
from pathlib import Path

def check_backend_running():
    """Check if backend is already running"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', 8000))
    sock.close()
    return result == 0

def start_backend():
    """Start the FastAPI backend"""
    print("Starting backend server...")

    backend_dir = Path(__file__).parent / 'backend'
    venv_python = backend_dir / '.venv' / 'bin' / 'python'

    if not venv_python.exists():
        print("Virtual environment not found. Creating...")
        subprocess.run([sys.executable, '-m', 'venv', str(backend_dir / '.venv')])

        print("Installing dependencies...")
        subprocess.run([str(venv_python), '-m', 'pip', 'install', '-q', '-r', str(backend_dir / 'requirements.txt')])

    # Start uvicorn
    process = subprocess.Popen(
        [str(venv_python), '-m', 'uvicorn', 'api.main:app', '--host', '0.0.0.0', '--port', '8000'],
        cwd=str(backend_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to start
    print("Waiting for backend to start...")
    for i in range(30):
        if check_backend_running():
            print("✅ Backend started successfully!")
            return process
        time.sleep(0.5)

    print("❌ Backend failed to start")
    return None

def serve_frontend():
    """Start a simple HTTP server for the frontend"""
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import threading

    frontend_dir = Path(__file__).parent / 'frontend'
    os.chdir(frontend_dir)

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Suppress logs

    server = HTTPServer(('localhost', 8080), Handler)

    def run_server():
        print("✅ Frontend server started on http://localhost:8080")
        server.serve_forever()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    return server

def main():
    print("=" * 50)
    print("  E-Search - Auto-Start Server")
    print("=" * 50)
    print()

    # Check if backend is already running
    if check_backend_running():
        print("✅ Backend already running on http://localhost:8000")
    else:
        backend_process = start_backend()
        if not backend_process:
            print("\nFailed to start backend. Please check logs.")
            return

    # Start frontend server
    frontend_server = serve_frontend()

    print()
    print("=" * 50)
    print("  Application Ready!")
    print("=" * 50)
    print()
    print("  Backend API: http://localhost:8000")
    print("  Frontend UI: http://localhost:8080")
    print("  API Docs:    http://localhost:8000/docs")
    print()
    print("  Opening browser in 2 seconds...")
    print()
    print("  Press Ctrl+C to stop all servers")
    print("=" * 50)

    # Open browser
    time.sleep(2)
    webbrowser.open('http://localhost:8080')

    try:
        # Keep running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down servers...")
        frontend_server.shutdown()
        print("✅ All servers stopped")

if __name__ == '__main__':
    main()
