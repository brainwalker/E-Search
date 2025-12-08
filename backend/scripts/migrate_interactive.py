"""
Migration script to transition from location string to locations table

This script:
1. Creates a backup of the database
2. Drops existing tables and recreates with new schema
3. Seeds locations table with predefined locations
4. Ready for new scrapes with the updated schema

IMPORTANT: This will delete all existing data!
Run this when you're ready to start fresh with the new locations table.
"""
import os
import shutil
from datetime import datetime
from api.database import engine, Base, SessionLocal, Location, Source, Tier


def backup_database():
    """Create a backup of the current database"""
    db_path = "./data/escort_listings.db"
    if os.path.exists(db_path):
        backup_path = f"./data/escort_listings_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(db_path, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
        return True
    else:
        print("ℹ️  No existing database found, creating new one...")
        return False


def recreate_tables():
    """Drop all tables and recreate with new schema"""
    print("\n🔄 Recreating database tables with new schema...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ Tables recreated successfully")


def seed_locations():
    """Seed the locations table with predefined locations"""
    db = SessionLocal()

    try:
        print("\n📍 Seeding locations...")

        # Create or get SFT source first
        source = db.query(Source).filter(Source.name == "SFT").first()
        if not source:
            source = Source(
                name="SFT",
                url="https://www.sexyfriendstoronto.com/toronto-escorts/schedule",
                base_url="https://www.sexyfriendstoronto.com/toronto-escorts/",
                image_base_url="https://www.sexyfriendstoronto.com/toronto-escorts/thumbnails/",
                active=True
            )
            db.add(source)
            db.commit()
            db.refresh(source)
            print(f"✅ Created source: {source.name}")

        # Define locations for SFT
        locations_data = [
            {"town": "Vaughan", "location": "unknown", "is_default": False},
            {"town": "Midtown", "location": "Yonge & Eglinton", "is_default": False},
            {"town": "Downtown", "location": "University & Queen", "is_default": False},
            {"town": "Downtown", "location": "Bay & Gerrard St W", "is_default": False},
            {"town": "Downtown", "location": "Dundas & Jarvis", "is_default": False},
            {"town": "Downtown", "location": "University & Adelaide", "is_default": False},
            {"town": "Downtown", "location": "Front & Spadina", "is_default": False},
            {"town": "Etobicoke", "location": "HWY-427 & Burnhamthorpe Rd", "is_default": False},
            {"town": "Oakville", "location": "Trafalgar & Uppermiddle Rd E", "is_default": False},
            {"town": "Mississauga", "location": "SQ1", "is_default": False},
            {"town": "Brampton", "location": "Unknown", "is_default": False},
            {"town": "Unknown", "location": "unknown", "is_default": True},  # Default fallback
        ]

        # Insert locations
        for loc_data in locations_data:
            location = Location(
                source_id=source.id,
                town=loc_data["town"],
                location=loc_data["location"],
                is_default=loc_data["is_default"]
            )
            db.add(location)

        db.commit()
        print(f"✅ Seeded {len(locations_data)} locations for {source.name}")

        # Display the created locations
        print("\n📋 Created locations:")
        locations = db.query(Location).filter(Location.source_id == source.id).all()
        for loc in locations:
            default_marker = " (DEFAULT)" if loc.is_default else ""
            print(f"   ID {loc.id}: {loc.town}, {loc.location}{default_marker}")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding locations: {e}")
        raise
    finally:
        db.close()


