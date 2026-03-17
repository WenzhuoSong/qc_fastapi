"""
Phase 1 Database Migration Script

Adds new columns to ticker_news_library table:
- category (VARCHAR50)
- related (JSONB)
- datetime_utc (INTEGER)
- url (TEXT)
- credibility (INTEGER)

Usage:
    python migrate_phase1.py              # local
    python migrate_phase1.py --production # Railway (uses DATABASE_URL from env)
"""

import sys
from sqlalchemy import text

from app.db.database import SessionLocal, engine
from app.config import settings


MIGRATION_SQL = """
-- Phase 1 Schema Changes for ticker_news_library
-- Check if columns exist before adding to make this idempotent

DO $$
BEGIN
    -- Add category column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='ticker_news_library' AND column_name='category'
    ) THEN
        ALTER TABLE ticker_news_library ADD COLUMN category VARCHAR(50);
        RAISE NOTICE 'Added column: category';
    ELSE
        RAISE NOTICE 'Column already exists: category';
    END IF;

    -- Add related column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='ticker_news_library' AND column_name='related'
    ) THEN
        ALTER TABLE ticker_news_library ADD COLUMN related JSONB;
        RAISE NOTICE 'Added column: related';
    ELSE
        RAISE NOTICE 'Column already exists: related';
    END IF;

    -- Add datetime_utc column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='ticker_news_library' AND column_name='datetime_utc'
    ) THEN
        ALTER TABLE ticker_news_library ADD COLUMN datetime_utc INTEGER;
        RAISE NOTICE 'Added column: datetime_utc';
    ELSE
        RAISE NOTICE 'Column already exists: datetime_utc';
    END IF;

    -- Add url column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='ticker_news_library' AND column_name='url'
    ) THEN
        ALTER TABLE ticker_news_library ADD COLUMN url TEXT;
        RAISE NOTICE 'Added column: url';
    ELSE
        RAISE NOTICE 'Column already exists: url';
    END IF;

    -- Add credibility column
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='ticker_news_library' AND column_name='credibility'
    ) THEN
        ALTER TABLE ticker_news_library ADD COLUMN credibility INTEGER;
        RAISE NOTICE 'Added column: credibility';
    ELSE
        RAISE NOTICE 'Column already exists: credibility';
    END IF;
END $$;
"""


def run_migration():
    """Execute the Phase 1 migration."""
    print("=" * 60)
    print("Phase 1 Database Migration")
    print("=" * 60)
    print(f"Database: {settings.DATABASE_URL[:50]}..." if settings.DATABASE_URL else "No DATABASE_URL")
    print()

    if not settings.DATABASE_URL:
        print("❌ ERROR: DATABASE_URL not set in environment")
        sys.exit(1)

    try:
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            pg_version = result.scalar()
            print(f"✓ Connected to PostgreSQL: {pg_version}\n")

        # Execute migration
        print("Running migration SQL...")
        print("-" * 60)

        with engine.begin() as conn:
            conn.execute(text(MIGRATION_SQL))

        print("-" * 60)
        print()

        # Verify new columns
        print("Verifying new columns...")
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = 'ticker_news_library'
                AND column_name IN ('category', 'related', 'datetime_utc', 'url', 'credibility')
                ORDER BY column_name
            """))

            columns = result.fetchall()
            if len(columns) == 5:
                print("✓ All 5 new columns verified:")
                for col_name, col_type in columns:
                    print(f"  - {col_name}: {col_type}")
            else:
                print(f"⚠ Only found {len(columns)}/5 columns")
                for col_name, col_type in columns:
                    print(f"  - {col_name}: {col_type}")

        print()
        print("=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)

    except Exception as e:
        print()
        print("=" * 60)
        print(f"❌ Migration failed: {e}")
        print("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        sys.exit(0)

    if "--production" in sys.argv:
        print("⚠ Running in PRODUCTION mode")
        confirm = input("Type 'yes' to continue: ")
        if confirm.lower() != "yes":
            print("Aborted.")
            sys.exit(0)

    run_migration()
