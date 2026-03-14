"""
PostgreSQL Connection Pool & Session Management (SQLAlchemy)

Engine and session are created lazily so the app can still start
(and tests can run) without a configured DATABASE_URL.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator, Optional

from app.config import settings

Base = declarative_base()

_engine = None
_SessionLocal = None


def _get_engine():
    global _engine
    if _engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
    return _engine


def _get_session_factory():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_get_engine())
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session per request."""
    factory = _get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def SessionLocal() -> Session:
    """Create a new DB session (for use outside FastAPI, e.g. cron_pipeline)."""
    factory = _get_session_factory()
    return factory()


def init_db() -> None:
    """Create all tables if they don't exist yet."""
    engine = _get_engine()
    Base.metadata.create_all(bind=engine)