def seed_tiers():
    """Seed the tiers table with predefined tier pricing"""
    db = SessionLocal()

    try:
        print("\n⭐ Seeding tiers...")

        # Get SFT source
        source = db.query(Source).filter(Source.name == "SFT").first()
        if not source:
            print("⚠️  SFT source not found. Creating it first...")
            source = Source(
                name="SFT",
                url="https://www.sexyfriendstoronto.com/toronto-escorts/schedule",
                base_url="https://www.sexyfriendstoronto.com/toronto-escorts/",
                image_base_url="https://www.sexyfriendstoronto.com/toronto-escorts/thumbnails/",
                active=True
            )
            db.add(source)
            db.commit()
            db.refresh(source)
            print(f"✅ Created source: {source.name}")

        # Check if tiers already exist
        existing_count = db.query(Tier).filter(Tier.source_id == source.id).count()
        if existing_count > 0:
            print(f"⚠️  Tiers already exist for SFT ({existing_count} tiers found)")
            print("Skipping tier seed.")
            return

        # Define tiers for SFT
        tiers_data = [
            {
                "star": 1,
                "tier": "Elite",
                "incall_30min": "$160",
                "incall_45min": "$200",
                "incall_1hr": "$250",
                "outcall_per_hr": "$270"
            },
            {
                "star": 2,
                "tier": "VIP",
                "incall_30min": "$190",
                "incall_45min": "$230",
                "incall_1hr": "$290",
                "outcall_per_hr": "$300"
            },
            {
                "star": 3,
                "tier": "Ultra VIP",
                "incall_30min": "$230",
                "incall_45min": "$270",
                "incall_1hr": "$330",
                "outcall_per_hr": "$340"
            },
            {
                "star": 4,
                "tier": "Platinum VIP",
                "incall_30min": "$300",
                "incall_45min": "$350",
                "incall_1hr": "$400",
                "outcall_per_hr": "Unknown"
            }
        ]

        # Insert tiers
        for tier_data in tiers_data:
            tier = Tier(
                source_id=source.id,
                star=tier_data["star"],
                tier=tier_data["tier"],
                incall_30min=tier_data["incall_30min"],
                incall_45min=tier_data["incall_45min"],
                incall_1hr=tier_data["incall_1hr"],
                outcall_per_hr=tier_data["outcall_per_hr"]
            )
            db.add(tier)

        db.commit()
        print(f"✅ Seeded {len(tiers_data)} tiers for {source.name}")

        # Display the created tiers
        print("\n📋 Created tiers:")
        tiers = db.query(Tier).filter(Tier.source_id == source.id).order_by(Tier.star).all()
        for t in tiers:
            print(f"   Star {t.star}: {t.tier}")
            print(f"      Incall 30min: {t.incall_30min}, 45min: {t.incall_45min}, 1hr: {t.incall_1hr}")
            print(f"      Outcall per hr: {t.outcall_per_hr}")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding tiers: {e}")
        raise
    finally:
        db.close()


def main():
    """Main migration function"""
    print("=" * 60)
    print("DATABASE MIGRATION: Location String to Locations Table")
    print("=" * 60)
    print("\n⚠️  WARNING: This will delete all existing data!")
    print("⚠️  A backup will be created automatically.\n")

    response = input("Continue with migration? (yes/no): ")
    if response.lower() != 'yes':
        print("Migration cancelled.")
        return

    # Step 1: Backup
    print("\n" + "=" * 60)
    print("STEP 1: Backing up database")
    print("=" * 60)
    backup_database()

    # Step 2: Recreate tables
    print("\n" + "=" * 60)
    print("STEP 2: Recreating tables with new schema")
    print("=" * 60)
    recreate_tables()

    # Step 3: Seed locations
    print("\n" + "=" * 60)
    print("STEP 3: Seeding locations")
    print("=" * 60)
    seed_locations()

    # Step 4: Seed tiers
    print("\n" + "=" * 60)
    print("STEP 4: Seeding tiers")
    print("=" * 60)
    seed_tiers()

    print("\n" + "=" * 60)
    print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("\nNext steps:")
    print("1. Start the backend server: cd backend && python -m api.main")
    print("2. Run the scraper to populate data with new location references")
    print("\nThe 'Delete all data' button will preserve sources, locations, and tiers.")


if __name__ == "__main__":
    main()
