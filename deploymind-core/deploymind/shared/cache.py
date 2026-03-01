"""Caching utilities for performance optimization."""

import json
import functools
from typing import Callable, Any, Optional
from datetime import timedelta
import hashlib

from deploymind.shared.secure_logging import get_logger

logger = get_logger(__name__)


def cache_key(*args, **kwargs) -> str:
    """Generate cache key from function arguments.

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        MD5 hash of arguments as cache key
    """
    # Create deterministic string from args
    key_parts = [str(arg) for arg in args]
    key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
    key_str = "|".join(key_parts)

    # Hash for consistent length
    return hashlib.md5(key_str.encode()).hexdigest()


def cached(
    ttl_seconds: int = 300,
    prefix: str = "cache",
    use_redis: bool = True
):
    """Decorator to cache function results.

    Args:
        ttl_seconds: Time to live in seconds (default: 300 = 5 minutes)
        prefix: Cache key prefix for namespacing
        use_redis: Whether to use Redis (falls back to in-memory if False)

    Example:
        @cached(ttl_seconds=60, prefix="deployment")
        def get_deployment(deployment_id):
            return expensive_operation(deployment_id)
    """
    def decorator(func: Callable) -> Callable:
        # In-memory cache fallback
        memory_cache = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{prefix}:{func.__name__}:{cache_key(*args, **kwargs)}"

            # Try Redis first if enabled
            if use_redis:
                try:
                    from deploymind.config.dependencies import container
                    redis_client = container.redis_client

                    # Try to get from Redis
                    cached_value = redis_client.get(key)
                    if cached_value is not None:
                        logger.debug(f"Cache HIT: {key}")
                        return json.loads(cached_value)

                except Exception as e:
                    logger.warning(f"Redis cache error: {e}, falling back to in-memory")

            # Check in-memory cache
            if key in memory_cache:
                logger.debug(f"Memory cache HIT: {key}")
                return memory_cache[key]

            # Cache miss - execute function
            logger.debug(f"Cache MISS: {key}")
            result = func(*args, **kwargs)

            # Store in cache
            try:
                if use_redis:
                    from deploymind.config.dependencies import container
                    redis_client = container.redis_client
                    redis_client.setex(key, ttl_seconds, json.dumps(result))
                else:
                    memory_cache[key] = result
            except Exception as e:
                logger.warning(f"Failed to cache result: {e}")
                # Store in memory as fallback
                memory_cache[key] = result

            return result

        # Add cache control methods
        def clear_cache():
            """Clear all cached results for this function."""
            memory_cache.clear()
            logger.info(f"Cleared cache for {func.__name__}")

        wrapper.clear_cache = clear_cache
        return wrapper

    return decorator


class CacheStats:
    """Track cache performance statistics."""

    def __init__(self):
        """Initialize cache statistics."""
        self.hits = 0
        self.misses = 0
        self.errors = 0

    def record_hit(self):
        """Record a cache hit."""
        self.hits += 1

    def record_miss(self):
        """Record a cache miss."""
        self.misses += 1

    def record_error(self):
        """Record a cache error."""
        self.errors += 1

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate.

        Returns:
            Hit rate as percentage (0-100)
        """
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    def reset(self):
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.errors = 0

    def __repr__(self) -> str:
        """String representation of cache stats."""
        return (
            f"CacheStats(hits={self.hits}, misses={self.misses}, "
            f"errors={self.errors}, hit_rate={self.hit_rate:.1f}%)"
        )


# Global cache stats instance
cache_stats = CacheStats()


def batch_operation(items: list, operation: Callable, batch_size: int = 100) -> list:
    """Process items in batches for better performance.

    Args:
        items: List of items to process
        operation: Function to apply to each batch
        batch_size: Number of items per batch

    Returns:
        List of results from all batches

    Example:
        results = batch_operation(
            items=deployment_ids,
            operation=lambda batch: repo.get_many(batch),
            batch_size=50
        )
    """
    results = []

    for i in range(0, len(items), batch_size):
        batch = items[i:i + batch_size]
        batch_results = operation(batch)
        results.extend(batch_results)

    return results
