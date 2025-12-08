"""
Database Viewer Endpoints
Provides web interface to browse database tables
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from typing import Optional
from api.database import get_db, engine
import logging
from pathlib import Path
from datetime import datetime

router = APIRouter(prefix="/db", tags=["Database Viewer"])

# Setup logging directory
LOG_DIR = Path(__file__).parent.parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "backend.log"

# Configure file logging
file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Get root logger and add handler
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)
root_logger.setLevel(logging.INFO)


@router.get("/tables")
async def get_tables():
    """Get list of all tables in the database"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    table_info = []
    for table_name in tables:
        columns = inspector.get_columns(table_name)
        table_info.append({
            "name": table_name,
            "columns": [{"name": col["name"], "type": str(col["type"])} for col in columns]
        })

    return {"tables": table_info}


@router.get("/table/{table_name}")
async def get_table_data(
    table_name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Get data from a specific table with pagination"""

    # Verify table exists
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return {"error": f"Table '{table_name}' not found"}

    # Get total count
    count_query = text(f"SELECT COUNT(*) FROM {table_name}")
    total_count = db.execute(count_query).scalar()

    # Get paginated data
    offset = (page - 1) * page_size
    data_query = text(f"SELECT * FROM {table_name} LIMIT :limit OFFSET :offset")
    result = db.execute(data_query, {"limit": page_size, "offset": offset})

    # Convert to list of dicts
    columns = result.keys()
    rows = []
    for row in result:
        row_dict = {}
        for i, col in enumerate(columns):
            value = row[i]
            # Convert to string if not JSON serializable
            if isinstance(value, (bytes, bytearray)):
                value = value.decode('utf-8', errors='ignore')
            row_dict[col] = value
        rows.append(row_dict)

    return {
        "table": table_name,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size,
        "columns": list(columns),
        "data": rows
    }


@router.get("/query")
async def execute_query(
    sql: str = Query(..., description="SQL query to execute (SELECT only)"),
    db: Session = Depends(get_db)
):
    """Execute a custom SQL query (SELECT only for safety)"""

    # Only allow SELECT queries for safety
    if not sql.strip().upper().startswith('SELECT'):
        return {"error": "Only SELECT queries are allowed"}

    try:
        result = db.execute(text(sql))
        columns = result.keys()
        rows = []
        for row in result:
            row_dict = {}
            for i, col in enumerate(columns):
                value = row[i]
                if isinstance(value, (bytes, bytearray)):
                    value = value.decode('utf-8', errors='ignore')
                row_dict[col] = value
            rows.append(row_dict)

        return {
            "columns": list(columns),
            "data": rows,
            "count": len(rows)
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/stats")
async def get_db_stats(db: Session = Depends(get_db)):
    """Get database statistics"""
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    stats = {}
    for table_name in tables:
        count_query = text(f"SELECT COUNT(*) FROM {table_name}")
        count = db.execute(count_query).scalar()
        stats[table_name] = count

    # Get database file size if SQLite
    try:
        size_query = text("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        size = db.execute(size_query).scalar()
        stats["_database_size_bytes"] = size
        stats["_database_size_mb"] = round(size / (1024 * 1024), 2)
    except:
        pass

    return stats


@router.get("/logs")
async def get_logs(
    lines: int = Query(100, ge=1, le=1000, description="Number of lines to retrieve"),
    since: Optional[str] = Query(None, description="Only return logs after this timestamp (ISO format)")
):
    """Get backend logs"""
    try:
        if not LOG_FILE.exists():
            return {
                "logs": [],
                "total_lines": 0,
                "file_exists": False,
                "message": "Log file not found. Logging will start once the backend processes requests."
            }
        
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            all_lines = f.readlines()
        
        total_lines = len(all_lines)
        
        # Filter by timestamp if provided
        if since:
            try:
                since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
                filtered_lines = []
                for line in all_lines:
                    # Try to parse timestamp from log line (format: YYYY-MM-DD HH:MM:SS)
                    try:
                        log_time_str = line.split(' - ')[0]
                        log_dt = datetime.strptime(log_time_str, '%Y-%m-%d %H:%M:%S,%f')
                        if log_dt >= since_dt:
                            filtered_lines.append(line)
                    except:
                        # If we can't parse timestamp, include the line
                        filtered_lines.append(line)
                all_lines = filtered_lines
            except Exception as e:
                # If timestamp parsing fails, return all lines
                pass
        
        # Get last N lines
        logs = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "logs": [line.rstrip('\n') for line in logs],
            "total_lines": total_lines,
            "file_exists": True,
            "last_updated": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading logs: {str(e)}")


@router.post("/restart")
async def restart_backend():
    """Trigger backend restart (creates a restart flag file)"""
    try:
        # Create a restart flag file that an external process manager can watch
        restart_flag = Path(__file__).parent.parent.parent / "backend" / ".restart_flag"
        restart_flag.touch()
        
        # Log the restart request
        logging.info("Backend restart requested via API")
        
        return {
            "message": "Restart signal sent. The backend will restart if a process manager is configured.",
            "restart_flag_created": True,
            "note": "For automatic restart, use a process manager like supervisor, systemd, or a wrapper script that watches for .restart_flag"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating restart flag: {str(e)}")


@router.get("/status")
async def get_backend_status():
    """Get backend status information"""
    try:
        log_file_size = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
        restart_flag_exists = (Path(__file__).parent.parent.parent / "backend" / ".restart_flag").exists()
        
        return {
            "status": "running",
            "log_file": str(LOG_FILE),
            "log_file_exists": LOG_FILE.exists(),
            "log_file_size_bytes": log_file_size,
            "restart_flag_exists": restart_flag_exists,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
