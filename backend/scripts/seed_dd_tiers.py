"""
Seed DD (DiscreetDolls) tiers with rate information.

DD Tiers:
- 1 star: Doll - 160/200/260/280
- 2 star: Diamond Doll - 190/230/260/320
- 3 star: Platinum Dolls - 220/260/330/350
- 4 star: Sapphire Dolls - 290/330/400/420
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal, Source, Tier


def seed_dd_tiers():
    """Seed tiers for DD source"""
    db = SessionLocal()
    try:
        print("\n" + "=" * 60)
        print("SEEDING DD TIERS")
        print("=" * 60)

        # Get DD source
        dd_source = db.query(Source).filter(Source.name == "DD").first()

        if not dd_source:
            print("DD source not found! Creating it...")
            dd_source = Source(
                name="DD",
                url="https://discreetdolls.com/daily-schedule/",
                base_url="https://discreetdolls.com/",
                image_base_url="https://discreetdolls.com/wp-content/uploads/",
                active=True
            )
            db.add(dd_source)
            db.commit()
            db.refresh(dd_source)
            print(f"Created DD source with ID {dd_source.id}")

        # Remove existing DD tiers
        existing_tiers = db.query(Tier).filter(Tier.source_id == dd_source.id).all()
        if existing_tiers:
            for tier in existing_tiers:
                db.delete(tier)
            db.commit()
            print(f"Removed {len(existing_tiers)} existing tiers")

        # DD tier definitions
        dd_tiers = [
            {
                "tier": "Doll",
                "star": 1,
                "incall_30min": "$160",
                "incall_45min": "$200",
                "incall_1hr": "$260",
                "outcall_per_hr": "$280"
            },
            {
                "tier": "Diamond Doll",
                "star": 2,
                "incall_30min": "$190",
                "incall_45min": "$230",
                "incall_1hr": "$260",
                "outcall_per_hr": "$320"
            },
            {
                "tier": "Platinum Dolls",
                "star": 3,
                "incall_30min": "$220",
                "incall_45min": "$260",
                "incall_1hr": "$330",
                "outcall_per_hr": "$350"
            },
            {
                "tier": "Sapphire Dolls",
                "star": 4,
                "incall_30min": "$290",
                "incall_45min": "$330",
                "incall_1hr": "$400",
                "outcall_per_hr": "$420"
            },
        ]

        # Insert tiers
        for tier_data in dd_tiers:
            tier = Tier(
                source_id=dd_source.id,
                tier=tier_data["tier"],
                star=tier_data["star"],
                incall_30min=tier_data["incall_30min"],
                incall_45min=tier_data["incall_45min"],
                incall_1hr=tier_data["incall_1hr"],
                outcall_per_hr=tier_data["outcall_per_hr"]
            )
            db.add(tier)
            print(f"  Added: {tier_data['star']} star - {tier_data['tier']}")

        db.commit()
        print(f"\nSeeded {len(dd_tiers)} tiers for DD source")

        # Verify
        print("\nDD Tiers:")
        print("-" * 70)
        print(f"{'Star':<6} {'Tier':<16} {'30min':<8} {'45min':<8} {'1hr':<8} {'Outcall':<8}")
        print("-" * 70)
        all_tiers = db.query(Tier).filter(
            Tier.source_id == dd_source.id
        ).order_by(Tier.star).all()

        for t in all_tiers:
            print(f"{t.star:<6} {t.tier:<16} {t.incall_30min:<8} {t.incall_45min:<8} {t.incall_1hr:<8} {t.outcall_per_hr:<8}")

    except Exception as e:
        db.rollback()
        print(f"Error seeding DD tiers: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_dd_tiers()
