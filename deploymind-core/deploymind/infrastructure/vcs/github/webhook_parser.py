"""GitHub Webhook payload parser.

Transforms raw GitHub webhook JSON payloads into typed domain events.
Supports: push, pull_request, and ping event types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Domain events
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PushEvent:
    """Represents a GitHub push webhook event."""

    repository: str          # "owner/repo"
    branch: str              # "main" (refs/heads stripped)
    commit_sha: str          # HEAD commit SHA after push
    commit_message: str      # HEAD commit message
    pusher: str              # GitHub login of the pusher
    compare_url: str         # GitHub compare URL for this push
    before_sha: str          # SHA before the push (all-zeros = new branch)
    commits_count: int       # Number of commits in the push

    @property
    def is_new_branch(self) -> bool:
        """True when this push created a new branch."""
        return self.before_sha == "0" * 40

    @property
    def is_default_branch(self) -> bool:
        """True when push is to main/master."""
        return self.branch in ("main", "master")


@dataclass(frozen=True)
class PullRequestEvent:
    """Represents a GitHub pull_request webhook event."""

    repository: str          # "owner/repo"
    pr_number: int           # Pull request number
    branch: str              # Head branch name
    commit_sha: str          # Head commit SHA
    action: str              # opened / synchronize / closed / reopened / labeled
    title: str               # PR title
    base_branch: str         # Target branch (e.g. "main")
    draft: bool              # Whether PR is a draft

    @property
    def is_mergeable_action(self) -> bool:
        """True for actions that should trigger a build."""
        return self.action in ("opened", "synchronize", "reopened")

    @property
    def is_merged(self) -> bool:
        """True when action is closed and PR was merged."""
        return self.action == "merged"


@dataclass(frozen=True)
class PingEvent:
    """Represents a GitHub ping webhook event (sent when hook is first created)."""

    hook_id: int
    repository: str          # "owner/repo" — empty string if org-level ping
    zen: str                 # GitHub's random zen quote


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class WebhookParseError(ValueError):
    """Raised when a webhook payload cannot be parsed."""


class WebhookParser:
    """Parses raw GitHub webhook payloads into typed event objects.

    Usage::

        parser = WebhookParser()
        event = parser.parse("push", payload_dict)
    """

    # Map GitHub event header → parser method
    _HANDLERS = {
        "push": "_parse_push",
        "pull_request": "_parse_pull_request",
        "ping": "_parse_ping",
    }

    def parse(self, event_type: str, payload: dict[str, Any]) -> PushEvent | PullRequestEvent | PingEvent:
        """Dispatch to the correct parser based on X-GitHub-Event header value.

        Args:
            event_type: Value of the ``X-GitHub-Event`` HTTP header.
            payload: Decoded JSON body.

        Returns:
            Typed event dataclass.

        Raises:
            WebhookParseError: If event_type is unsupported or payload is malformed.
        """
        if not isinstance(payload, dict):
            raise WebhookParseError("Payload must be a JSON object (dict)")

        handler_name = self._HANDLERS.get(event_type)
        if handler_name is None:
            raise WebhookParseError(
                f"Unsupported event type: '{event_type}'. "
                f"Supported: {list(self._HANDLERS)}"
            )

        handler = getattr(self, handler_name)
        try:
            return handler(payload)
        except (KeyError, TypeError, IndexError) as exc:
            raise WebhookParseError(
                f"Malformed '{event_type}' payload: {exc}"
            ) from exc

    def parse_push(self, payload: dict[str, Any]) -> PushEvent:
        """Parse a push event payload directly."""
        return self._parse_push(payload)

    def parse_pull_request(self, payload: dict[str, Any]) -> PullRequestEvent:
        """Parse a pull_request event payload directly."""
        return self._parse_pull_request(payload)

    def parse_ping(self, payload: dict[str, Any]) -> PingEvent:
        """Parse a ping event payload directly."""
        return self._parse_ping(payload)

    # ------------------------------------------------------------------
    # Private parsers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_push(payload: dict[str, Any]) -> PushEvent:
        repo_info = payload.get("repository", {})
        repo = repo_info.get("full_name", "")
        if not repo:
            raise WebhookParseError("Push payload missing repository.full_name")

        raw_ref = payload.get("ref", "")
        branch = raw_ref.replace("refs/heads/", "").replace("refs/tags/", "")

        commits: list[dict] = payload.get("commits", [])
        head_commit = payload.get("head_commit") or (commits[-1] if commits else {})

        commit_sha = payload.get("after", "")
        commit_message = head_commit.get("message", "") if head_commit else ""
        pusher = payload.get("pusher", {}).get("name", "")
        compare_url = payload.get("compare", "")
        before_sha = payload.get("before", "0" * 40)

        return PushEvent(
            repository=repo,
            branch=branch,
            commit_sha=commit_sha,
            commit_message=commit_message,
            pusher=pusher,
            compare_url=compare_url,
            before_sha=before_sha,
            commits_count=len(commits),
        )

    @staticmethod
    def _parse_pull_request(payload: dict[str, Any]) -> PullRequestEvent:
        repo_info = payload.get("repository", {})
        repo = repo_info.get("full_name", "")
        if not repo:
            raise WebhookParseError("PR payload missing repository.full_name")

        pr = payload.get("pull_request", {})
        if not pr:
            raise WebhookParseError("PR payload missing pull_request object")

        action = payload.get("action", "")

        # Detect merge: action is "closed" and merged flag is True
        if action == "closed" and pr.get("merged", False):
            action = "merged"

        head = pr.get("head", {})
        base = pr.get("base", {})

        return PullRequestEvent(
            repository=repo,
            pr_number=payload.get("number", 0),
            branch=head.get("ref", ""),
            commit_sha=head.get("sha", ""),
            action=action,
            title=pr.get("title", ""),
            base_branch=base.get("ref", ""),
            draft=pr.get("draft", False),
        )

    @staticmethod
    def _parse_ping(payload: dict[str, Any]) -> PingEvent:
        repo_info = payload.get("repository") or {}
        repo = repo_info.get("full_name", "") if isinstance(repo_info, dict) else ""

        hook = payload.get("hook", {})
        hook_id = hook.get("id", 0) if isinstance(hook, dict) else payload.get("hook_id", 0)

        return PingEvent(
            hook_id=hook_id,
            repository=repo,
            zen=payload.get("zen", ""),
        )
