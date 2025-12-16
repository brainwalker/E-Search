"""
Seed SecretEscorts source, locations, and tiers into the database.

SecretEscorts details:
- Locations: Etobicoke, North York, Vaughan, Oakville
- Tiers: Blush (star=1), Rose (star=2), Rouge (star=3)
- Schedule URL: https://secretescorts.ca/availability/
- Secrets list: https://secretescorts.ca/secrets/
- Profile URL pattern: /model/{name}/
"""
from api.database import SessionLocal, Source, Location, Tier


def seed_secret():
    db = SessionLocal()

    try:
        # Check if Secret source already exists
        source = db.query(Source).filter(Source.name == "SECRET").first()

        if not source:
            print("Creating SECRET source...")
            source = Source(
                name="SECRET",
                url="https://secretescorts.ca/availability/",
                base_url="https://secretescorts.ca/model/",
                image_base_url="https://secretescorts.ca/wp-content/uploads/",
                active=True
            )
            db.add(source)
            db.commit()
            db.refresh(source)
            print(f"  Created source: {source.name} (id={source.id})")
        else:
            print(f"SECRET source already exists (id={source.id})")

        # Seed locations - Secret operates in 4 GTA locations
        print("\nSeeding SECRET locations...")
        locations_data = [
            {"city": "Toronto", "town": "Etobicoke", "location": "Etobicoke", "is_default": True},
            {"city": "Toronto", "town": "North York", "location": "North York", "is_default": False},
            {"city": "Toronto", "town": "Vaughan", "location": "Vaughan", "is_default": False},
            {"city": "Oakville", "town": "Oakville", "location": "Oakville", "is_default": False},
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

        # Seed tiers - Secret has 3 tiers: Blush, Rose, Rouge
        # Pricing from profile pages:
        # Blush: $200/30min, $250/45min, $300/1hr, $470/90min
        # Rose: $250/30min, $300/45min, $350/1hr, $540/90min
        # Rouge: $280/30min, $320/45min, $380/1hr, $600/90min
        print("\nSeeding SECRET tiers...")
        tiers_data = [
            {
                "tier": "Blush",
                "star": 1,
                "incall_30min": "$200",
                "incall_45min": "$250",
                "incall_1hr": "$300",
                "incall_90min": "$470",
                "outcall_per_hr": None
            },
            {
                "tier": "Rose",
                "star": 2,
                "incall_30min": "$250",
                "incall_45min": "$300",
                "incall_1hr": "$350",
                "incall_90min": "$540",
                "outcall_per_hr": None
            },
            {
                "tier": "Rouge",
                "star": 3,
                "incall_30min": "$280",
                "incall_45min": "$320",
                "incall_1hr": "$380",
                "incall_90min": "$600",
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
                    incall_90min=tier_data["incall_90min"],
                    outcall_per_hr=tier_data["outcall_per_hr"]
                )
                db.add(tier)
                print(f"  Added tier: {tier_data['tier']} (star={tier_data['star']})")
            else:
                # Update existing tier with 90min rate if missing
                if not existing.incall_90min and tier_data.get("incall_90min"):
                    existing.incall_90min = tier_data["incall_90min"]
                    print(f"  Updated {tier_data['tier']} with 90min rate: {tier_data['incall_90min']}")
                else:
                    print(f"  Exists: {tier_data['tier']}")

        db.commit()
        print("\nSECRET seed complete!")

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
            print(f"  Star {t.star}: {t.tier} - {t.incall_30min} / {t.incall_45min} / {t.incall_1hr} / {t.incall_90min}")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_secret()
