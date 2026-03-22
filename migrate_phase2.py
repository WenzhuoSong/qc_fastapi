"""
Phase 2 Database Migration — Event Transmission Table

Creates the event_transmission table for storing macro event → sector
transmission vectors. Idempotent design: checks if table exists before creating.

Usage:
    python migrate_phase2.py
"""

import sys
from sqlalchemy import inspect

from app.db.database import engine, SessionLocal
from app.db.models import EventTransmission


def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    inspector = inspect(engine)
    return table_name in inspector.get_table_names()


def run_migration():
    """Create event_transmission table if it doesn't exist."""
    print("=== Phase 2 Migration: Event Transmission Table ===")

    if table_exists("event_transmission"):
        print("✓ event_transmission table already exists, skipping creation")
        return

    print("Creating event_transmission table...")

    try:
        # Create table using SQLAlchemy metadata
        EventTransmission.__table__.create(bind=engine, checkfirst=True)
        print("✓ event_transmission table created successfully")

        # Verify table was created
        if table_exists("event_transmission"):
            print("✓ Table verification passed")

            # Display schema
            inspector = inspect(engine)
            columns = inspector.get_columns("event_transmission")
            print("\nTable schema:")
            for col in columns:
                print(f"  - {col['name']}: {col['type']}")

        else:
            print("✗ Table verification failed")
            sys.exit(1)

    except Exception as e:
        print(f"✗ Migration failed: {e}")
        sys.exit(1)

    print("\n=== Phase 2 Migration Complete ===")


if __name__ == "__main__":
    run_migration()
