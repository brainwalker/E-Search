"""
Database Viewer Endpoints
Provides web interface to browse database tables
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from typing import Optional, Set
from api.database import get_db, engine, Listing, Location, Tier
from api.config import settings
import logging
from pathlib import Path
from datetime import datetime

router = APIRouter(prefix="/db", tags=["Database Viewer"])

# Use settings for log file path
LOG_FILE = settings.log_file

# Get logger for this module (logging is configured in main.py)
logger = logging.getLogger(__name__)

# Whitelist of allowed table names to prevent SQL injection
# This is populated dynamically from the database schema on first request
_ALLOWED_TABLES: Optional[Set[str]] = None


def get_allowed_tables() -> Set[str]:
    """Get the set of allowed table names from the database schema."""
    global _ALLOWED_TABLES
    if _ALLOWED_TABLES is None:
        inspector = inspect(engine)
        _ALLOWED_TABLES = set(inspector.get_table_names())
    return _ALLOWED_TABLES


def validate_table_name(table_name: str) -> str:
    """
    Validate that a table name is in the allowed list.
    Raises HTTPException if table name is not valid.
    """
    allowed = get_allowed_tables()
    if table_name not in allowed:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid table name: '{table_name}'. Allowed tables: {sorted(allowed)}"
        )
    return table_name


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

    # Validate table name against whitelist to prevent SQL injection
    table_name = validate_table_name(table_name)

    # Get total count - table_name is now validated/safe
    count_query = text(f"SELECT COUNT(*) FROM {table_name}")
    total_count = db.execute(count_query).scalar()

    # Get paginated data
    offset = (page - 1) * page_size
    
    # Custom column order for listings table to show important fields first
    if table_name == 'listings':
        columns_order = """id, name, tier, age, nationality, ethnicity, 
                          bust, measurements, height, weight, 
                          eye_color, hair_color, service_type, bust_type,
                          profile_url, source_id, images, 
                          is_active, is_expired, created_at, updated_at"""
        data_query = text(f"SELECT {columns_order} FROM {table_name} LIMIT :limit OFFSET :offset")
    else:
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
    # Use validated table names from whitelist
    tables = get_allowed_tables()

    stats = {}
    for table_name in sorted(tables):
        # Table names are from our validated whitelist, safe to use
        count_query = text(f"SELECT COUNT(*) FROM {table_name}")
        count = db.execute(count_query).scalar()
        stats[table_name] = count

    # Get database file size if SQLite
    try:
        size_query = text("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        size = db.execute(size_query).scalar()
        stats["_database_size_bytes"] = size
        stats["_database_size_mb"] = round(size / (1024 * 1024), 2)
    except Exception as e:
        # SQLite-specific query may fail on other databases
        logger.debug(f"Could not get database size: {e}")

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
                # Make since_dt timezone-naive for comparison with log timestamps
                if since_dt.tzinfo is not None:
                    since_dt = since_dt.replace(tzinfo=None)
                filtered_lines = []
                for line in all_lines:
                    # Try to parse timestamp from log line (format: YYYY-MM-DD HH:MM:SS)
                    try:
                        log_time_str = line.split(' - ')[0]
                        log_dt = datetime.strptime(log_time_str, '%Y-%m-%d %H:%M:%S,%f')
                        if log_dt >= since_dt:
                            filtered_lines.append(line)
                    except (ValueError, IndexError):
                        # If we can't parse timestamp, include the line
                        filtered_lines.append(line)
                all_lines = filtered_lines
            except ValueError as e:
                # If timestamp parsing fails, log and return all lines
                logger.debug(f"Could not parse 'since' timestamp: {e}")
        
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
    """Trigger backend restart by killing uvicorn processes and starting fresh"""
    import subprocess
    import signal
    import os
    import sys

    try:
        logging.info("Backend restart requested via API")

        # Get the backend directory
        backend_dir = Path(__file__).parent.parent

        # Find and kill existing uvicorn processes on port 8000
        try:
            # Use lsof to find process on port 8000
            result = subprocess.run(
                ["lsof", "-ti", ":8000"],
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        try:
                            os.kill(int(pid), signal.SIGTERM)
                            logging.info(f"Killed process {pid}")
                        except (ProcessLookupError, ValueError):
                            pass
        except Exception as e:
            logging.warning(f"Error killing existing processes: {e}")

        # Give processes time to die
        import asyncio
        await asyncio.sleep(1)

        # Force kill any remaining processes
        try:
            result = subprocess.run(
                ["lsof", "-ti", ":8000"],
                capture_output=True,
                text=True
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    if pid:
                        try:
                            os.kill(int(pid), signal.SIGKILL)
                            logging.info(f"Force killed process {pid}")
                        except (ProcessLookupError, ValueError):
                            pass
        except Exception:
            pass

        await asyncio.sleep(0.5)

        # Start new uvicorn process
        venv_python = backend_dir / ".venv" / "bin" / "python"
        if not venv_python.exists():
            venv_python = sys.executable

        subprocess.Popen(
            [str(venv_python), "-m", "uvicorn", "api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
            cwd=str(backend_dir),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )

        logging.info("Backend restart initiated")

        return {
            "message": "Backend restart initiated. Server will be available shortly.",
            "success": True
        }
    except Exception as e:
        logging.error(f"Error during restart: {e}")
        raise HTTPException(status_code=500, detail=f"Error restarting backend: {str(e)}")


@router.get("/status")
async def get_backend_status():
    """Get backend status information"""
    try:
        log_file_size = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0

        return {
            "status": "running",
            "log_file": str(LOG_FILE),
            "log_file_exists": LOG_FILE.exists(),
            "log_file_size_bytes": log_file_size,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/table/{table_name}/row/{row_id}")
async def get_table_row(
    table_name: str,
    row_id: int,
    db: Session = Depends(get_db)
):
    """Get a single row from a table"""
    allowed_tables = {'listings', 'locations', 'tiers'}
    if table_name not in allowed_tables:
        raise HTTPException(
            status_code=400,
            detail=f"Getting rows is only allowed for: {', '.join(sorted(allowed_tables))}. Requested: '{table_name}'"
        )
    
    table_name = validate_table_name(table_name)
    
    from api.database import Listing, Location, Tier
    
    if table_name == 'listings':
        row = db.query(Listing).filter(Listing.id == row_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Listing with id {row_id} not found")
        return {
            'id': row.id,
            'name': row.name,
            'tier': row.tier,
            'age': row.age,
            'nationality': row.nationality,
            'ethnicity': row.ethnicity,
            'height': row.height,
            'weight': row.weight,
            'measurements': row.measurements,
            'bust': row.bust,
            'bust_type': row.bust_type,
            'eye_color': row.eye_color,
            'hair_color': row.hair_color,
            'service_type': row.service_type,
            'images': row.images,
            'is_active': row.is_active,
            'is_expired': row.is_expired,
            'source_id': row.source_id,
            'profile_url': row.profile_url,
        }
    elif table_name == 'locations':
        row = db.query(Location).filter(Location.id == row_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Location with id {row_id} not found")
        return {
            'id': row.id,
            'town': row.town,
            'location': row.location,
            'address': row.address,
            'notes': row.notes,
            'source_id': row.source_id,
            'is_default': row.is_default,
        }
    elif table_name == 'tiers':
        row = db.query(Tier).filter(Tier.id == row_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Tier with id {row_id} not found")
        return {
            'id': row.id,
            'tier': row.tier,
            'star': row.star,
            'source_id': row.source_id,
            'incall_30min': row.incall_30min,
            'incall_45min': row.incall_45min,
            'incall_1hr': row.incall_1hr,
            'outcall_per_hr': row.outcall_per_hr,
        }


@router.put("/table/{table_name}/row/{row_id}")
async def update_table_row(
    table_name: str,
    row_id: int,
    updates: dict,
    db: Session = Depends(get_db)
):
    """Update a row in a table"""
    # Only allow updates to specific tables
    allowed_tables = {'listings', 'locations', 'tiers'}
    if table_name not in allowed_tables:
        raise HTTPException(
            status_code=400,
            detail=f"Editing is only allowed for: {', '.join(sorted(allowed_tables))}. Requested: '{table_name}'"
        )
    
    # Validate table name
    table_name = validate_table_name(table_name)
    
    # Import models
    from api.database import Listing, Location, Tier
    
    # Handle different table types
    if table_name == 'listings':
        row = db.query(Listing).filter(Listing.id == row_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Listing with id {row_id} not found")
        
        allowed_fields = {
            'name', 'profile_url', 'tier', 'age', 'nationality', 'ethnicity',
            'height', 'weight', 'measurements', 'bust', 'bust_type',
            'eye_color', 'hair_color', 'service_type', 'images',
            'is_active', 'is_expired', 'source_id'
        }
        
        # Update fields
        updated_fields = []
        for field, value in updates.items():
            if field not in allowed_fields:
                continue
            
            if hasattr(row, field):
                # Handle special cases
                if field == 'images' and isinstance(value, list):
                    import json
                    value = json.dumps(value) if value else None
                elif field in ('age', 'source_id') and value is not None:
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid value for {field}: {value}. Must be an integer."
                        )
                elif field in ('is_active', 'is_expired') and value is not None:
                    value = bool(value)
                
                setattr(row, field, value)
                updated_fields.append(field)
        
        # Update updated_at timestamp (only for listings)
        if table_name == 'listings' and updated_fields:
            row.updated_at = datetime.now()
        
        # Build result dict
        result = {
            'id': row.id,
            'name': row.name,
            'tier': row.tier,
            'age': row.age,
            'nationality': row.nationality,
            'ethnicity': row.ethnicity,
            'height': row.height,
            'weight': row.weight,
            'measurements': row.measurements,
            'bust': row.bust,
            'bust_type': row.bust_type,
            'eye_color': row.eye_color,
            'hair_color': row.hair_color,
            'service_type': row.service_type,
            'images': row.images,
            'is_active': row.is_active,
            'is_expired': row.is_expired,
            'source_id': row.source_id,
            'profile_url': row.profile_url,
            'updated_at': row.updated_at.isoformat() if row.updated_at else None,
        }
        
    elif table_name == 'locations':
        row = db.query(Location).filter(Location.id == row_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Location with id {row_id} not found")
        
        allowed_fields = {
            'town', 'location', 'address', 'notes', 'source_id', 'is_default'
        }
        
        updated_fields = []
        for field, value in updates.items():
            if field not in allowed_fields:
                continue
            
            if hasattr(row, field):
                # Handle special cases
                if field == 'source_id' and value is not None:
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid value for {field}: {value}. Must be an integer."
                        )
                elif field == 'is_default' and value is not None:
                    value = bool(value)
                elif value == '':
                    value = None  # Convert empty strings to None
                
                setattr(row, field, value)
                updated_fields.append(field)
        
        if not updated_fields:
            raise HTTPException(
                status_code=400,
                detail="No valid fields to update. Allowed fields: " + ", ".join(sorted(allowed_fields))
            )
        
        result = {
            'id': row.id,
            'town': row.town,
            'location': row.location,
            'address': row.address,
            'notes': row.notes,
            'source_id': row.source_id,
            'is_default': row.is_default,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
        
    elif table_name == 'tiers':
        row = db.query(Tier).filter(Tier.id == row_id).first()
        if not row:
            raise HTTPException(status_code=404, detail=f"Tier with id {row_id} not found")
        
        allowed_fields = {
            'tier', 'star', 'source_id',
            'incall_30min', 'incall_45min', 'incall_1hr', 'outcall_per_hr'
        }
        
        updated_fields = []
        for field, value in updates.items():
            if field not in allowed_fields:
                continue
            
            if hasattr(row, field):
                # Handle special cases
                if field == 'source_id' and value is not None:
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid value for {field}: {value}. Must be an integer."
                        )
                elif field == 'star' and value is not None:
                    try:
                        value = int(value)
                    except (ValueError, TypeError):
                        raise HTTPException(
                            status_code=400,
                            detail=f"Invalid value for {field}: {value}. Must be an integer."
                        )
                elif value == '':
                    value = None  # Convert empty strings to None
                
                setattr(row, field, value)
                updated_fields.append(field)
        
        if not updated_fields:
            raise HTTPException(
                status_code=400,
                detail="No valid fields to update. Allowed fields: " + ", ".join(sorted(allowed_fields))
            )
        
        result = {
            'id': row.id,
            'tier': row.tier,
            'star': row.star,
            'source_id': row.source_id,
            'incall_30min': row.incall_30min,
            'incall_45min': row.incall_45min,
            'incall_1hr': row.incall_1hr,
            'outcall_per_hr': row.outcall_per_hr,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
    
    if not updated_fields:
        raise HTTPException(
            status_code=400,
            detail="No valid fields to update"
        )
    
    try:
        db.commit()
        db.refresh(row)
        
        return {
            "success": True,
            "message": f"Updated {len(updated_fields)} field(s): {', '.join(updated_fields)}",
            "updated_fields": updated_fields,
            "row": result
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating {table_name} {row_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating row: {str(e)}")
