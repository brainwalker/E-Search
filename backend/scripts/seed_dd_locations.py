"""
Seed DD (DiscreetDolls) locations and update source URLs
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal, Source, Location


def update_dd_source():
    """Update DD source with correct base URLs"""
    db = SessionLocal()
    try:
        print("\n🔄 Updating DD source URLs...")

        dd_source = db.query(Source).filter(Source.name == "DD").first()

        if not dd_source:
            print("❌ DD source not found!")
            return None

        # Update URLs
        dd_source.base_url = "https://discreetdolls.com/"
        dd_source.image_base_url = "https://discreetdolls.com/wp-content/uploads/"

        db.commit()
        db.refresh(dd_source)

        print(f"✅ Updated DD source:")
        print(f"   Base URL: {dd_source.base_url}")
        print(f"   Image Base URL: {dd_source.image_base_url}")

        return dd_source

    except Exception as e:
        db.rollback()
        print(f"❌ Error updating DD source: {e}")
        raise
    finally:
        db.close()


def seed_dd_locations():
    """Seed locations for DD source"""
    db = SessionLocal()
    try:
        print("\n📍 Seeding DD locations...")

        # Get DD source
        dd_source = db.query(Source).filter(Source.name == "DD").first()

        if not dd_source:
            print("❌ DD source not found!")
            return

        # Remove existing non-default DD locations (keep default)
        existing_locations = db.query(Location).filter(
            Location.source_id == dd_source.id,
            Location.is_default == False
        ).all()

        if existing_locations:
            for loc in existing_locations:
                db.delete(loc)
            db.commit()
            print(f"🗑️  Removed {len(existing_locations)} existing non-default locations")

        # Define DD locations
        dd_locations = [
            {"town": "Downtown", "location": "Richmond-Peter", "is_default": False},
            {"town": "Downtown", "location": "Front-Spadina", "is_default": False},
            {"town": "Downtown", "location": "Bay-College", "is_default": False},
            {"town": "North York", "location": "unknown", "is_default": False},
            {"town": "Etobicoke", "location": "HWY427-Bloor", "is_default": False},
            {"town": "Mississauga", "location": "HWY10-Eglinton", "is_default": False},
            {"town": "Mississauga", "location": "Square One", "is_default": False},
            {"town": "Oakville", "location": "unknown", "is_default": False},
            {"town": "unknown", "location": "unknown", "is_default": True},  # Default (update existing)
        ]

        # Insert new locations
        for loc_data in dd_locations:
            # Check if this is the default location (it should already exist)
            if loc_data["is_default"]:
                default_loc = db.query(Location).filter(
                    Location.source_id == dd_source.id,
                    Location.is_default == True
                ).first()

                if default_loc:
                    # Update existing default
                    default_loc.town = loc_data["town"]
                    default_loc.location = loc_data["location"]
                    print(f"✅ Updated default location")
                else:
                    # Create default if it doesn't exist
                    location = Location(
                        source_id=dd_source.id,
                        town=loc_data["town"],
                        location=loc_data["location"],
                        is_default=loc_data["is_default"]
                    )
                    db.add(location)
                    print(f"✅ Created default location")
            else:
                # Add new non-default location
                location = Location(
                    source_id=dd_source.id,
                    town=loc_data["town"],
                    location=loc_data["location"],
                    is_default=loc_data["is_default"]
                )
                db.add(location)

        db.commit()
        print(f"✅ Seeded {len(dd_locations)} locations for DD source")

        # Display all DD locations
        print("\n📋 DD Locations:")
        all_dd_locations = db.query(Location).filter(
            Location.source_id == dd_source.id
        ).order_by(Location.id).all()

        for loc in all_dd_locations:
            default_marker = " (DEFAULT)" if loc.is_default else ""
            print(f"   ID {loc.id}: {loc.town}, {loc.location}{default_marker}")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding DD locations: {e}")
        raise
    finally:
        db.close()


def verify_all_sources():
    """Verify all sources and their locations"""
    db = SessionLocal()
    try:
        print("\n" + "=" * 60)
        print("VERIFICATION - ALL SOURCES")
        print("=" * 60)

        sources = db.query(Source).all()

        for source in sources:
            print(f"\n📌 {source.name}")
            print(f"   URL: {source.url}")
            print(f"   Base URL: {source.base_url}")
            print(f"   Image Base URL: {source.image_base_url}")

            location_count = db.query(Location).filter(
                Location.source_id == source.id
            ).count()
            print(f"   Total Locations: {location_count}")

    except Exception as e:
        print(f"❌ Error verifying: {e}")
    finally:
        db.close()


def main():
    """Main function"""
    print("=" * 60)
    print("DD SOURCE & LOCATIONS SETUP")
    print("=" * 60)

    try:
        # Step 1: Update DD source URLs
        print("\n" + "=" * 60)
        print("STEP 1: Updating DD Source URLs")
        print("=" * 60)
        update_dd_source()

        # Step 2: Seed DD locations
        print("\n" + "=" * 60)
        print("STEP 2: Seeding DD Locations")
        print("=" * 60)
        seed_dd_locations()

        # Step 3: Verify
        verify_all_sources()

        print("\n" + "=" * 60)
        print("✅ SETUP COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        import sys
        sys.exit(1)


if __name__ == "__main__":
    main()
