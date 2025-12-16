"""
Seed SelectCompanyEscorts source, locations, and tiers into the database.

SelectCompanyEscorts details:
- Single location: Downtown Toronto (incall/outcall)
- Single tier: Standard pricing
- Schedule URL: https://www.selectcompanyescorts.com/schedule/
- Profile URL pattern: /toronto-companions/{name}/
"""
from api.database import SessionLocal, Source, Location, Tier


def seed_select():
    db = SessionLocal()

    try:
        # Check if Select source already exists
        source = db.query(Source).filter(Source.name == "SELECT").first()

        if not source:
            print("Creating SELECT source...")
            source = Source(
                name="SELECT",
                url="https://www.selectcompanyescorts.com/schedule/",
                base_url="https://www.selectcompanyescorts.com/toronto-escorts/",
                image_base_url="https://www.selectcompanyescorts.com/wp-content/uploads/",
                active=True
            )
            db.add(source)
            db.commit()
            db.refresh(source)
            print(f"  Created source: {source.name} (id={source.id})")
        else:
            print(f"SELECT source already exists (id={source.id})")

        # Seed locations - Select operates primarily in Downtown Toronto
        print("\nSeeding SELECT locations...")
        locations_data = [
            {"city": "Toronto", "town": "Downtown", "location": "Toronto", "is_default": True},
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

        # Seed tiers - Select has single standard tier pricing
        # In-Call: $160/30min, $200/45min, $250/1hr
        # Out-Call: $300/90min (Downtown)
        print("\nSeeding SELECT tiers...")
        tiers_data = [
            {
                "tier": "Standard",
                "star": 1,
                "incall_30min": "$160",
                "incall_45min": "$200",
                "incall_1hr": "$250",
                "outcall_per_hr": "$300"  # 90min outcall rate
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
        print("\nSELECT seed complete!")

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
            print(f"  Star {t.star}: {t.tier} - {t.incall_30min} / {t.incall_45min} / {t.incall_1hr}")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_select()
