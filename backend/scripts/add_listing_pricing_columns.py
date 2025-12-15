"""
Migration script to add per-listing pricing columns to the listings table.
These columns support sources with variable pricing (like Mirage PLATINUM VIP).

When null, pricing falls back to tier-based lookup from the tiers table.
"""
import sqlite3
from pathlib import Path


def migrate():
    """Add pricing columns to listings table"""
    db_path = Path(__file__).parent.parent / "data" / "escort_listings.db"

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        print("Run the backend server first to create the database.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check which columns already exist
    cursor.execute("PRAGMA table_info(listings)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    new_columns = [
        ("incall_30min", "VARCHAR"),
        ("incall_45min", "VARCHAR"),
        ("incall_1hr", "VARCHAR"),
        ("outcall_1hr", "VARCHAR"),
        ("min_booking", "VARCHAR"),
    ]

    added = 0
    for col_name, col_type in new_columns:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE listings ADD COLUMN {col_name} {col_type}")
                print(f"  Added column: {col_name}")
                added += 1
            except sqlite3.OperationalError as e:
                print(f"  Error adding {col_name}: {e}")
        else:
            print(f"  Column already exists: {col_name}")

    conn.commit()
    conn.close()

    if added > 0:
        print(f"\n Successfully added {added} new column(s)")
    else:
        print(f"\n All columns already exist, no changes needed")

    return True


def verify():
    """Verify the columns were added"""
    db_path = Path(__file__).parent.parent / "data" / "escort_listings.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(listings)")
    columns = cursor.fetchall()

    print("\nListings table columns:")
    for col in columns:
        print(f"  {col[1]}: {col[2]}")

    conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Adding per-listing pricing columns to listings table")
    print("=" * 60)
    print("\nNew columns:")
    print("  - incall_30min: Per-listing 30min incall rate")
    print("  - incall_45min: Per-listing 45min incall rate")
    print("  - incall_1hr: Per-listing 1hr incall rate")
    print("  - outcall_1hr: Per-listing 1hr outcall rate")
    print("  - min_booking: Minimum booking time (30min, 45min, 1hr)")
    print("\nThese columns are nullable. When null, pricing falls back to")
    print("tier-based lookup from the tiers table.\n")

    if migrate():
        verify()
        print("\n Migration complete!")
    else:
        print("\n Migration failed!")
