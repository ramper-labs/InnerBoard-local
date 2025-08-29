"""
Tests for caching system.
"""

import pytest
import time
from unittest.mock import Mock, patch
from app.cache import (
    TTLCache,
    CachedFunction,
    ConnectionPool,
    cache_manager,
    cached_response,
    cached_model,
    cached_reflection,
)


class TestTTLCache:
    """Test TTL cache functionality."""

    def test_basic_cache_operations(self):
        """Test basic cache get/set operations."""
        cache = TTLCache(default_ttl=10)

        # Test set and get
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        # Test get with default
        assert cache.get("nonexistent", "default") == "default"

        # Test delete
        cache.set("key2", "value2")
        assert cache.delete("key2") is True
        assert cache.get("key2") is None
        assert cache.delete("nonexistent") is False

    def test_cache_expiration(self):
        """Test cache expiration."""
        cache = TTLCache(default_ttl=1)  # 1 second TTL

        # Set value
        cache.set("temp", "value")
        assert cache.get("temp") == "value"

        # Wait for expiration
        time.sleep(1.1)
        assert cache.get("temp") is None

    def test_cache_size_limits(self):
        """Test cache size limits and cleanup."""
        cache = TTLCache(max_size=3)

        # Fill cache
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

        # Add one more (should trigger cleanup and size limit)
        cache.set("key4", "value4")

        # Cache should have cleaned up expired entries and limited size
        stats = cache.stats()
        assert stats["size"] <= cache.max_size

    def test_cache_statistics(self):
        """Test cache statistics."""
        cache = TTLCache()

        # No requests yet
        stats = cache.stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0

        # Add some data and test
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        # Test hits and misses
        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("nonexistent")  # Miss
        cache.get("key2")  # Hit

        stats = cache.stats()
        assert stats["hits"] == 3
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.75
        assert stats["total_requests"] == 4

    def test_cache_clear(self):
        """Test cache clearing."""
        cache = TTLCache()

        cache.set("key1", "value1")
        cache.set("key2", "value2")

        assert cache.get("key1") == "value1"
        assert cache.get("key2") == "value2"

        # Clear cache
        cache.clear()

        assert cache.get("key1") is None
        assert cache.get("key2") is None

        stats = cache.stats()
        assert stats["size"] == 0
        assert stats["hits"] == 0  # Clear resets all counters
        assert (
            stats["misses"] == 2
        )  # We had 2 misses after clearing (trying to get non-existent keys)


class TestCachedFunction:
    """Test cached function decorator."""

    def test_cached_function_basic(self):
        """Test basic cached function functionality."""
        cache = TTLCache(default_ttl=10)

        call_count = 0

        @CachedFunction(cache, ttl=5)
        def expensive_function(x, y=10):
            nonlocal call_count
            call_count += 1
            return x * y

        # First call should execute function
        result1 = expensive_function(5, y=2)
        assert result1 == 10
        assert call_count == 1

        # Second call with same args should use cache
        result2 = expensive_function(5, y=2)
        assert result2 == 10
        assert call_count == 1  # Should not have increased

        # Different args should execute function again
        result3 = expensive_function(3, y=4)
        assert result3 == 12
        assert call_count == 2

    def test_cached_function_expiration(self):
        """Test cached function with expiration."""
        cache = TTLCache(default_ttl=1)

        call_count = 0

        @CachedFunction(cache, ttl=1)
        def test_func():
            nonlocal call_count
            call_count += 1
            return "result"

        # First call
        test_func()
        assert call_count == 1

        # Second call (should use cache)
        test_func()
        assert call_count == 1

        # Wait for expiration
        time.sleep(1.1)

        # Third call (should execute again)
        test_func()
        assert call_count == 2


class TestConnectionPool:
    """Test connection pool functionality."""

    def test_connection_pool_basic(self):
        """Test basic connection pool operations."""
        # Mock factory
        call_count = 0

        def mock_factory():
            nonlocal call_count
            call_count += 1
            return Mock()

        pool = ConnectionPool(mock_factory, max_size=3)

        # Get connections
        conn1 = pool.get()
        assert call_count == 1

        conn2 = pool.get()
        assert call_count == 2

        # Return connection
        pool.put(conn1)

        # Get again (should reuse)
        conn3 = pool.get()
        assert call_count == 2  # Should not have increased

        # Fill pool
        conn4 = pool.get()
        conn5 = pool.get()
        assert call_count == 4

        # Try to return when pool is full
        pool.put(conn4)  # Should be accepted
        pool.put(conn2)  # Should be accepted
        pool.put(conn3)  # Should be rejected (pool full)

    def test_connection_pool_clear(self):
        """Test connection pool clearing."""

        def mock_factory():
            return Mock()

        pool = ConnectionPool(mock_factory, max_size=2)

        # Add some connections
        pool.get()
        pool.get()

        # Clear pool
        pool.clear()

        # Should be able to get new connections
        conn = pool.get()
        assert conn is not None


