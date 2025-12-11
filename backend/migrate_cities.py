#!/usr/bin/env python3
"""
Migration script to add city column to locations table and populate it correctly.
"""
from sqlalchemy import text
from api.database import engine, Location
from sqlalchemy.orm import sessionmaker

# Cities that are NOT Toronto neighborhoods
CITIES = ['Mississauga', 'Brampton', 'Oakville', 'Vaughan']

# Toronto neighborhoods
TORONTO_NEIGHBORHOODS = ['Downtown', 'Midtown', 'North York', 'Etobicoke']

def migrate():
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # First, check if the column exists
        with engine.connect() as conn:
            # Add the city column if it doesn't exist
            try:
                conn.execute(text("ALTER TABLE locations ADD COLUMN city VARCHAR DEFAULT 'Toronto'"))
                conn.commit()
                print("✓ Added 'city' column to locations table")
            except Exception as e:
                if 'duplicate column name' in str(e).lower() or 'already exists' in str(e).lower():
                    print("✓ 'city' column already exists")
                else:
                    print(f"Note: {e}")

        # Update all locations with proper city values
        print("\nUpdating location cities...")

        # Set city for standalone cities (Mississauga, Brampton, etc.)
        for city_name in CITIES:
            count = db.query(Location).filter(Location.town == city_name).update({
                'city': city_name,
                'town': city_name
            })
            if count > 0:
                print(f"  ✓ Updated {count} {city_name} locations (city=town={city_name})")

        # Set city='Toronto' for Toronto neighborhoods
        for neighborhood in TORONTO_NEIGHBORHOODS:
            count = db.query(Location).filter(Location.town == neighborhood).update({
                'city': 'Toronto',
                'town': neighborhood
            })
            if count > 0:
                print(f"  ✓ Updated {count} {neighborhood} locations (city=Toronto, town={neighborhood})")

        # Handle Unknown locations
        count = db.query(Location).filter(Location.town == 'Unknown').update({
            'city': 'Toronto',
            'town': 'Unknown'
        })
        if count > 0:
            print(f"  ✓ Updated {count} Unknown locations (city=Toronto, town=Unknown)")

        db.commit()
        print("\n✅ Migration completed successfully!")

        # Show summary
        print("\nLocation summary:")
        cities = db.query(Location.city, Location.town).distinct().all()
        for city, town in sorted(cities):
            count = db.query(Location).filter(Location.city == city, Location.town == town).count()
            print(f"  - {city}/{town}: {count} locations")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == '__main__':
    print("Starting migration to add city column...\n")
    migrate()
