"""
Caching system for InnerBoard-local.
Provides efficient caching with TTL support and memory management.
"""

import time
import hashlib
from typing import Any, Dict, Optional, Callable, TypeVar, Generic
from threading import Lock
from app.config import config
from app.logging_config import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Thread-safe TTL (Time-To-Live) cache with automatic cleanup."""

    def __init__(self, default_ttl: int = 3600, max_size: int = 1000):
        """
        Initialize TTL cache.

        Args:
            default_ttl: Default TTL in seconds
            max_size: Maximum cache size before cleanup
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        key_data = str(args) + str(sorted(kwargs.items()))
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache."""
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if time.time() < entry["expires"]:
                    self._hits += 1
                    return entry["value"]
                else:
                    # Expired entry
                    del self._cache[key]

            self._misses += 1
            return default

    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL."""
        if ttl is None:
            ttl = self.default_ttl

        with self._lock:
            # Clean up if cache is getting too large
            if len(self._cache) >= self.max_size:
                self._cleanup_expired()

            if len(self._cache) >= self.max_size:
                # Remove oldest entries (simple LRU approximation)
                oldest_key = min(
                    self._cache.keys(), key=lambda k: self._cache[k]["expires"]
                )
                del self._cache[oldest_key]

            self._cache[key] = {
                "value": value,
                "expires": time.time() + ttl,
                "created": time.time(),
            }

    def delete(self, key: str) -> bool:
        """Delete key from cache."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def _cleanup_expired(self) -> int:
        """Remove expired entries."""
        current_time = time.time()
        expired_keys = [
            key
            for key, entry in self._cache.items()
            if current_time >= entry["expires"]
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests) if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": hit_rate,
                "total_requests": total_requests,
            }


class CachedFunction:
    """Decorator for caching function results."""

    def __init__(self, cache: TTLCache, ttl: Optional[int] = None):
        self.cache = cache
        self.ttl = ttl

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            # Create cache key
            key = self._make_func_key(func, args, kwargs)

            # Try to get from cache
            cached_result = self.cache.get(key)
            if cached_result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                return cached_result

            # Compute result
            logger.debug(f"Cache miss for {func.__name__}")
            result = func(*args, **kwargs)

            # Cache result
            self.cache.set(key, result, self.ttl)

            return result

        # Preserve function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        return wrapper

    def _make_func_key(self, func: Callable, args: tuple, kwargs: dict) -> str:
        """Generate cache key for function call."""
        key_parts = [func.__module__, func.__name__]
        key_parts.extend(str(arg) for arg in args)
        key_parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))
        key_data = "|".join(key_parts)
        return hashlib.md5(key_data.encode()).hexdigest()


class ConnectionPool:
    """Simple connection pool for managing resources."""

    def __init__(self, factory: Callable[[], Any], max_size: int = 10):
        self.factory = factory
        self.max_size = max_size
        self._pool = []
        self._lock = Lock()

    def get(self) -> Any:
        """Get a connection from the pool."""
        with self._lock:
            if self._pool:
                return self._pool.pop()
            else:
                return self.factory()

    def put(self, connection: Any) -> None:
        """Return a connection to the pool."""
        with self._lock:
            if len(self._pool) < self.max_size:
                self._pool.append(connection)

    def clear(self) -> None:
        """Clear all connections in the pool."""
        with self._lock:
            self._pool.clear()


# Global cache instances
response_cache = TTLCache(default_ttl=config.cache_ttl_seconds)
model_cache = TTLCache(default_ttl=1800)  # 30 minutes for models
reflection_cache = TTLCache(default_ttl=600)  # 10 minutes for reflections


def cached_response(ttl: Optional[int] = None):
    """Decorator for caching API responses."""
    return CachedFunction(response_cache, ttl)


def cached_model(ttl: Optional[int] = None):
    """Decorator for caching model operations."""
    return CachedFunction(model_cache, ttl)


def cached_reflection(ttl: Optional[int] = None):
    """Decorator for caching reflection operations."""
    return CachedFunction(reflection_cache, ttl)


class CacheManager:
    """Central cache management system."""

    def __init__(self):
        self.caches = {
            "response": response_cache,
            "model": model_cache,
            "reflection": reflection_cache,
        }

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all caches."""
        return {name: cache.stats() for name, cache in self.caches.items()}

    def clear_all(self) -> None:
        """Clear all caches."""
        for cache in self.caches.values():
            cache.clear()
        logger.info("All caches cleared")

    def cleanup(self) -> int:
        """Clean up expired entries in all caches."""
        total_cleaned = 0
        for name, cache in self.caches.items():
            # Access private method to clean up
            cleaned = cache._cleanup_expired()
            total_cleaned += cleaned

        if total_cleaned > 0:
            logger.info(f"Cleaned up {total_cleaned} expired cache entries")

        return total_cleaned


# Global cache manager
cache_manager = CacheManager()


def main():
    """Demonstrate caching functionality."""
    print("=== InnerBoard Cache System Demo ===")

    # Test TTL cache
    print("\n1. TTL Cache Test:")
    cache = TTLCache(default_ttl=2)  # 2 second TTL

    # Set and get values
    cache.set("test_key", "test_value")
    print(f"Immediate get: {cache.get('test_key')}")

    # Wait for expiration
    print("Waiting 3 seconds for expiration...")
    time.sleep(3)
    print(f"After expiration: {cache.get('test_key')}")

    # Test cache statistics
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    cache.get("key1")  # Hit
    cache.get("key3")  # Miss

    stats = cache.stats()
    print(f"Cache stats: {stats}")

    # Test cached function
    print("\n2. Cached Function Test:")

    @cached_response(ttl=5)
    def expensive_operation(x: int) -> int:
        print(f"Computing expensive operation for {x}")
        time.sleep(0.1)  # Simulate work
        return x * 2

    print("First call (should compute):")
    result1 = expensive_operation(5)

    print("Second call (should use cache):")
    result2 = expensive_operation(5)

    print(f"Results: {result1}, {result2}")

    # Test cache manager
    print("\n3. Cache Manager Stats:")
    cache_stats = cache_manager.get_stats()
    for cache_name, stats in cache_stats.items():
        print(
            f"{cache_name}: {stats['size']} entries, {stats['hit_rate']:.2%} hit rate"
        )

    print("\nCache demo complete!")


if __name__ == "__main__":
    main()
