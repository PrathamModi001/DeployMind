"""Unit tests for caching utilities."""

import pytest
import time
from unittest.mock import Mock, patch

from deploymind.shared.cache import (
    cache_key,
    cached,
    CacheStats,
    batch_operation
)


class TestCacheKey:
    """Test cache key generation."""

    def test_cache_key_with_args(self):
        """Test cache key generation with positional arguments."""
        key1 = cache_key("arg1", "arg2", "arg3")
        key2 = cache_key("arg1", "arg2", "arg3")

        assert key1 == key2
        assert len(key1) == 32  # MD5 hash length

    def test_cache_key_with_kwargs(self):
        """Test cache key generation with keyword arguments."""
        key1 = cache_key(name="test", value=123)
        key2 = cache_key(name="test", value=123)

        assert key1 == key2

    def test_cache_key_different_args(self):
        """Test different arguments produce different keys."""
        key1 = cache_key("arg1")
        key2 = cache_key("arg2")

        assert key1 != key2

    def test_cache_key_kwargs_order_independent(self):
        """Test kwargs order doesn't affect key."""
        key1 = cache_key(a=1, b=2, c=3)
        key2 = cache_key(c=3, b=2, a=1)

        assert key1 == key2


class TestCachedDecorator:
    """Test cached decorator."""

    def test_cache_hit_in_memory(self):
        """Test cache hit with in-memory caching."""
        call_count = 0

        @cached(ttl_seconds=60, use_redis=False)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Not called again

    def test_cache_miss_different_args(self):
        """Test cache miss with different arguments."""
        call_count = 0

        @cached(ttl_seconds=60, use_redis=False)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result1 = expensive_function(5)
        result2 = expensive_function(10)

        assert result1 == 10
        assert result2 == 20
        assert call_count == 2  # Called twice for different args

    def test_cache_with_kwargs(self):
        """Test caching with keyword arguments."""
        call_count = 0

        @cached(ttl_seconds=60, use_redis=False)
        def expensive_function(x, multiplier=2):
            nonlocal call_count
            call_count += 1
            return x * multiplier

        result1 = expensive_function(5, multiplier=3)
        result2 = expensive_function(5, multiplier=3)

        assert result1 == 15
        assert result2 == 15
        assert call_count == 1  # Cached

    def test_cache_clear(self):
        """Test cache clearing."""
        call_count = 0

        @cached(ttl_seconds=60, use_redis=False)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        expensive_function(5)
        assert call_count == 1

        # Second call (cached)
        expensive_function(5)
        assert call_count == 1

        # Clear cache
        expensive_function.clear_cache()

        # Third call (cache cleared, should execute)
        expensive_function(5)
        assert call_count == 2

    def test_cache_with_prefix(self):
        """Test cache with custom prefix."""
        @cached(ttl_seconds=60, prefix="test_prefix", use_redis=False)
        def func1(x):
            return x

        @cached(ttl_seconds=60, prefix="other_prefix", use_redis=False)
        def func2(x):
            return x

        # Both should work independently
        result1 = func1(5)
        result2 = func2(5)

        assert result1 == 5
        assert result2 == 5

    def test_cache_preserves_function_name(self):
        """Test decorator preserves function name."""
        @cached(ttl_seconds=60, use_redis=False)
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    @patch('config.dependencies.container')
    def test_cache_with_redis(self, mock_container):
        """Test caching with Redis."""
        mock_redis = Mock()
        mock_redis.get.return_value = None  # Cache miss
        mock_redis.setex.return_value = True
        mock_container.redis_client = mock_redis

        call_count = 0

        @cached(ttl_seconds=60, use_redis=True)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        result = expensive_function(5)

        assert result == 10
        assert call_count == 1
        # Should have tried to get from Redis
        assert mock_redis.get.called

    @patch('config.dependencies.container')
    def test_cache_redis_fallback(self, mock_container):
        """Test fallback to in-memory when Redis fails."""
        mock_redis = Mock()
        mock_redis.get.side_effect = Exception("Redis error")
        mock_redis.setex.side_effect = Exception("Redis error")
        mock_container.redis_client = mock_redis

        call_count = 0

        @cached(ttl_seconds=60, use_redis=True)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # Second call should use in-memory cache
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Still cached in memory


class TestCacheStats:
    """Test CacheStats class."""

    def test_initial_stats(self):
        """Test initial cache statistics."""
        stats = CacheStats()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.errors == 0
        assert stats.hit_rate == 0.0

    def test_record_hits_and_misses(self):
        """Test recording hits and misses."""
        stats = CacheStats()

        stats.record_hit()
        stats.record_hit()
        stats.record_miss()

        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.hit_rate == pytest.approx(66.67, rel=0.1)

    def test_record_errors(self):
        """Test recording errors."""
        stats = CacheStats()

        stats.record_error()
        stats.record_error()

        assert stats.errors == 2

    def test_reset_stats(self):
        """Test resetting statistics."""
        stats = CacheStats()

        stats.record_hit()
        stats.record_miss()
        stats.record_error()

        stats.reset()

        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.errors == 0

    def test_stats_repr(self):
        """Test string representation."""
        stats = CacheStats()
        stats.record_hit()
        stats.record_miss()

        repr_str = repr(stats)

        assert "hits=1" in repr_str
        assert "misses=1" in repr_str
        assert "hit_rate=" in repr_str


class TestBatchOperation:
    """Test batch operation utility."""

    def test_batch_operation_basic(self):
        """Test basic batch processing."""
        items = list(range(10))

        def process_batch(batch):
            return [x * 2 for x in batch]

        results = batch_operation(items, process_batch, batch_size=3)

        assert len(results) == 10
        assert results == [0, 2, 4, 6, 8, 10, 12, 14, 16, 18]

    def test_batch_operation_exact_batches(self):
        """Test batch processing with exact batch sizes."""
        items = list(range(10))
        batches_processed = []

        def process_batch(batch):
            batches_processed.append(len(batch))
            return [x * 2 for x in batch]

        results = batch_operation(items, process_batch, batch_size=5)

        assert len(results) == 10
        assert batches_processed == [5, 5]  # Two equal batches

    def test_batch_operation_uneven_batches(self):
        """Test batch processing with uneven batch sizes."""
        items = list(range(10))
        batches_processed = []

        def process_batch(batch):
            batches_processed.append(len(batch))
            return [x * 2 for x in batch]

        results = batch_operation(items, process_batch, batch_size=3)

        assert len(results) == 10
        assert batches_processed == [3, 3, 3, 1]  # Last batch is smaller

    def test_batch_operation_single_batch(self):
        """Test batch processing when all items fit in one batch."""
        items = list(range(5))

        def process_batch(batch):
            return [x * 2 for x in batch]

        results = batch_operation(items, process_batch, batch_size=10)

        assert len(results) == 5
        assert results == [0, 2, 4, 6, 8]

    def test_batch_operation_empty_list(self):
        """Test batch processing with empty list."""
        items = []

        def process_batch(batch):
            return [x * 2 for x in batch]

        results = batch_operation(items, process_batch, batch_size=5)

        assert len(results) == 0
        assert results == []