class TestDecorators:
    """Test caching decorators."""

    def test_cached_response_decorator(self):
        """Test cached_response decorator."""
        call_count = 0

        @cached_response(ttl=5)
        def api_call(endpoint):
            nonlocal call_count
            call_count += 1
            return f"response_from_{endpoint}"

        # First call
        result1 = api_call("users")
        assert result1 == "response_from_users"
        assert call_count == 1

        # Second call (should use cache)
        result2 = api_call("users")
        assert result2 == "response_from_users"
        assert call_count == 1

    def test_cached_model_decorator(self):
        """Test cached_model decorator."""
        call_count = 0

        @cached_model(ttl=10)
        def load_model(model_name):
            nonlocal call_count
            call_count += 1
            return f"model_{model_name}_loaded"

        # First call
        result1 = load_model("llama3.1")
        assert result1 == "model_llama3.1_loaded"
        assert call_count == 1

        # Second call (should use cache)
        result2 = load_model("llama3.1")
        assert result2 == "model_llama3.1_loaded"
        assert call_count == 1

    def test_cached_reflection_decorator(self):
        """Test cached_reflection decorator."""
        call_count = 0

        @cached_reflection(ttl=30)
        def process_reflection(text):
            nonlocal call_count
            call_count += 1
            return f"processed_{hash(text)}"

        # First call
        result1 = process_reflection("test reflection")
        assert call_count == 1

        # Second call with same text (should use cache)
        result2 = process_reflection("test reflection")
        assert result1 == result2
        assert call_count == 1


class TestCacheManager:
    """Test cache manager functionality."""

    def test_cache_manager_stats(self):
        """Test cache manager statistics."""
        # Clear any existing data
        cache_manager.clear_all()

        # Add some data to different caches
        from app.cache import response_cache, model_cache

        response_cache.set("test_response", "response_data")
        model_cache.set("test_model", "model_data")

        stats = cache_manager.get_stats()

        assert "response" in stats
        assert "model" in stats
        assert "reflection" in stats

        assert stats["response"]["size"] >= 1
        assert stats["model"]["size"] >= 1

    def test_cache_manager_clear_all(self):
        """Test clearing all caches."""
        # Add data to caches
        from app.cache import response_cache, model_cache, reflection_cache

        response_cache.set("test1", "data1")
        model_cache.set("test2", "data2")
        reflection_cache.set("test3", "data3")

        # Verify data exists
        assert response_cache.get("test1") is not None
        assert model_cache.get("test2") is not None
        assert reflection_cache.get("test3") is not None

        # Clear all
        cache_manager.clear_all()

        # Verify data is gone
        assert response_cache.get("test1") is None
        assert model_cache.get("test2") is None
        assert reflection_cache.get("test3") is None

    def test_cache_manager_cleanup(self):
        """Test cache cleanup functionality."""
        from app.cache import response_cache

        # Add some data with short TTL
        response_cache.set("short", "data", ttl=1)
        response_cache.set("long", "data", ttl=60)

        # Wait for short TTL to expire
        time.sleep(1.1)

        # Run cleanup
        cleaned = cache_manager.cleanup()

        # Should have cleaned up at least one entry
        assert cleaned >= 1


class TestIntegration:
    """Integration tests for caching system."""

    def test_multi_cache_scenario(self):
        """Test multiple caches working together."""
        # Clear all caches
        cache_manager.clear_all()

        # Simulate a complex workflow with multiple cache types
        @cached_response(ttl=5)
        def fetch_user_data(user_id):
            return f"user_data_{user_id}"

        @cached_model(ttl=10)
        def load_analysis_model():
            return "analysis_model_loaded"

        @cached_reflection(ttl=15)
        def analyze_reflection(text):
            return f"analysis_of_{hash(text)}"

        # Execute workflow
        user_data = fetch_user_data("user123")
        model = load_analysis_model()
        analysis = analyze_reflection("test reflection")

        # Verify results
        assert user_data == "user_data_user123"
        assert model == "analysis_model_loaded"
        assert "analysis_of_" in analysis

        # Check cache stats
        stats = cache_manager.get_stats()
        assert stats["response"]["size"] >= 1
        assert stats["model"]["size"] >= 1
        assert stats["reflection"]["size"] >= 1

    def test_cache_performance_under_load(self):
        """Test cache performance under simulated load."""
        cache = TTLCache(max_size=100, default_ttl=60)

        # Simulate high-frequency cache operations
        for i in range(150):  # More than max_size
            cache.set(f"key_{i}", f"value_{i}")

        # Verify cache respects size limits
        stats = cache.stats()
        assert stats["size"] <= 100

        # Test retrieval performance
        start_time = time.time()
        for i in range(50):
            cache.get(f"key_{i}")

        end_time = time.time()
        retrieval_time = end_time - start_time

        # Should be very fast (less than 0.1 seconds for 50 operations)
        assert retrieval_time < 0.1


if __name__ == "__main__":
    pytest.main([__file__])
