"""
Migration script to add ethnicity and measurements columns to listings table.
"""
import sqlite3
from pathlib import Path


def migrate():
    """Add ethnicity and measurements columns to listings table"""
    db_path = Path(__file__).parent.parent / "data" / "escort_listings.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return False
    
    print(f"📂 Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check current columns
        cursor.execute("PRAGMA table_info(listings)")
        columns = {row[1] for row in cursor.fetchall()}
        
        print(f"📋 Current columns: {len(columns)}")
        
        # Add ethnicity column if not exists
        if 'ethnicity' not in columns:
            print("   Adding 'ethnicity' column...")
            cursor.execute("ALTER TABLE listings ADD COLUMN ethnicity VARCHAR")
            print("   ✅ Added 'ethnicity'")
        else:
            print("   ⏭️ 'ethnicity' already exists")
        
        # Add measurements column if not exists
        if 'measurements' not in columns:
            print("   Adding 'measurements' column...")
            cursor.execute("ALTER TABLE listings ADD COLUMN measurements VARCHAR")
            print("   ✅ Added 'measurements'")
        else:
            print("   ⏭️ 'measurements' already exists")
        
        conn.commit()
        
        # Verify
        cursor.execute("PRAGMA table_info(listings)")
        new_columns = {row[1] for row in cursor.fetchall()}
        print(f"\n✅ Migration completed! Columns: {len(new_columns)}")
        
        # Show new columns
        added = new_columns - columns
        if added:
            print(f"   Added: {', '.join(added)}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("ADD ETHNICITY & MEASUREMENTS COLUMNS")
    print("=" * 60)
    migrate()
