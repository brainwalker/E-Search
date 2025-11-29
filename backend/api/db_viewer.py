"""
Database Viewer Endpoints
Provides web interface to browse database tables
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from typing import List, Dict, Any
from api.database import get_db, engine, Base
import json

router = APIRouter(prefix="/db", tags=["Database Viewer"])


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
