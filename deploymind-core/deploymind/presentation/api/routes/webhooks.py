"""FastAPI router for GitHub webhook events.

Receives GitHub webhook POSTs, verifies the HMAC-SHA256 signature,
parses the payload into typed domain events, and enqueues deployments.

Endpoint:
    POST /webhooks/github
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from deploymind.infrastructure.vcs.github.webhook_parser import (
    PingEvent,
    PullRequestEvent,
    PushEvent,
    WebhookParser,
    WebhookParseError,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_parser = WebhookParser()


# ---------------------------------------------------------------------------
# Signature verification helper
# ---------------------------------------------------------------------------


def _verify_signature(secret: str, body: bytes, signature_header: str | None) -> None:
    """Verify GitHub's X-Hub-Signature-256 header using HMAC-SHA256.

    Args:
        secret: Webhook secret configured in GitHub.
        body: Raw request body bytes.
        signature_header: Value of the ``X-Hub-Signature-256`` header.

    Raises:
        HTTPException 401: If the signature is missing or does not match.
    """
    if not signature_header:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Hub-Signature-256 header",
        )

    if not signature_header.startswith("sha256="):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Signature must start with 'sha256='",
        )

    expected = hmac.new(
        key=secret.encode(),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    received = signature_header[len("sha256="):]

    if not hmac.compare_digest(expected, received):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature mismatch",
        )


# ---------------------------------------------------------------------------
# Route factory — accepts webhook_secret as a dependency so it can be
# overridden in tests without touching global state.
# ---------------------------------------------------------------------------


def create_webhook_router(webhook_secret: str) -> APIRouter:
    """Create a webhook router bound to a specific secret.

    Separating construction from the module-level router allows test code to
    inject a fake secret and inspect routed events.

    Args:
        webhook_secret: HMAC secret configured in GitHub webhook settings.

    Returns:
        Configured APIRouter instance.
    """
    local_router = APIRouter(prefix="/webhooks", tags=["webhooks"])

    @local_router.post("/github", status_code=status.HTTP_202_ACCEPTED)
    async def github_webhook(
        request: Request,
        x_hub_signature_256: str | None = Header(default=None),
        x_github_event: str | None = Header(default=None),
        x_github_delivery: str | None = Header(default=None),
    ) -> dict[str, Any]:
        """Handle incoming GitHub webhook events.

        GitHub sends this endpoint HTTP POST requests when repository events
        occur (push, pull_request, ping, …).

        The handler:
        1. Reads the raw body before JSON parsing (required for HMAC).
        2. Verifies the HMAC-SHA256 signature.
        3. Parses the payload into a typed domain event.
        4. Routes to the appropriate handler.
        """
        body = await request.body()

        # 1. Verify signature
        _verify_signature(webhook_secret, body, x_hub_signature_256)

        # 2. Decode payload
        try:
            payload: dict[str, Any] = json.loads(body)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON body: {exc}",
            )

        event_type = (x_github_event or "").lower()
        delivery_id = x_github_delivery or "unknown"

        logger.info(
            "Received GitHub webhook",
            extra={"event": event_type, "delivery": delivery_id},
        )

        # 3. Parse and route
        try:
            event = _parser.parse(event_type, payload)
        except WebhookParseError as exc:
            # Unknown / unsupported event — return 200 so GitHub doesn't retry
            logger.warning(f"Unsupported webhook event '{event_type}': {exc}")
            return {"status": "ignored", "event": event_type, "reason": str(exc)}

        if isinstance(event, PingEvent):
            return _handle_ping(event)
        elif isinstance(event, PushEvent):
            return _handle_push(event)
        elif isinstance(event, PullRequestEvent):
            return _handle_pull_request(event)

        return {"status": "ignored", "event": event_type}

    return local_router


# ---------------------------------------------------------------------------
# Event handlers
# ---------------------------------------------------------------------------


def _handle_ping(event: PingEvent) -> dict[str, Any]:
    """Respond to GitHub's initial ping — no deployment triggered."""
    logger.info(
        f"GitHub ping received: hook_id={event.hook_id}, zen={event.zen!r}"
    )
    return {
        "status": "ok",
        "event": "ping",
        "hook_id": event.hook_id,
        "zen": event.zen,
    }


def _handle_push(event: PushEvent) -> dict[str, Any]:
    """Handle a push event — enqueue deployment for default-branch pushes."""
    logger.info(
        "Push event",
        extra={
            "repo": event.repository,
            "branch": event.branch,
            "sha": event.commit_sha[:7],
            "pusher": event.pusher,
        },
    )

    if not event.is_default_branch:
        return {
            "status": "ignored",
            "event": "push",
            "reason": f"Branch '{event.branch}' is not main/master",
        }

    # TODO(Phase 4 wiring): enqueue via DeploymentQueue
    logger.info(f"Would enqueue deployment for {event.repository}@{event.branch}")

    return {
        "status": "queued",
        "event": "push",
        "repository": event.repository,
        "branch": event.branch,
        "commit_sha": event.commit_sha,
        "pusher": event.pusher,
    }


def _handle_pull_request(event: PullRequestEvent) -> dict[str, Any]:
    """Handle a pull_request event — post status updates for open PRs."""
    logger.info(
        "Pull request event",
        extra={
            "repo": event.repository,
            "pr": event.pr_number,
            "action": event.action,
        },
    )

    if not event.is_mergeable_action:
        return {
            "status": "ignored",
            "event": "pull_request",
            "reason": f"Action '{event.action}' does not trigger a build",
        }

    if event.draft:
        return {
            "status": "ignored",
            "event": "pull_request",
            "reason": "Draft PRs are not built",
        }

    # TODO(Phase 4 wiring): post "pending" commit status and enqueue build
    logger.info(
        f"Would build PR #{event.pr_number} for {event.repository}@{event.branch}"
    )

    return {
        "status": "queued",
        "event": "pull_request",
        "repository": event.repository,
        "pr_number": event.pr_number,
        "branch": event.branch,
        "commit_sha": event.commit_sha,
        "action": event.action,
    }
