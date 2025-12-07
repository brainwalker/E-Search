"""
Seed locations data for SexyFriendsToronto
This script populates the locations table with predefined locations
"""
from api.database import SessionLocal, Location, Source


def seed_locations():
    db = SessionLocal()

    try:
        # Get SexyFriendsToronto source
        source = db.query(Source).filter(Source.name == "SexyFriendsToronto").first()

        if not source:
            print("Error: SexyFriendsToronto source not found. Please run scraper first to create the source.")
            return

        # Check if locations already exist
        existing_count = db.query(Location).filter(Location.source_id == source.id).count()
        if existing_count > 0:
            print(f"Locations already exist for SexyFriendsToronto ({existing_count} locations found)")
            print("Skipping seed. Delete existing locations first if you want to re-seed.")
            return

        # Define locations for SexyFriendsToronto
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
        print(f"✅ Successfully seeded {len(locations_data)} locations for SexyFriendsToronto")

        # Display the created locations
        print("\nCreated locations:")
        locations = db.query(Location).filter(Location.source_id == source.id).all()
        for loc in locations:
            default_marker = " (DEFAULT)" if loc.is_default else ""
            print(f"  ID {loc.id}: {loc.town}, {loc.location}{default_marker}")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding locations: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_locations()
