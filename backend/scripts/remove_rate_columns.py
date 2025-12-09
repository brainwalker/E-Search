"""
Migration script to remove rate columns from listings table.
Rates are now retrieved from the tiers table based on the tier field.
"""
import sqlite3
from pathlib import Path


def migrate():
    """Remove rate columns from listings table"""
    db_path = Path(__file__).parent.parent / "data" / "escort_listings.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return False
    
    print(f"📂 Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns exist
        cursor.execute("PRAGMA table_info(listings)")
        columns = {row[1] for row in cursor.fetchall()}
        
        rate_columns = ['incall_30min', 'incall_45min', 'incall_1hr', 'outcall_1hr', 'rate_notes']
        existing_rate_columns = [col for col in rate_columns if col in columns]
        
        if not existing_rate_columns:
            print("✅ Rate columns already removed")
            return True
        
        print(f"📋 Rate columns to remove: {existing_rate_columns}")
        
        # SQLite doesn't support DROP COLUMN directly, need to recreate table
        # First, get the current table schema without rate columns
        
        # Create new table without rate columns
        print("\n🔄 Creating new listings table without rate columns...")
        
        cursor.execute("""
            CREATE TABLE listings_new (
                id INTEGER PRIMARY KEY,
                source_id INTEGER,
                name VARCHAR NOT NULL,
                profile_url VARCHAR,
                tier VARCHAR,
                age INTEGER,
                nationality VARCHAR,
                height VARCHAR,
                weight VARCHAR,
                bust VARCHAR,
                bust_type VARCHAR,
                eye_color VARCHAR,
                hair_color VARCHAR,
                service_type VARCHAR,
                images TEXT,
                is_active BOOLEAN DEFAULT 1,
                is_expired BOOLEAN DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(source_id) REFERENCES sources(id)
            )
        """)
        
        # Copy data
        print("📦 Copying data to new table...")
        cursor.execute("""
            INSERT INTO listings_new (
                id, source_id, name, profile_url, tier, age, nationality,
                height, weight, bust, bust_type, eye_color, hair_color,
                service_type, images, is_active, is_expired, created_at, updated_at
            )
            SELECT 
                id, source_id, name, profile_url, tier, age, nationality,
                height, weight, bust, bust_type, eye_color, hair_color,
                service_type, images, is_active, is_expired, created_at, updated_at
            FROM listings
        """)
        
        # Get count
        cursor.execute("SELECT COUNT(*) FROM listings_new")
        count = cursor.fetchone()[0]
        print(f"   Copied {count} listings")
        
        # Drop old table and rename new one
        print("🗑️ Dropping old table...")
        cursor.execute("DROP TABLE listings")
        
        print("📝 Renaming new table...")
        cursor.execute("ALTER TABLE listings_new RENAME TO listings")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("   Rate columns removed: incall_30min, incall_45min, incall_1hr, outcall_1hr, rate_notes")
        print("   Rates are now determined by the tier field via the tiers table")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("REMOVE RATE COLUMNS MIGRATION")
    print("=" * 60)
    migrate()
