"""Caching utilities for API responses and data.

This module provides caching functionality to improve performance by reducing
repeated API calls and expensive computations.
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional, Tuple
from functools import wraps

logger = logging.getLogger("talk2me_ui.cache")


class TTLCache:
    """Time-based cache with automatic expiration.

    Thread-safe in-memory cache that automatically removes expired entries.
    """

    def __init__(self, default_ttl: int = 300):
        """Initialize the cache.

        Args:
            default_ttl: Default time-to-live in seconds for cache entries
        """
        self.default_ttl = default_ttl
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = asyncio.Lock()

    def _make_key(self, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        # Sort kwargs for consistent key generation
        key_parts = list(args)
        key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
        key_string = "|".join(str(part) for part in key_parts)
        return hashlib.md5(key_string.encode()).hexdigest()

    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        async with self._lock:
            if key not in self._cache:
                return None

            value, expires_at = self._cache[key]
            if time.time() > expires_at:
                # Entry expired, remove it
                del self._cache[key]
                return None

            return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in the cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default if None)
        """
        async with self._lock:
            expires_at = time.time() + (ttl or self.default_ttl)
            self._cache[key] = (value, expires_at)

    async def delete(self, key: str) -> bool:
        """Delete a value from the cache.

        Args:
            key: Cache key

        Returns:
            True if key was found and deleted, False otherwise
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()

    async def cleanup_expired(self) -> int:
        """Remove expired entries from the cache.

        Returns:
            Number of entries removed
        """
        async with self._lock:
            expired_keys = []
            current_time = time.time()

            for key, (_, expires_at) in self._cache.items():
                if current_time > expires_at:
                    expired_keys.append(key)

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        total_entries = len(self._cache)
        expired_count = 0
        current_time = time.time()

        for _, (_, expires_at) in self._cache.items():
            if current_time > expires_at:
                expired_count += 1

        return {
            "total_entries": total_entries,
            "expired_entries": expired_count,
            "active_entries": total_entries - expired_count,
            "default_ttl": self.default_ttl,
        }


# Global cache instances
api_cache = TTLCache(default_ttl=300)  # 5 minutes for API responses
voice_cache = TTLCache(default_ttl=3600)  # 1 hour for voice data
audio_cache = TTLCache(default_ttl=1800)  # 30 minutes for audio processing results


def cached_api_response(ttl: Optional[int] = None, cache_instance: Optional[TTLCache] = None):
    """Decorator to cache API responses.

    Args:
        ttl: Time-to-live in seconds (uses cache default if None)
        cache_instance: Cache instance to use (uses api_cache if None)

    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = cache_instance or api_cache

            # Generate cache key from function name and arguments
            key = f"{func.__name__}:{cache._make_key(*args, **kwargs)}"

            # Try to get from cache first
            cached_result = await cache.get(key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result

            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set(key, result, ttl)

            logger.debug(f"Cached result for {func.__name__}")
            return result

        return wrapper
    return decorator


def invalidate_cache(cache_instance: Optional[TTLCache] = None, pattern: Optional[str] = None):
    """Decorator to invalidate cache entries after function execution.

    Args:
        cache_instance: Cache instance to invalidate (invalidates all if None)
        pattern: Key pattern to match for invalidation (invalidates all if None)

    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            # Invalidate cache
            if cache_instance:
                if pattern:
                    # For pattern matching, we'd need a more sophisticated cache
                    # For now, clear the entire cache instance
                    await cache_instance.clear()
                else:
                    await cache_instance.clear()
            else:
                # Clear all caches
                await api_cache.clear()
                await voice_cache.clear()
                await audio_cache.clear()

            return result

        return wrapper
    return decorator


# Background task to clean up expired cache entries
async def cleanup_cache_task():
    """Background task to periodically clean up expired cache entries."""
    while True:
        try:
            await asyncio.sleep(300)  # Clean up every 5 minutes

            removed = await api_cache.cleanup_expired()
            removed += await voice_cache.cleanup_expired()
            removed += await audio_cache.cleanup_expired()

            if removed > 0:
                logger.info(f"Cache cleanup removed {removed} expired entries")

        except Exception as e:
            logger.error(f"Error during cache cleanup: {e}")


# Start cache cleanup task
def start_cache_cleanup():
    """Start the background cache cleanup task."""
    asyncio.create_task(cleanup_cache_task())
    logger.info("Cache cleanup task started")
