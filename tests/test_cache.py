"""Tests for caching functionality."""

import time
from unittest.mock import patch

import pytest

from src.talk2me_ui.cache import (
    APICache,
    cached_api_response,
    get_cache_instance,
    start_cache_cleanup,
    voice_cache,
)


class TestAPICache:
    """Test cases for APICache class."""

    def test_cache_initialization(self):
        """Test APICache initialization."""
        cache = APICache(max_size=100, ttl=60)
        assert cache.max_size == 100
        assert cache.ttl == 60
        assert len(cache.cache) == 0

    def test_cache_set_and_get(self):
        """Test basic cache set and get operations."""
        cache = APICache()

        # Set a value
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"

        # Get non-existent key
        assert cache.get("non_existent") is None

    def test_cache_expiration(self):
        """Test cache expiration."""
        cache = APICache(ttl=1)  # 1 second TTL

        # Set a value
        cache.set("test_key", "test_value")
        assert cache.get("test_key") == "test_value"

        # Wait for expiration
        time.sleep(1.1)
        assert cache.get("test_key") is None

    def test_cache_max_size(self):
        """Test cache size limits."""
        cache = APICache(max_size=2)

        # Add items up to max size
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert len(cache.cache) == 2

        # Add one more - should evict oldest
        cache.set("key3", "value3")
        assert len(cache.cache) == 2
        assert cache.get("key1") is None  # Should be evicted
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

    def test_cache_cleanup(self):
        """Test cache cleanup."""
        cache = APICache(ttl=1)

        # Add some items
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Wait for expiration
        time.sleep(1.1)

        # Cleanup should remove expired items
        cache.cleanup()
        assert len(cache.cache) == 0

    def test_cache_clear(self):
        """Test cache clearing."""
        cache = APICache()

        cache.set("key1", "value1")
        cache.set("key2", "value2")
        assert len(cache.cache) == 2

        cache.clear()
        assert len(cache.cache) == 0


class TestCachedAPIResponse:
    """Test cases for cached_api_response decorator."""

    @pytest.mark.asyncio
    async def test_cached_response_decorator(self):
        """Test the cached_api_response decorator."""
        cache = APICache()

        @cached_api_response(cache_instance=cache, ttl=60)
        async def test_function(param: str):
            return {"result": param, "timestamp": time.time()}

        # First call
        result1 = await test_function("test")
        assert result1["result"] == "test"

        # Second call should return cached result
        result2 = await test_function("test")
        assert result2 == result1

        # Different parameter should not be cached
        result3 = await test_function("different")
        assert result3["result"] == "different"
        assert result3 != result1

    @pytest.mark.asyncio
    async def test_cached_response_expiration(self):
        """Test cached response expiration."""
        cache = APICache(ttl=1)

        @cached_api_response(cache_instance=cache, ttl=1)
        async def test_function():
            return {"timestamp": time.time()}

        # First call
        result1 = await test_function()

        # Wait for expiration
        time.sleep(1.1)

        # Second call should not be cached
        result2 = await test_function()
        assert result2["timestamp"] != result1["timestamp"]


class TestCacheManagement:
    """Test cache management functions."""

    def test_get_cache_instance(self):
        """Test getting cache instance."""
        cache = get_cache_instance("test_cache", max_size=50, ttl=30)
        assert isinstance(cache, APICache)
        assert cache.max_size == 50
        assert cache.ttl == 30

        # Same instance should be returned
        cache2 = get_cache_instance("test_cache")
        assert cache is cache2

    def test_voice_cache_instance(self):
        """Test voice cache instance."""
        assert isinstance(voice_cache, APICache)

    @patch("src.talk2me_ui.cache.asyncio.create_task")
    def test_start_cache_cleanup(self, mock_create_task):
        """Test starting cache cleanup."""
        start_cache_cleanup()
        mock_create_task.assert_called_once()


class TestCacheIntegration:
    """Integration tests for caching functionality."""

    @pytest.mark.asyncio
    async def test_end_to_end_caching(self):
        """Test end-to-end caching with FastAPI-like usage."""
        cache = APICache(ttl=5)

        # Simulate API endpoint with caching
        call_count = 0

        @cached_api_response(cache_instance=cache, ttl=5)
        async def mock_api_endpoint(user_id: int, category: str = "default"):
            nonlocal call_count
            call_count += 1
            return {
                "user_id": user_id,
                "category": category,
                "data": f"response_{call_count}",
                "cached": False,
            }

        # First call
        result1 = await mock_api_endpoint(123, "voices")
        assert call_count == 1
        assert result1["user_id"] == 123
        assert result1["category"] == "voices"

        # Second call with same parameters should be cached
        result2 = await mock_api_endpoint(123, "voices")
        assert call_count == 1  # Should not increment
        assert result2 == result1

        # Different parameters should not be cached
        result3 = await mock_api_endpoint(456, "voices")
        assert call_count == 2
        assert result3["user_id"] == 456

        # Same user, different category should not be cached
        result4 = await mock_api_endpoint(123, "sounds")
        assert call_count == 3
        assert result4["category"] == "sounds"
