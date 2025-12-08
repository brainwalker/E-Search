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
    venv_dir = backend_dir / '.venv'
    venv_bin = venv_dir / 'bin'
    
    # Try to find Python executable in venv (could be python, python3, or python3.x)
    venv_python = None
    if venv_bin.exists():
        for python_name in ['python', 'python3', f'python{sys.version_info.major}', f'python{sys.version_info.major}.{sys.version_info.minor}']:
            candidate = venv_bin / python_name
            if candidate.exists():
                # Verify the Python actually works (not a broken symlink)
                try:
                    result = subprocess.run(
                        [str(candidate), '--version'],
                        capture_output=True,
                        timeout=2
                    )
                    if result.returncode == 0:
                        venv_python = candidate
                        break
                except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                    # Broken symlink or non-executable, skip it
                    continue

    if not venv_python or not venv_python.exists():
        print("Virtual environment not found or broken. Creating...")
        
        # Remove broken venv if it exists
        if venv_dir.exists():
            print("Removing existing virtual environment...")
            import shutil
            try:
                shutil.rmtree(venv_dir)
                time.sleep(0.5)  # Brief pause after removal
            except Exception as e:
                print(f"⚠️  Warning: Could not remove existing venv: {e}")
                print("   Attempting to continue anyway...")
        
        # Create venv with better error handling
        print(f"Creating virtual environment with {sys.executable}...")
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'venv', str(venv_dir)],
                check=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            print("✅ Virtual environment created successfully")
        except subprocess.TimeoutExpired:
            print("❌ Error: Virtual environment creation timed out")
            return None
        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating virtual environment:")
            print(f"   Command: {' '.join(e.cmd)}")
            print(f"   Return code: {e.returncode}")
            if e.stdout:
                print(f"   stdout: {e.stdout}")
            if e.stderr:
                print(f"   stderr: {e.stderr}")
            print("\n💡 Try creating the venv manually:")
            print(f"   cd {backend_dir}")
            print(f"   {sys.executable} -m venv .venv")
            print(f"   .venv/bin/pip install -r requirements.txt")
            return None
        except Exception as e:
            print(f"❌ Unexpected error creating virtual environment: {e}")
            return None
        
        # Wait a moment for venv to be fully created
        time.sleep(2)
        
        # Find the Python executable again
        for python_name in ['python', 'python3', f'python{sys.version_info.major}', f'python{sys.version_info.major}.{sys.version_info.minor}']:
            candidate = venv_bin / python_name
            if candidate.exists():
                venv_python = candidate
                break
        
        if not venv_python or not venv_python.exists():
            print("❌ Error: Could not find Python executable in virtual environment")
            print(f"   Looking in: {venv_bin}")
            print(f"   Available files: {list(venv_bin.iterdir()) if venv_bin.exists() else 'Directory does not exist'}")
            return None

        print("Installing dependencies...")
        try:
            subprocess.run(
                [str(venv_python), '-m', 'pip', 'install', '-q', '-r', str(backend_dir / 'requirements.txt')],
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"❌ Error installing dependencies: {e}")
            return None

    # Verify venv_python exists before starting
    if not venv_python or not venv_python.exists():
        print("❌ Error: Python executable not found in virtual environment")
        return None
    
    # Start uvicorn
    print(f"Starting backend with: {venv_python}")
    process = subprocess.Popen(
        [str(venv_python), '-m', 'uvicorn', 'api.main:app', '--host', '0.0.0.0', '--port', '8000', '--reload'],
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
    frontend_dir_abs = str(frontend_dir.absolute())
    
    class FrontendHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            # Python 3.7+ supports directory parameter - use it directly
            super().__init__(*args, directory=frontend_dir_abs, **kwargs)
        
        def log_message(self, format, *args):
            pass  # Suppress logs
        
        def end_headers(self):
            # Add CORS headers
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            super().end_headers()

    server = HTTPServer(('localhost', 8080), FrontendHandler)

    def run_server():
        print("✅ Frontend server started on http://localhost:8080")
        print(f"   Serving from: {frontend_dir}")
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
