#!/usr/bin/env python3
"""
E-Search Auto-Start Server
This script automatically starts the backend and serves the frontend.
Also watches for .restart_flag to auto-restart the backend.
"""

import subprocess
import sys
import time
import webbrowser
import os
from pathlib import Path
import threading
import signal

# Global reference to backend process for restart
backend_process = None
backend_lock = threading.Lock()
shutdown_event = threading.Event()


def check_backend_running():
    """Check if backend is already running"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', 8000))
    sock.close()
    return result == 0


def get_venv_python():
    """Find the Python executable in the virtual environment"""
    backend_dir = Path(__file__).parent / 'backend'
    venv_dir = backend_dir / '.venv'
    venv_bin = venv_dir / 'bin'

    if not venv_bin.exists():
        return None, backend_dir, venv_dir

    for python_name in ['python', 'python3', f'python{sys.version_info.major}', f'python{sys.version_info.major}.{sys.version_info.minor}']:
        candidate = venv_bin / python_name
        if candidate.exists():
            try:
                result = subprocess.run(
                    [str(candidate), '--version'],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode == 0:
                    return candidate, backend_dir, venv_dir
            except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
                continue

    return None, backend_dir, venv_dir


def start_backend():
    """Start the FastAPI backend"""
    global backend_process

    print("Starting backend server...")

    venv_python, backend_dir, venv_dir = get_venv_python()

    if not venv_python:
        print("Virtual environment not found or broken. Creating...")

        # Remove broken venv if it exists
        if venv_dir.exists():
            print("Removing existing virtual environment...")
            import shutil
            try:
                shutil.rmtree(venv_dir)
                time.sleep(0.5)
            except Exception as e:
                print(f"⚠️  Warning: Could not remove existing venv: {e}")
                print("   Attempting to continue anyway...")

        # Create venv
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

        time.sleep(2)
        venv_python, _, _ = get_venv_python()

        if not venv_python:
            print("❌ Error: Could not find Python executable in virtual environment")
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

    # Start uvicorn
    print(f"Starting backend with: {venv_python}")
    with backend_lock:
        backend_process = subprocess.Popen(
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
            return backend_process
        time.sleep(0.5)

    print("❌ Backend failed to start")
    return None


def stop_backend():
    """Stop the backend process"""
    global backend_process

    with backend_lock:
        if backend_process:
            print("🔄 Stopping backend...")
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                backend_process.kill()
            backend_process = None

            # Wait for port to be released
            for _ in range(10):
                if not check_backend_running():
                    break
                time.sleep(0.5)


def restart_backend():
    """Restart the backend server"""
    print("\n🔄 Restarting backend...")
    stop_backend()
    time.sleep(1)
    start_backend()
    print("✅ Backend restarted!")


def watch_restart_flag():
    """Watch for .restart_flag file and restart backend when it appears"""
    restart_flag = Path(__file__).parent / 'backend' / '.restart_flag'
    last_mtime = None

    # Remove any existing flag on startup
    if restart_flag.exists():
        restart_flag.unlink()

    while not shutdown_event.is_set():
        try:
            if restart_flag.exists():
                current_mtime = restart_flag.stat().st_mtime

                # Check if this is a new flag or updated flag
                if last_mtime is None or current_mtime > last_mtime:
                    last_mtime = current_mtime

                    # Remove the flag file
                    try:
                        restart_flag.unlink()
                    except:
                        pass

                    # Restart the backend
                    restart_backend()

            time.sleep(1)
        except Exception as e:
            print(f"⚠️  Restart watcher error: {e}")
            time.sleep(1)


def serve_frontend():
    """Start a simple HTTP server for the frontend"""
    from http.server import HTTPServer, SimpleHTTPRequestHandler

    frontend_dir = Path(__file__).parent / 'frontend'
    frontend_dir_abs = str(frontend_dir.absolute())

    class FrontendHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=frontend_dir_abs, **kwargs)

        def log_message(self, format, *args):
            pass  # Suppress logs

        def end_headers(self):
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
        if not start_backend():
            print("\nFailed to start backend. Please check logs.")
            return

    # Start frontend server
    frontend_server = serve_frontend()

    # Start restart flag watcher
    watcher_thread = threading.Thread(target=watch_restart_flag, daemon=True)
    watcher_thread.start()

    print()
    print("=" * 50)
    print("  Application Ready!")
    print("=" * 50)
    print()
    print("  Backend API: http://localhost:8000")
    print("  Frontend UI: http://localhost:8080")
    print("  API Docs:    http://localhost:8000/docs")
    print()
    print("  Auto-restart: Watching for .restart_flag")
    print("  Opening browser in 2 seconds...")
    print()
    print("  Press Ctrl+C to stop all servers")
    print("=" * 50)

    # Open browser
    time.sleep(2)
    webbrowser.open('http://localhost:8080')

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\nShutting down servers...")
        shutdown_event.set()
        stop_backend()
        frontend_server.shutdown()
        print("✅ All servers stopped")


if __name__ == '__main__':
    main()
