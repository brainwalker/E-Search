"""
Add performance indexes to the database.
Based on analysis of common query patterns.
"""
import sqlite3
from pathlib import Path


def add_indexes():
    """Add missing indexes for better query performance"""
    db_path = Path(__file__).parent.parent / "data" / "escort_listings.db"
    
    if not db_path.exists():
        print(f"❌ Database not found at {db_path}")
        return False
    
    print(f"📂 Database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Indexes to create
    indexes = [
        # Listings table - frequently filtered/sorted columns
        ("ix_listings_source_id", "listings", "source_id"),
        ("ix_listings_tier", "listings", "tier"),
        ("ix_listings_is_expired", "listings", "is_expired"),
        ("ix_listings_is_active", "listings", "is_active"),
        ("ix_listings_updated_at", "listings", "updated_at DESC"),
        ("ix_listings_name", "listings", "name"),
        
        # Listing tags - junction table needs indexes on both FKs
        ("ix_listing_tags_listing_id", "listing_tags", "listing_id"),
        ("ix_listing_tags_tag_id", "listing_tags", "tag_id"),
    ]
    
    # Composite indexes for common query patterns
    composite_indexes = [
        # Source + expired filter (common filter combination)
        ("ix_listings_source_expired", "listings", "source_id, is_expired"),
        # Source + tier filter
        ("ix_listings_source_tier", "listings", "source_id, tier"),
    ]
    
    created = 0
    skipped = 0
    
    try:
        # Get existing indexes
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        existing = {row[0] for row in cursor.fetchall()}
        
        print(f"\n📋 Existing indexes: {len(existing)}")
        
        # Create single-column indexes
        print("\n🔧 Creating single-column indexes...")
        for name, table, column in indexes:
            if name in existing:
                print(f"   ⏭️ {name} already exists")
                skipped += 1
            else:
                sql = f"CREATE INDEX {name} ON {table} ({column})"
                cursor.execute(sql)
                print(f"   ✅ Created {name}")
                created += 1
        
        # Create composite indexes
        print("\n🔧 Creating composite indexes...")
        for name, table, columns in composite_indexes:
            if name in existing:
                print(f"   ⏭️ {name} already exists")
                skipped += 1
            else:
                sql = f"CREATE INDEX {name} ON {table} ({columns})"
                cursor.execute(sql)
                print(f"   ✅ Created {name}")
                created += 1
        
        conn.commit()
        
        # Analyze tables to update query planner statistics
        print("\n📊 Analyzing tables for query optimization...")
        cursor.execute("ANALYZE")
        conn.commit()
        
        print(f"\n✅ Done! Created {created} indexes, skipped {skipped} existing")
        
        # Show final index list
        print("\n📋 Current indexes:")
        cursor.execute("""
            SELECT name, tbl_name 
            FROM sqlite_master 
            WHERE type='index' 
            ORDER BY tbl_name, name
        """)
        for row in cursor.fetchall():
            print(f"   {row[1]}: {row[0]}")
        
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("ADD PERFORMANCE INDEXES")
    print("=" * 60)
    add_indexes()
