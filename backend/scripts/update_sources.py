"""
Update sources table schema and data
Adds base_url and image_base_url fields, updates SFT source, adds DD source
"""
import sys
from api.database import engine, SessionLocal, Source, Location
from sqlalchemy import text

def add_new_columns():
    """Add base_url and image_base_url columns to sources table"""
    db = SessionLocal()
    try:
        print("\n📝 Adding new columns to sources table...")

        # Add base_url column
        db.execute(text("ALTER TABLE sources ADD COLUMN base_url VARCHAR"))
        print("✅ Added base_url column")

        # Add image_base_url column
        db.execute(text("ALTER TABLE sources ADD COLUMN image_base_url VARCHAR"))
        print("✅ Added image_base_url column")

        db.commit()
        print("✅ Schema updated successfully")

    except Exception as e:
        db.rollback()
        if "duplicate column name" in str(e).lower():
            print("ℹ️  Columns already exist, skipping...")
        else:
            print(f"❌ Error adding columns: {e}")
            raise
    finally:
        db.close()


def update_sft_source():
    """Update SexyFriendsToronto source with new name and URLs"""
    db = SessionLocal()
    try:
        print("\n🔄 Updating SFT source...")

        # Find the SexyFriendsToronto source
        sft_source = db.query(Source).filter(Source.name == "SexyFriendsToronto").first()

        if sft_source:
            sft_source.name = "SFT"
            sft_source.url = "https://www.sexyfriendstoronto.com/toronto-escorts/schedule"
            sft_source.base_url = "https://www.sexyfriendstoronto.com/toronto-escorts/"
            sft_source.image_base_url = "https://www.sexyfriendstoronto.com/toronto-escorts/thumbnails/"

            db.commit()
            print(f"✅ Updated source:")
            print(f"   Name: {sft_source.name}")
            print(f"   URL: {sft_source.url}")
            print(f"   Base URL: {sft_source.base_url}")
            print(f"   Image Base URL: {sft_source.image_base_url}")
        else:
            print("⚠️  SexyFriendsToronto source not found")

    except Exception as e:
        db.rollback()
        print(f"❌ Error updating SFT source: {e}")
        raise
    finally:
        db.close()


def add_dd_source():
    """Add DiscreetDolls (DD) source"""
    db = SessionLocal()
    try:
        print("\n➕ Adding DD source...")

        # Check if DD source already exists
        dd_source = db.query(Source).filter(Source.name == "DD").first()

        if dd_source:
            print("ℹ️  DD source already exists")
            return

        # Create DD source
        dd_source = Source(
            name="DD",
            url="https://discreetdolls.com/daily-schedule/",
            base_url="https://discreetdolls.com/",  # To be updated based on actual URL structure
            image_base_url="https://discreetdolls.com/",  # To be updated based on actual URL structure
            active=True
        )

        db.add(dd_source)
        db.commit()
        db.refresh(dd_source)

        print(f"✅ Created DD source:")
        print(f"   ID: {dd_source.id}")
        print(f"   Name: {dd_source.name}")
        print(f"   URL: {dd_source.url}")

        # Create default location for DD
        default_location = Location(
            source_id=dd_source.id,
            town="Unknown",
            location="unknown",
            is_default=True
        )
        db.add(default_location)
        db.commit()
        print(f"✅ Created default location for DD source")

    except Exception as e:
        db.rollback()
        print(f"❌ Error adding DD source: {e}")
        raise
    finally:
        db.close()


def verify_changes():
    """Verify all changes were applied correctly"""
    db = SessionLocal()
    try:
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)

        sources = db.query(Source).all()
        print(f"\n📊 Total sources: {len(sources)}")

        for source in sources:
            print(f"\n📌 {source.name}")
            print(f"   URL: {source.url}")
            print(f"   Base URL: {source.base_url}")
            print(f"   Image Base URL: {source.image_base_url}")
            print(f"   Active: {source.active}")

            # Count locations for this source
            location_count = db.query(Location).filter(Location.source_id == source.id).count()
            print(f"   Locations: {location_count}")

    except Exception as e:
        print(f"❌ Error verifying changes: {e}")
    finally:
        db.close()


def main():
    """Main migration function"""
    print("=" * 60)
    print("SOURCE UPDATE MIGRATION")
    print("=" * 60)

    try:
        # Step 1: Add new columns
        print("\n" + "=" * 60)
        print("STEP 1: Adding new columns")
        print("=" * 60)
        add_new_columns()

        # Step 2: Update SFT source
        print("\n" + "=" * 60)
        print("STEP 2: Updating SFT source")
        print("=" * 60)
        update_sft_source()

        # Step 3: Add DD source
        print("\n" + "=" * 60)
        print("STEP 3: Adding DD source")
        print("=" * 60)
        add_dd_source()

        # Step 4: Verify changes
        verify_changes()

        print("\n" + "=" * 60)
        print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Update scraper to use base URLs when storing profile_url and images")
        print("2. Update frontend to merge base URLs with stored paths")
        print("3. Test scraping with updated sources")

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
