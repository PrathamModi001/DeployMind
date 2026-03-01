"""Intensive tests for DeploymentQueue.

All Redis calls are mocked — no real Redis required.

Covers:
- DeploymentJob: serialization round-trip, from_json, from_dict, to_json, defaults
- enqueue: rpush called, job_id returned, auto-generates job_id when empty
- dequeue: brpoplpush called, returns DeploymentJob, records timestamp key,
  returns None on timeout (None from brpoplpush), corrupt JSON skipped
- ack: lrem called, timestamp key deleted, returns True/False correctly
- nack: atomic pipeline — lrem + rpush to dead-letter + delete ts key
- queue_depth / processing_depth / dead_letter_depth: llen delegation
- get_processing_jobs: lrange + parse, handles corrupt JSON entries gracefully
- requeue_stale: moves old jobs back to queue, skips fresh jobs, handles missing ts
- clear: deletes all three lists
"""

from __future__ import annotations

import json
import time
import uuid
from unittest.mock import MagicMock, call, patch

import pytest

from deploymind.infrastructure.queue.deployment_queue import (
    DeploymentJob,
    DeploymentQueue,
    _DEAD_LETTER_KEY,
    _PROCESSING_KEY,
    _PROCESSING_TS_PREFIX,
    _QUEUE_KEY,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_redis():
    r = MagicMock()
    # pipeline() returns a context that accumulates calls then executes
    pipe = MagicMock()
    r.pipeline.return_value = pipe
    pipe.__enter__ = MagicMock(return_value=pipe)
    pipe.__exit__ = MagicMock(return_value=False)
    return r


@pytest.fixture
def queue(mock_redis):
    return DeploymentQueue(mock_redis, block_timeout=1)


def _make_job(**kwargs) -> DeploymentJob:
    defaults = dict(
        job_id=str(uuid.uuid4()),
        repository="owner/repo",
        branch="main",
        commit_sha="abc123",
        triggered_by="pusher",
        priority=5,
        created_at=time.time(),
        metadata={},
    )
    defaults.update(kwargs)
    return DeploymentJob(**defaults)


# ===========================================================================
# DeploymentJob — unit tests
# ===========================================================================

class TestDeploymentJob:
    def test_to_json_round_trip(self):
        job = _make_job()
        restored = DeploymentJob.from_json(job.to_json())
        assert restored.job_id == job.job_id
        assert restored.repository == job.repository
        assert restored.branch == job.branch
        assert restored.commit_sha == job.commit_sha
        assert restored.triggered_by == job.triggered_by
        assert restored.priority == job.priority

    def test_from_json_bytes(self):
        job = _make_job()
        raw_bytes = job.to_json().encode("utf-8")
        restored = DeploymentJob.from_json(raw_bytes)
        assert restored.job_id == job.job_id

    def test_from_dict(self):
        job = _make_job(repository="acme/api")
        restored = DeploymentJob.from_dict({
            "job_id": job.job_id,
            "repository": "acme/api",
            "branch": job.branch,
            "commit_sha": job.commit_sha,
            "triggered_by": job.triggered_by,
            "priority": job.priority,
            "created_at": job.created_at,
            "metadata": {},
        })
        assert restored.repository == "acme/api"

    def test_default_job_id_generated(self):
        job = DeploymentJob()
        assert job.job_id  # non-empty

    def test_default_created_at_is_recent(self):
        before = time.time()
        job = DeploymentJob()
        after = time.time()
        assert before <= job.created_at <= after

    def test_metadata_default_is_empty_dict(self):
        job = DeploymentJob()
        assert job.metadata == {}

    def test_metadata_preserved_through_serialization(self):
        job = _make_job(metadata={"pr": 42, "env": "staging"})
        restored = DeploymentJob.from_json(job.to_json())
        assert restored.metadata == {"pr": 42, "env": "staging"}

    def test_to_json_is_valid_json(self):
        job = _make_job()
        parsed = json.loads(job.to_json())
        assert parsed["repository"] == job.repository

    def test_priority_stored_correctly(self):
        job = _make_job(priority=1)
        restored = DeploymentJob.from_json(job.to_json())
        assert restored.priority == 1


# ===========================================================================
# enqueue
# ===========================================================================

class TestEnqueue:
    def test_rpush_called_with_queue_key(self, queue, mock_redis):
        job = _make_job()
        queue.enqueue(job)
        mock_redis.rpush.assert_called_once()
        args = mock_redis.rpush.call_args.args
        assert args[0] == _QUEUE_KEY

    def test_rpush_payload_is_valid_json(self, queue, mock_redis):
        job = _make_job()
        queue.enqueue(job)
        payload = mock_redis.rpush.call_args.args[1]
        parsed = json.loads(payload)
        assert parsed["job_id"] == job.job_id

    def test_returns_job_id(self, queue, mock_redis):
        job = _make_job()
        result = queue.enqueue(job)
        assert result == job.job_id

    def test_auto_generates_job_id_when_empty(self, queue, mock_redis):
        job = _make_job(job_id="")
        returned_id = queue.enqueue(job)
        assert returned_id  # not empty
        assert len(returned_id) == 36  # UUID length


# ===========================================================================
# dequeue
# ===========================================================================

class TestDequeue:
    def test_brpoplpush_called_correctly(self, queue, mock_redis):
        job = _make_job()
        mock_redis.brpoplpush.return_value = job.to_json().encode()
        queue.dequeue()
        mock_redis.brpoplpush.assert_called_once_with(
            _QUEUE_KEY, _PROCESSING_KEY, timeout=1
        )

    def test_returns_deserialized_job(self, queue, mock_redis):
        job = _make_job(repository="acme/api")
        mock_redis.brpoplpush.return_value = job.to_json().encode()
        result = queue.dequeue()
        assert result is not None
        assert result.repository == "acme/api"

    def test_returns_none_on_timeout(self, queue, mock_redis):
        mock_redis.brpoplpush.return_value = None
        result = queue.dequeue()
        assert result is None

    def test_records_processing_timestamp(self, queue, mock_redis):
        job = _make_job()
        mock_redis.brpoplpush.return_value = job.to_json().encode()
        queue.dequeue()
        mock_redis.set.assert_called_once()
        key_arg = mock_redis.set.call_args.args[0]
        assert job.job_id in key_arg
        assert _PROCESSING_TS_PREFIX in key_arg

    def test_timestamp_has_expiry(self, queue, mock_redis):
        job = _make_job()
        mock_redis.brpoplpush.return_value = job.to_json().encode()
        queue.dequeue()
        call_kwargs = mock_redis.set.call_args.kwargs
        assert "ex" in call_kwargs


# ===========================================================================
# ack
# ===========================================================================

class TestAck:
    def test_lrem_called_with_processing_key(self, queue, mock_redis):
        job = _make_job()
        mock_redis.lrem.return_value = 1
        queue.ack(job)
        mock_redis.lrem.assert_called_once()
        args = mock_redis.lrem.call_args.args
        assert args[0] == _PROCESSING_KEY

    def test_timestamp_key_deleted(self, queue, mock_redis):
        job = _make_job()
        mock_redis.lrem.return_value = 1
        queue.ack(job)
        mock_redis.delete.assert_called_once_with(
            f"{_PROCESSING_TS_PREFIX}{job.job_id}"
        )

    def test_returns_true_when_removed(self, queue, mock_redis):
        job = _make_job()
        mock_redis.lrem.return_value = 1
        assert queue.ack(job) is True

    def test_returns_false_when_not_found(self, queue, mock_redis):
        job = _make_job()
        mock_redis.lrem.return_value = 0
        assert queue.ack(job) is False


# ===========================================================================
# nack
# ===========================================================================

class TestNack:
    def test_nack_uses_pipeline(self, queue, mock_redis):
        job = _make_job()
        pipe = mock_redis.pipeline.return_value
        queue.nack(job)
        mock_redis.pipeline.assert_called_once()
        pipe.execute.assert_called_once()

    def test_nack_removes_from_processing(self, queue, mock_redis):
        job = _make_job()
        pipe = mock_redis.pipeline.return_value
        queue.nack(job)
        pipe.lrem.assert_called_once_with(_PROCESSING_KEY, 1, job.to_json())

    def test_nack_pushes_to_dead_letter(self, queue, mock_redis):
        job = _make_job()
        pipe = mock_redis.pipeline.return_value
        queue.nack(job)
        pipe.rpush.assert_called_once_with(_DEAD_LETTER_KEY, job.to_json())

    def test_nack_deletes_timestamp_key(self, queue, mock_redis):
        job = _make_job()
        pipe = mock_redis.pipeline.return_value
        queue.nack(job)
        pipe.delete.assert_called_once_with(f"{_PROCESSING_TS_PREFIX}{job.job_id}")


# ===========================================================================
# Depth queries
# ===========================================================================

class TestDepthQueries:
    def test_queue_depth(self, queue, mock_redis):
        mock_redis.llen.return_value = 7
        assert queue.queue_depth() == 7
        mock_redis.llen.assert_called_once_with(_QUEUE_KEY)

    def test_processing_depth(self, queue, mock_redis):
        mock_redis.llen.return_value = 3
        assert queue.processing_depth() == 3
        mock_redis.llen.assert_called_once_with(_PROCESSING_KEY)

    def test_dead_letter_depth(self, queue, mock_redis):
        mock_redis.llen.return_value = 1
        assert queue.dead_letter_depth() == 1
        mock_redis.llen.assert_called_once_with(_DEAD_LETTER_KEY)


# ===========================================================================
# get_processing_jobs
# ===========================================================================

class TestGetProcessingJobs:
    def test_returns_deserialized_jobs(self, queue, mock_redis):
        jobs = [_make_job(branch=f"branch-{i}") for i in range(3)]
        mock_redis.lrange.return_value = [j.to_json().encode() for j in jobs]
        result = queue.get_processing_jobs()
        assert len(result) == 3
        branches = {j.branch for j in result}
        assert branches == {"branch-0", "branch-1", "branch-2"}

    def test_lrange_uses_processing_key(self, queue, mock_redis):
        mock_redis.lrange.return_value = []
        queue.get_processing_jobs()
        mock_redis.lrange.assert_called_once_with(_PROCESSING_KEY, 0, -1)

    def test_empty_list_returns_empty(self, queue, mock_redis):
        mock_redis.lrange.return_value = []
        assert queue.get_processing_jobs() == []

    def test_corrupt_entry_skipped(self, queue, mock_redis):
        valid_job = _make_job()
        mock_redis.lrange.return_value = [
            b"not-valid-json",
            valid_job.to_json().encode(),
        ]
        result = queue.get_processing_jobs()
        assert len(result) == 1
        assert result[0].job_id == valid_job.job_id


# ===========================================================================
# requeue_stale
# ===========================================================================

class TestRequeueStale:
    def test_stale_job_requeued(self, queue, mock_redis):
        job = _make_job()
        mock_redis.lrange.return_value = [job.to_json().encode()]
        stale_ts = str(time.time() - 600)  # 10 minutes ago
        mock_redis.get.return_value = stale_ts.encode()
        pipe = mock_redis.pipeline.return_value

        count = queue.requeue_stale(max_age_seconds=300.0)

        assert count == 1
        pipe.lrem.assert_called_once()
        pipe.rpush.assert_called_once()
        pipe.execute.assert_called_once()

    def test_fresh_job_not_requeued(self, queue, mock_redis):
        job = _make_job()
        mock_redis.lrange.return_value = [job.to_json().encode()]
        fresh_ts = str(time.time() - 10)  # 10 seconds ago
        mock_redis.get.return_value = fresh_ts.encode()
        pipe = mock_redis.pipeline.return_value

        count = queue.requeue_stale(max_age_seconds=300.0)

        assert count == 0
        pipe.lrem.assert_not_called()

    def test_job_without_timestamp_skipped(self, queue, mock_redis):
        job = _make_job()
        mock_redis.lrange.return_value = [job.to_json().encode()]
        mock_redis.get.return_value = None  # no timestamp recorded
        pipe = mock_redis.pipeline.return_value

        count = queue.requeue_stale(max_age_seconds=300.0)

        assert count == 0

    def test_multiple_jobs_some_stale(self, queue, mock_redis):
        fresh = _make_job(job_id="fresh-id")
        stale = _make_job(job_id="stale-id")
        mock_redis.lrange.return_value = [
            fresh.to_json().encode(),
            stale.to_json().encode(),
        ]
        fresh_ts = str(time.time() - 10)
        stale_ts = str(time.time() - 600)

        def get_side_effect(key):
            if "fresh-id" in key:
                return fresh_ts.encode()
            return stale_ts.encode()

        mock_redis.get.side_effect = get_side_effect
        pipe = mock_redis.pipeline.return_value

        count = queue.requeue_stale(max_age_seconds=300.0)
        assert count == 1


# ===========================================================================
# clear
# ===========================================================================

class TestClear:
    def test_clear_deletes_all_keys(self, queue, mock_redis):
        queue.clear()
        mock_redis.delete.assert_called_once_with(
            _QUEUE_KEY, _PROCESSING_KEY, _DEAD_LETTER_KEY
        )
