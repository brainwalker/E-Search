"""
Seed Mirage source, locations, and tiers into the database.
"""
from api.database import SessionLocal, Source, Location, Tier


def seed_mirage():
    db = SessionLocal()

    try:
        # Check if Mirage source already exists
        source = db.query(Source).filter(Source.name == "Mirage").first()

        if not source:
            print("Creating Mirage source...")
            source = Source(
                name="Mirage",
                url="https://mirage-entertainment.cc/toronto-escorts-schedule/",
                base_url="https://mirage-entertainment.cc/escort/",
                image_base_url="https://mirage-entertainment.cc/wp-content/uploads/",
                active=True
            )
            db.add(source)
            db.commit()
            db.refresh(source)
            print(f"  Created source: {source.name} (id={source.id})")
        else:
            print(f"Mirage source already exists (id={source.id})")

        # Seed locations
        print("\nSeeding Mirage locations...")
        locations_data = [
            {"city": "Toronto", "town": "Downtown", "location": "DT Toronto", "is_default": True},
            {"city": "Toronto", "town": "North York", "location": "North York", "is_default": False},
            {"city": "Toronto", "town": "Markham", "location": "Markham", "is_default": False},
            {"city": "Toronto", "town": "Etobicoke", "location": "Airport", "is_default": False},
        ]

        for loc_data in locations_data:
            existing = db.query(Location).filter(
                Location.source_id == source.id,
                Location.town == loc_data["town"],
                Location.location == loc_data["location"]
            ).first()

            if not existing:
                location = Location(
                    source_id=source.id,
                    city=loc_data["city"],
                    town=loc_data["town"],
                    location=loc_data["location"],
                    is_default=loc_data["is_default"]
                )
                db.add(location)
                print(f"  Added: {loc_data['town']} - {loc_data['location']}")
            else:
                print(f"  Exists: {loc_data['town']} - {loc_data['location']}")

        db.commit()

        # Seed tiers
        # PLATINUM VIP has per-listing pricing, but we still add it for star lookup
        print("\nSeeding Mirage tiers...")
        tiers_data = [
            {
                "tier": "Regular",
                "star": 1,
                "incall_30min": "$160",
                "incall_45min": None,
                "incall_1hr": "$250",
                "outcall_per_hr": None
            },
            {
                "tier": "VIP",
                "star": 2,
                "incall_30min": "$200",
                "incall_45min": None,
                "incall_1hr": "$300",
                "outcall_per_hr": None
            },
            {
                "tier": "Platinum VIP",  # Uses per-listing pricing, but needs entry for star display
                "star": 3,
                "incall_30min": None,  # Variable per-listing
                "incall_45min": None,
                "incall_1hr": None,
                "outcall_per_hr": None
            },
        ]

        for tier_data in tiers_data:
            existing = db.query(Tier).filter(
                Tier.source_id == source.id,
                Tier.tier == tier_data["tier"]
            ).first()

            if not existing:
                tier = Tier(
                    source_id=source.id,
                    tier=tier_data["tier"],
                    star=tier_data["star"],
                    incall_30min=tier_data["incall_30min"],
                    incall_45min=tier_data["incall_45min"],
                    incall_1hr=tier_data["incall_1hr"],
                    outcall_per_hr=tier_data["outcall_per_hr"]
                )
                db.add(tier)
                print(f"  Added tier: {tier_data['tier']} (star={tier_data['star']})")
            else:
                print(f"  Exists: {tier_data['tier']}")

        db.commit()
        print("\nMirage seed complete!")

        # Display summary
        print("\n" + "=" * 50)
        print("Summary:")
        print("=" * 50)

        locs = db.query(Location).filter(Location.source_id == source.id).all()
        print(f"\nLocations ({len(locs)}):")
        for loc in locs:
            default = " (DEFAULT)" if loc.is_default else ""
            print(f"  {loc.id}: {loc.town} - {loc.location}{default}")

        tiers = db.query(Tier).filter(Tier.source_id == source.id).order_by(Tier.star).all()
        print(f"\nTiers ({len(tiers)}):")
        for t in tiers:
            print(f"  Star {t.star}: {t.tier} - {t.incall_30min} / {t.incall_1hr}")

        print("\nNote: Platinum VIP tier uses per-listing pricing (prices stored on listing)")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_mirage()
