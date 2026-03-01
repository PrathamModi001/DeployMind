"""Redis-backed reliable deployment queue.

Uses the BRPOPLPUSH (or BLMOVE on Redis ≥ 6.2) reliability pattern:
  - Jobs are pushed to ``deploymind:queue``
  - A worker atomically moves a job to ``deploymind:processing`` before working on it
  - If the worker crashes, the job stays in ``deploymind:processing``
    and can be re-queued by a watchdog (``requeue_stale``).
  - On success the worker calls ``ack()`` to remove it from processing.
  - On unrecoverable failure the worker calls ``nack()`` to move it to
    ``deploymind:dead-letter``.

Job lifecycle:
    enqueue  →  dequeue  →  [work]  →  ack      (success)
                                    →  nack     (dead-letter)
               requeue_stale        (crash recovery)
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

import redis


# ---------------------------------------------------------------------------
# Queue key constants
# ---------------------------------------------------------------------------

_QUEUE_KEY = "deploymind:queue"
_PROCESSING_KEY = "deploymind:processing"
_DEAD_LETTER_KEY = "deploymind:dead-letter"
_JOB_DATA_PREFIX = "deploymind:job:"  # Hash with per-job metadata
_PROCESSING_TS_PREFIX = "deploymind:processing-ts:"  # Score when dequeued


# ---------------------------------------------------------------------------
# Domain object
# ---------------------------------------------------------------------------


@dataclass
class DeploymentJob:
    """Represents a single deployment task in the queue.

    Attributes:
        job_id: Unique identifier (UUIDv4 string).
        repository: GitHub repository in "owner/repo" format.
        branch: Branch to deploy.
        commit_sha: Commit SHA to build and deploy.
        triggered_by: Actor that caused the deployment (pusher login, "manual", etc.).
        priority: Lower numbers run first when ordering is applied (default 5).
        created_at: Unix timestamp when the job was enqueued.
        metadata: Arbitrary key→value pairs (PR number, deploy target, …).
    """

    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    repository: str = ""
    branch: str = ""
    commit_sha: str = ""
    triggered_by: str = "unknown"
    priority: int = 5
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, raw: str | bytes) -> "DeploymentJob":
        data = json.loads(raw)
        return cls(**data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DeploymentJob":
        return cls(**data)


# ---------------------------------------------------------------------------
# Queue implementation
# ---------------------------------------------------------------------------


class DeploymentQueue:
    """Reliable FIFO deployment queue backed by Redis lists.

    Args:
        redis_client: A ``redis.Redis`` connection instance.
        block_timeout: Seconds to block on ``dequeue`` waiting for a job.
            Set to 0 to block indefinitely; 1–N for a bounded wait.
    """

    def __init__(self, redis_client: redis.Redis, block_timeout: int = 5) -> None:
        self._r = redis_client
        self._block_timeout = block_timeout

    # ------------------------------------------------------------------
    # Producer API
    # ------------------------------------------------------------------

    def enqueue(self, job: DeploymentJob) -> str:
        """Push a job to the tail of the queue.

        Args:
            job: The job to enqueue. ``job.job_id`` is set if empty.

        Returns:
            The job's ``job_id``.
        """
        if not job.job_id:
            job.job_id = str(uuid.uuid4())
        if not job.created_at:
            job.created_at = time.time()

        payload = job.to_json()
        self._r.rpush(_QUEUE_KEY, payload)
        return job.job_id

    # ------------------------------------------------------------------
    # Consumer API
    # ------------------------------------------------------------------

    def dequeue(self) -> DeploymentJob | None:
        """Atomically pop a job from the queue and place it in processing.

        Uses BRPOPLPUSH for Redis < 6.2 compatibility.  The job stays in
        the ``processing`` list until the caller calls ``ack`` or ``nack``.

        Returns:
            A ``DeploymentJob`` if one was available within ``block_timeout``
            seconds, otherwise ``None``.
        """
        raw = self._r.brpoplpush(
            _QUEUE_KEY,
            _PROCESSING_KEY,
            timeout=self._block_timeout,
        )
        if raw is None:
            return None

        job = DeploymentJob.from_json(raw)
        # Record the timestamp at which we picked up this job so the watchdog
        # can detect stale processing entries.
        self._r.set(
            f"{_PROCESSING_TS_PREFIX}{job.job_id}",
            str(time.time()),
            ex=3600,  # auto-expire after 1 hour (safety net)
        )
        return job

    def ack(self, job: DeploymentJob) -> bool:
        """Remove a successfully processed job from the processing list.

        Args:
            job: The job that was processed.

        Returns:
            True if the job was found and removed; False if it was not in
            the processing list (e.g., already acked or timed out).
        """
        payload = job.to_json()
        removed = self._r.lrem(_PROCESSING_KEY, 1, payload)
        self._r.delete(f"{_PROCESSING_TS_PREFIX}{job.job_id}")
        return removed > 0

    def nack(self, job: DeploymentJob) -> None:
        """Move a failed job to the dead-letter list.

        Args:
            job: The job that failed unrecoverably.
        """
        payload = job.to_json()
        pipe = self._r.pipeline()
        pipe.lrem(_PROCESSING_KEY, 1, payload)
        pipe.rpush(_DEAD_LETTER_KEY, payload)
        pipe.delete(f"{_PROCESSING_TS_PREFIX}{job.job_id}")
        pipe.execute()

    # ------------------------------------------------------------------
    # Watchdog / introspection API
    # ------------------------------------------------------------------

    def queue_depth(self) -> int:
        """Return the number of jobs waiting to be picked up."""
        return self._r.llen(_QUEUE_KEY)

    def processing_depth(self) -> int:
        """Return the number of jobs currently being processed."""
        return self._r.llen(_PROCESSING_KEY)

    def dead_letter_depth(self) -> int:
        """Return the number of dead-lettered jobs."""
        return self._r.llen(_DEAD_LETTER_KEY)

    def get_processing_jobs(self) -> list[DeploymentJob]:
        """Return all jobs currently in the processing list (for inspection)."""
        raws = self._r.lrange(_PROCESSING_KEY, 0, -1)
        jobs = []
        for raw in raws:
            try:
                jobs.append(DeploymentJob.from_json(raw))
            except (json.JSONDecodeError, TypeError):
                pass  # corrupt entry — skip
        return jobs

    def requeue_stale(self, max_age_seconds: float = 300.0) -> int:
        """Move stale processing jobs back to the queue.

        A job is "stale" if it has been in the processing list longer than
        ``max_age_seconds`` without being acked.  This handles worker crashes.

        Args:
            max_age_seconds: Age threshold in seconds (default 5 minutes).

        Returns:
            Number of jobs that were re-queued.
        """
        now = time.time()
        requeued = 0

        processing_jobs = self.get_processing_jobs()
        for job in processing_jobs:
            ts_key = f"{_PROCESSING_TS_PREFIX}{job.job_id}"
            raw_ts = self._r.get(ts_key)
            if raw_ts is None:
                continue  # no timestamp, skip

            dequeued_at = float(raw_ts)
            if now - dequeued_at >= max_age_seconds:
                payload = job.to_json()
                pipe = self._r.pipeline()
                pipe.lrem(_PROCESSING_KEY, 1, payload)
                pipe.rpush(_QUEUE_KEY, payload)
                pipe.delete(ts_key)
                pipe.execute()
                requeued += 1

        return requeued

    def clear(self) -> None:
        """Remove all jobs from all lists (useful in tests / CI teardown)."""
        self._r.delete(_QUEUE_KEY, _PROCESSING_KEY, _DEAD_LETTER_KEY)
