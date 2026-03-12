"""
TTL Cache — Avoid redundant LLM calls for identical requests
"""

from cachetools import TTLCache
from typing import Any

_crew_cache: TTLCache = TTLCache(maxsize=128, ttl=300)


def get_cached_result(key: str) -> Any | None:
    """Return cached crew result or ``None`` on miss."""
    return _crew_cache.get(key)


def set_cached_result(key: str, value: Any) -> None:
    """Store a crew result with automatic TTL expiry."""
    _crew_cache[key] = value


def make_cache_key(topic: str, **kwargs: Any) -> str:
    """Build a deterministic cache key from request parameters."""
    parts = [topic] + [f"{k}={v}" for k, v in sorted(kwargs.items()) if v is not None]
    return "|".join(parts)


def clear_cache() -> None:
    """Manually flush all cached results."""
    _crew_cache.clear()
