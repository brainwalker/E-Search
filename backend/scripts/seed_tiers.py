"""
Seed tiers data for SFT
This script populates the tiers table with predefined tier pricing information
"""
from api.database import SessionLocal, Tier, Source


def seed_tiers():
    db = SessionLocal()

    try:
        # Get SFT source
        source = db.query(Source).filter(Source.name == "SFT").first()

        if not source:
            print("Error: SFT source not found. Please run scraper first to create the source.")
            return

        # Check if tiers already exist
        existing_count = db.query(Tier).filter(Tier.source_id == source.id).count()
        if existing_count > 0:
            print(f"Tiers already exist for SFT ({existing_count} tiers found)")
            print("Skipping seed. Delete existing tiers first if you want to re-seed.")
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
        print(f"✅ Successfully seeded {len(tiers_data)} tiers for SFT")

        # Display the created tiers
        print("\nCreated tiers:")
        tiers = db.query(Tier).filter(Tier.source_id == source.id).order_by(Tier.star).all()
        for t in tiers:
            print(f"  Star {t.star}: {t.tier}")
            print(f"    Incall 30min: {t.incall_30min}")
            print(f"    Incall 45min: {t.incall_45min}")
            print(f"    Incall 1hr: {t.incall_1hr}")
            print(f"    Outcall per hr: {t.outcall_per_hr}")

    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding tiers: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_tiers()
