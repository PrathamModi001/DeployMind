"""Redis-backed distributed lock.

Implements the single-instance Redlock pattern for environments where one
Redis node is sufficient.  For multi-node HA use the full Redlock algorithm.

Acquire:
    ``SET lock_key lock_value NX PX ttl_ms``
    Returns True only if the key did NOT previously exist.

Release (atomic via Lua):
    Only delete the key if its value matches our ``lock_value``.
    This prevents a slow worker from deleting another worker's lock.

Extend:
    Refresh the TTL of an already-held lock (heartbeat pattern).

Usage::

    lock = DistributedLock(redis_client, "deploymind:deploy:myrepo")

    if lock.acquire():
        try:
            do_work()
        finally:
            lock.release()

    # or as a context manager:
    with lock.locked(timeout_ms=30_000):
        do_work()
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator

import redis


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class LockAcquisitionError(RuntimeError):
    """Raised when a distributed lock cannot be acquired."""


# ---------------------------------------------------------------------------
# Lua scripts (evaluated atomically by Redis)
# ---------------------------------------------------------------------------

# Release: delete the key only when the stored value matches our token.
_LUA_RELEASE = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
"""

# Extend: refresh TTL only when the stored value matches our token.
_LUA_EXTEND = """
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("PEXPIRE", KEYS[1], ARGV[2])
else
    return 0
end
"""


# ---------------------------------------------------------------------------
# Lock implementation
# ---------------------------------------------------------------------------


class DistributedLock:
    """Distributed mutex backed by a single Redis instance.

    Args:
        redis_client: A ``redis.Redis`` connection.
        lock_name: Unique name for this lock (used as the Redis key).
        ttl_ms: Time-to-live in milliseconds.  The lock auto-expires if the
            holder crashes.  Choose a value longer than your typical critical
            section but short enough to bound the failure window.
        lock_value: Opaque token stored in the lock key.  Defaults to a UUIDv4.
            Override in tests for determinism.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        lock_name: str,
        ttl_ms: int = 30_000,
        lock_value: str | None = None,
    ) -> None:
        self._r = redis_client
        self._key = lock_name
        self._ttl_ms = ttl_ms
        self._value = lock_value or str(uuid.uuid4())

        # Register Lua scripts for atomic execution
        self._release_script: Any = self._r.register_script(_LUA_RELEASE)
        self._extend_script: Any = self._r.register_script(_LUA_EXTEND)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def acquire(self) -> bool:
        """Try to acquire the lock.

        Returns:
            True if the lock was acquired; False if it was already held.
        """
        result = self._r.set(
            self._key,
            self._value,
            px=self._ttl_ms,
            nx=True,
        )
        return result is True

    def release(self) -> bool:
        """Release the lock if we still hold it.

        Returns:
            True if the lock was released; False if someone else held it
            (or it had already expired).
        """
        result = self._release_script(keys=[self._key], args=[self._value])
        return int(result) == 1

    def extend(self, extra_ms: int | None = None) -> bool:
        """Refresh the lock's TTL (heartbeat).

        Useful when a critical section might run longer than ``ttl_ms``.

        Args:
            extra_ms: New TTL in milliseconds.  Defaults to the original ``ttl_ms``.

        Returns:
            True if the TTL was successfully extended; False if the lock
            was not held by us (expired or stolen).
        """
        new_ttl = extra_ms if extra_ms is not None else self._ttl_ms
        result = self._extend_script(
            keys=[self._key],
            args=[self._value, str(new_ttl)],
        )
        return int(result) == 1

    def is_locked(self) -> bool:
        """Return True if the lock key exists (held by anyone)."""
        return self._r.exists(self._key) == 1

    def get_holder(self) -> str | None:
        """Return the lock value (token) of the current holder, or None."""
        raw = self._r.get(self._key)
        if raw is None:
            return None
        return raw.decode() if isinstance(raw, bytes) else raw

    def is_held_by_us(self) -> bool:
        """Return True if this instance currently holds the lock."""
        return self.get_holder() == self._value

    @property
    def lock_name(self) -> str:
        return self._key

    @property
    def lock_value(self) -> str:
        return self._value

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    @contextmanager
    def locked(
        self,
        timeout_ms: int | None = None,
        retry_interval_ms: int = 50,
    ) -> Iterator[None]:
        """Context manager that acquires the lock or raises LockAcquisitionError.

        Args:
            timeout_ms: Total time in milliseconds to keep retrying before
                raising.  If None, only a single attempt is made.
            retry_interval_ms: Milliseconds between retries.

        Raises:
            LockAcquisitionError: If the lock cannot be acquired within timeout.

        Usage::

            with lock.locked(timeout_ms=5000):
                critical_section()
        """
        import time

        deadline = (time.monotonic() + timeout_ms / 1000.0) if timeout_ms else None
        sleep_s = retry_interval_ms / 1000.0

        while True:
            if self.acquire():
                break
            if deadline is None or time.monotonic() >= deadline:
                raise LockAcquisitionError(
                    f"Could not acquire lock '{self._key}' "
                    f"(timeout_ms={timeout_ms})"
                )
            time.sleep(sleep_s)

        try:
            yield
        finally:
            self.release()


# ---------------------------------------------------------------------------
# Type alias for the Any annotation used inside __init__
# ---------------------------------------------------------------------------
from typing import Any  # noqa: E402 — placed at end to avoid circular confusion
