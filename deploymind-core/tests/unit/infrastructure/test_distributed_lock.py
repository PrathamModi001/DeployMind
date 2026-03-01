"""Intensive tests for DistributedLock.

All Redis interactions are mocked — no real Redis required.
The Lua scripts are registered on the mock and their return values
are controlled directly.

Covers:
- acquire: SET NX PX called, returns True on success, False on failure
- release: Lua release script called, returns True/False correctly
- extend: Lua extend script called with correct key/args, returns True/False
- is_locked: EXISTS called, returns bool
- get_holder: GET called, decodes bytes, returns None if absent
- is_held_by_us: compares holder value to our token
- lock_name / lock_value properties
- locked() context manager: acquires + releases on success
- locked() context manager: raises LockAcquisitionError when unavailable
- locked() context manager: releases lock even if body raises exception
- locked() context manager: retries within timeout_ms window
- locked() with timeout_ms=None makes only one attempt
- LockAcquisitionError is a RuntimeError subclass
"""

from __future__ import annotations

import threading
import time
from contextlib import suppress
from unittest.mock import MagicMock, call, patch

import pytest

from deploymind.infrastructure.queue.distributed_lock import (
    DistributedLock,
    LockAcquisitionError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

LOCK_NAME = "deploymind:deploy:test-repo"
LOCK_VALUE = "fixed-token-for-tests"


@pytest.fixture
def mock_redis():
    r = MagicMock()
    # register_script returns a callable mock
    script_mock = MagicMock()
    r.register_script.return_value = script_mock
    return r


@pytest.fixture
def lock(mock_redis):
    return DistributedLock(
        redis_client=mock_redis,
        lock_name=LOCK_NAME,
        ttl_ms=5000,
        lock_value=LOCK_VALUE,
    )


# ===========================================================================
# LockAcquisitionError
# ===========================================================================

class TestLockAcquisitionError:
    def test_is_runtime_error(self):
        err = LockAcquisitionError("oh no")
        assert isinstance(err, RuntimeError)

    def test_message_preserved(self):
        err = LockAcquisitionError("lock busy")
        assert "lock busy" in str(err)


# ===========================================================================
# acquire
# ===========================================================================

class TestAcquire:
    def test_set_called_with_nx_and_px(self, lock, mock_redis):
        mock_redis.set.return_value = True
        lock.acquire()
        mock_redis.set.assert_called_once_with(
            LOCK_NAME, LOCK_VALUE, px=5000, nx=True
        )

    def test_returns_true_on_success(self, lock, mock_redis):
        mock_redis.set.return_value = True
        assert lock.acquire() is True

    def test_returns_false_on_failure(self, lock, mock_redis):
        mock_redis.set.return_value = None  # Redis returns None when NX fails
        assert lock.acquire() is False

    def test_returns_false_when_already_held(self, lock, mock_redis):
        mock_redis.set.side_effect = [True, None]  # first succeeds, second fails
        lock.acquire()
        assert lock.acquire() is False


# ===========================================================================
# release
# ===========================================================================

class TestRelease:
    def test_release_script_called(self, lock, mock_redis):
        release_script = mock_redis.register_script.return_value
        release_script.return_value = 1
        lock.release()
        release_script.assert_called_once_with(
            keys=[LOCK_NAME], args=[LOCK_VALUE]
        )

    def test_returns_true_when_released(self, lock, mock_redis):
        release_script = mock_redis.register_script.return_value
        release_script.return_value = 1
        assert lock.release() is True

    def test_returns_false_when_not_held(self, lock, mock_redis):
        release_script = mock_redis.register_script.return_value
        release_script.return_value = 0
        assert lock.release() is False

    def test_release_does_not_delete_others_lock(self, lock, mock_redis):
        # The Lua script should be called — it handles the check atomically.
        # Returning 0 simulates "value mismatch — nothing deleted".
        release_script = mock_redis.register_script.return_value
        release_script.return_value = 0
        result = lock.release()
        assert result is False


# ===========================================================================
# extend
# ===========================================================================

class TestExtend:
    def test_extend_script_called(self, lock, mock_redis):
        extend_script = mock_redis.register_script.return_value
        extend_script.return_value = 1
        lock.extend()
        extend_script.assert_called_once_with(
            keys=[LOCK_NAME], args=[LOCK_VALUE, "5000"]
        )

    def test_extend_with_custom_ttl(self, lock, mock_redis):
        extend_script = mock_redis.register_script.return_value
        extend_script.return_value = 1
        lock.extend(extra_ms=10_000)
        call_args = extend_script.call_args.kwargs
        assert "10000" in call_args["args"]

    def test_returns_true_on_success(self, lock, mock_redis):
        mock_redis.register_script.return_value.return_value = 1
        assert lock.extend() is True

    def test_returns_false_when_not_held(self, lock, mock_redis):
        mock_redis.register_script.return_value.return_value = 0
        assert lock.extend() is False


# ===========================================================================
# is_locked
# ===========================================================================

class TestIsLocked:
    def test_returns_true_when_key_exists(self, lock, mock_redis):
        mock_redis.exists.return_value = 1
        assert lock.is_locked() is True

    def test_returns_false_when_key_absent(self, lock, mock_redis):
        mock_redis.exists.return_value = 0
        assert lock.is_locked() is False

    def test_exists_called_with_correct_key(self, lock, mock_redis):
        mock_redis.exists.return_value = 0
        lock.is_locked()
        mock_redis.exists.assert_called_once_with(LOCK_NAME)


# ===========================================================================
# get_holder / is_held_by_us
# ===========================================================================

class TestGetHolder:
    def test_returns_none_when_absent(self, lock, mock_redis):
        mock_redis.get.return_value = None
        assert lock.get_holder() is None

    def test_decodes_bytes(self, lock, mock_redis):
        mock_redis.get.return_value = b"some-token"
        assert lock.get_holder() == "some-token"

    def test_returns_string_as_is(self, lock, mock_redis):
        mock_redis.get.return_value = "string-token"
        assert lock.get_holder() == "string-token"

    def test_is_held_by_us_true(self, lock, mock_redis):
        mock_redis.get.return_value = LOCK_VALUE.encode()
        assert lock.is_held_by_us() is True

    def test_is_held_by_us_false_when_different_value(self, lock, mock_redis):
        mock_redis.get.return_value = b"someone-elses-token"
        assert lock.is_held_by_us() is False

    def test_is_held_by_us_false_when_absent(self, lock, mock_redis):
        mock_redis.get.return_value = None
        assert lock.is_held_by_us() is False


# ===========================================================================
# Properties
# ===========================================================================

class TestProperties:
    def test_lock_name(self, lock):
        assert lock.lock_name == LOCK_NAME

    def test_lock_value(self, lock):
        assert lock.lock_value == LOCK_VALUE

    def test_auto_generated_lock_value_is_uuid(self, mock_redis):
        lock = DistributedLock(mock_redis, "some-lock")
        assert len(lock.lock_value) == 36  # UUID4 length


# ===========================================================================
# locked() context manager
# ===========================================================================

class TestLockedContextManager:
    def test_acquires_and_releases_on_success(self, lock, mock_redis):
        mock_redis.set.return_value = True
        release_script = mock_redis.register_script.return_value
        release_script.return_value = 1

        with lock.locked():
            pass

        mock_redis.set.assert_called_once()  # acquire
        release_script.assert_called()        # release

    def test_raises_when_cannot_acquire(self, lock, mock_redis):
        mock_redis.set.return_value = None  # always fails

        with pytest.raises(LockAcquisitionError):
            with lock.locked(timeout_ms=None):
                pass  # should never reach here

    def test_releases_even_when_body_raises(self, lock, mock_redis):
        mock_redis.set.return_value = True
        release_script = mock_redis.register_script.return_value
        release_script.return_value = 1

        with suppress(ValueError):
            with lock.locked():
                raise ValueError("boom")

        release_script.assert_called()

    def test_retries_within_timeout(self, lock, mock_redis):
        # First call fails, second succeeds
        mock_redis.set.side_effect = [None, True]
        release_script = mock_redis.register_script.return_value
        release_script.return_value = 1

        with lock.locked(timeout_ms=500, retry_interval_ms=10):
            pass

        assert mock_redis.set.call_count == 2

    def test_raises_after_timeout_exhausted(self, lock, mock_redis):
        mock_redis.set.return_value = None  # always fails

        with pytest.raises(LockAcquisitionError, match=LOCK_NAME):
            with lock.locked(timeout_ms=50, retry_interval_ms=10):
                pass

    def test_single_attempt_when_timeout_is_none(self, lock, mock_redis):
        mock_redis.set.return_value = None  # fails

        with pytest.raises(LockAcquisitionError):
            with lock.locked(timeout_ms=None):
                pass

        assert mock_redis.set.call_count == 1

    def test_error_message_contains_lock_name(self, lock, mock_redis):
        mock_redis.set.return_value = None

        with pytest.raises(LockAcquisitionError) as exc_info:
            with lock.locked(timeout_ms=None):
                pass

        assert LOCK_NAME in str(exc_info.value)

    def test_lock_not_held_after_context_exits(self, lock, mock_redis):
        mock_redis.set.return_value = True
        release_script = mock_redis.register_script.return_value
        release_script.return_value = 1

        with lock.locked():
            pass

        # After the with block, release should have been called
        release_script.assert_called()
