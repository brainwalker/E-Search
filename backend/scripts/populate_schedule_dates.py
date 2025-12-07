"""
Populate date field for existing schedules based on day_of_week
"""
from datetime import datetime, timedelta
from api.database import SessionLocal, Schedule


def get_date_from_day_of_week(day_of_week: str) -> datetime:
    """Convert day of week string to actual date (next occurrence of that day)"""
    # Map day names to weekday numbers (0 = Monday, 6 = Sunday)
    day_map = {
        'Monday': 0,
        'Tuesday': 1,
        'Wednesday': 2,
        'Thursday': 3,
        'Friday': 4,
        'Saturday': 5,
        'Sunday': 6
    }

    today = datetime.now()
    target_day = day_map.get(day_of_week)

    if target_day is None:
        # If day not recognized, return today's date
        return today.replace(hour=0, minute=0, second=0, microsecond=0)

    # Calculate days until target day
    current_day = today.weekday()
    days_ahead = target_day - current_day

    # If the day is today or has passed this week, get next week's occurrence
    if days_ahead <= 0:
        days_ahead += 7

    target_date = today + timedelta(days=days_ahead)
    return target_date.replace(hour=0, minute=0, second=0, microsecond=0)


def populate_dates():
    """Populate date field for all schedules that have null dates"""
    db = SessionLocal()
    try:
        print("\n📅 Populating schedule dates...")

        # Get all schedules with null dates
        schedules = db.query(Schedule).filter(Schedule.date == None).all()

        if not schedules:
            print("✅ All schedules already have dates!")
            return

        print(f"Found {len(schedules)} schedules without dates")

        updated_count = 0
        for schedule in schedules:
            if schedule.day_of_week:
                schedule.date = get_date_from_day_of_week(schedule.day_of_week)
                updated_count += 1

        db.commit()

        print(f"✅ Updated {updated_count} schedules with dates")

        # Verify
        null_count = db.query(Schedule).filter(Schedule.date == None).count()
        total_count = db.query(Schedule).count()

        print(f"\n📊 Schedule Stats:")
        print(f"   Total schedules: {total_count}")
        print(f"   With dates: {total_count - null_count}")
        print(f"   Without dates: {null_count}")

    except Exception as e:
        db.rollback()
        print(f"❌ Error populating dates: {e}")
        raise
    finally:
        db.close()


def main():
    """Main function"""
    print("=" * 60)
    print("POPULATE SCHEDULE DATES")
    print("=" * 60)

    try:
        populate_dates()

        print("\n" + "=" * 60)
        print("✅ COMPLETED SUCCESSFULLY!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Failed: {e}")
        import sys
        sys.exit(1)


if __name__ == "__main__":
    main()
