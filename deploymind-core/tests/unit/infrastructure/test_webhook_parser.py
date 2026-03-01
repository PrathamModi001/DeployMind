"""Intensive tests for WebhookParser and domain event dataclasses.

Covers:
- PushEvent / PullRequestEvent / PingEvent construction from real-shaped payloads
- Edge cases: empty commits list, missing fields, all-zero before_sha
- PullRequest merge detection (action=closed + merged=True → action='merged')
- is_default_branch / is_new_branch / is_mergeable_action / is_merged properties
- parse() dispatcher routing + unsupported-event error
- parse_push / parse_pull_request / parse_ping direct call paths
- WebhookParseError on malformed payloads (missing repo, missing pr object, non-dict)
- Draft PR handling
"""

from __future__ import annotations

import pytest

from deploymind.infrastructure.vcs.github.webhook_parser import (
    PingEvent,
    PullRequestEvent,
    PushEvent,
    WebhookParseError,
    WebhookParser,
)


# ---------------------------------------------------------------------------
# Helpers — minimal but realistic GitHub payload factories
# ---------------------------------------------------------------------------

def _push_payload(
    full_name: str = "owner/repo",
    ref: str = "refs/heads/main",
    after: str = "abc123def456" * 3 + "ab",  # 38 chars — close enough
    before: str = "0" * 40,
    commits: list | None = None,
    pusher: str = "alice",
    compare: str = "https://github.com/owner/repo/compare/abc...def",
) -> dict:
    if commits is None:
        commits = [{"message": "fix: bug", "id": after}]
    return {
        "ref": ref,
        "before": before,
        "after": after,
        "repository": {"full_name": full_name},
        "pusher": {"name": pusher},
        "compare": compare,
        "commits": commits,
        "head_commit": {"message": commits[0]["message"]} if commits else None,
    }


def _pr_payload(
    full_name: str = "owner/repo",
    number: int = 42,
    action: str = "opened",
    head_ref: str = "feature/my-feature",
    head_sha: str = "deadbeef" * 5,
    base_ref: str = "main",
    title: str = "Add feature",
    draft: bool = False,
    merged: bool = False,
) -> dict:
    return {
        "action": action,
        "number": number,
        "repository": {"full_name": full_name},
        "pull_request": {
            "title": title,
            "draft": draft,
            "merged": merged,
            "head": {"ref": head_ref, "sha": head_sha},
            "base": {"ref": base_ref},
        },
    }


def _ping_payload(
    full_name: str = "owner/repo",
    hook_id: int = 99,
    zen: str = "Keep it logically awesome.",
) -> dict:
    return {
        "zen": zen,
        "hook": {"id": hook_id},
        "repository": {"full_name": full_name},
    }


@pytest.fixture
def parser() -> WebhookParser:
    return WebhookParser()


# ===========================================================================
# PushEvent tests
# ===========================================================================

class TestPushEvent:
    def test_basic_push(self, parser):
        event = parser.parse_push(_push_payload())
        assert isinstance(event, PushEvent)

    def test_repository_parsed(self, parser):
        event = parser.parse_push(_push_payload(full_name="acme/api"))
        assert event.repository == "acme/api"

    def test_branch_stripped_of_refs_heads(self, parser):
        event = parser.parse_push(_push_payload(ref="refs/heads/feature/foo"))
        assert event.branch == "feature/foo"

    def test_branch_main(self, parser):
        event = parser.parse_push(_push_payload(ref="refs/heads/main"))
        assert event.branch == "main"

    def test_branch_tag_ref(self, parser):
        event = parser.parse_push(_push_payload(ref="refs/tags/v1.0.0"))
        assert event.branch == "v1.0.0"

    def test_commit_sha(self, parser):
        event = parser.parse_push(_push_payload(after="cafebabe" * 5))
        assert event.commit_sha == "cafebabe" * 5

    def test_commit_message(self, parser):
        commits = [{"message": "chore: update deps", "id": "abc"}]
        payload = _push_payload(commits=commits)
        payload["head_commit"] = {"message": "chore: update deps"}
        event = parser.parse_push(payload)
        assert event.commit_message == "chore: update deps"

    def test_pusher(self, parser):
        event = parser.parse_push(_push_payload(pusher="bob"))
        assert event.pusher == "bob"

    def test_compare_url(self, parser):
        url = "https://github.com/owner/repo/compare/abc...def"
        event = parser.parse_push(_push_payload(compare=url))
        assert event.compare_url == url

    def test_before_sha(self, parser):
        event = parser.parse_push(_push_payload(before="deadbeef" * 5))
        assert event.before_sha == "deadbeef" * 5

    def test_commits_count(self, parser):
        commits = [{"message": f"c{i}", "id": str(i)} for i in range(5)]
        event = parser.parse_push(_push_payload(commits=commits))
        assert event.commits_count == 5

    def test_empty_commits_list(self, parser):
        payload = _push_payload(commits=[])
        payload["head_commit"] = None
        event = parser.parse_push(payload)
        assert event.commits_count == 0
        assert event.commit_message == ""

    def test_is_new_branch_true(self, parser):
        event = parser.parse_push(_push_payload(before="0" * 40))
        assert event.is_new_branch is True

    def test_is_new_branch_false(self, parser):
        event = parser.parse_push(_push_payload(before="abc" + "0" * 37))
        assert event.is_new_branch is False

    def test_is_default_branch_main(self, parser):
        event = parser.parse_push(_push_payload(ref="refs/heads/main"))
        assert event.is_default_branch is True

    def test_is_default_branch_master(self, parser):
        event = parser.parse_push(_push_payload(ref="refs/heads/master"))
        assert event.is_default_branch is True

    def test_is_default_branch_false(self, parser):
        event = parser.parse_push(_push_payload(ref="refs/heads/develop"))
        assert event.is_default_branch is False

    def test_missing_repository_raises(self, parser):
        payload = _push_payload()
        del payload["repository"]
        with pytest.raises((WebhookParseError, KeyError)):
            parser.parse_push(payload)

    def test_empty_full_name_raises(self, parser):
        payload = _push_payload()
        payload["repository"]["full_name"] = ""
        with pytest.raises(WebhookParseError):
            parser.parse_push(payload)

    def test_parse_dispatcher_push(self, parser):
        event = parser.parse("push", _push_payload())
        assert isinstance(event, PushEvent)

    def test_push_event_is_frozen(self, parser):
        event = parser.parse_push(_push_payload())
        with pytest.raises((AttributeError, TypeError)):
            event.branch = "hacked"  # type: ignore[misc]


# ===========================================================================
# PullRequestEvent tests
# ===========================================================================

class TestPullRequestEvent:
    def test_basic_pr(self, parser):
        event = parser.parse_pull_request(_pr_payload())
        assert isinstance(event, PullRequestEvent)

    def test_repository(self, parser):
        event = parser.parse_pull_request(_pr_payload(full_name="org/svc"))
        assert event.repository == "org/svc"

    def test_pr_number(self, parser):
        event = parser.parse_pull_request(_pr_payload(number=99))
        assert event.pr_number == 99

    def test_branch(self, parser):
        event = parser.parse_pull_request(_pr_payload(head_ref="feat/xyz"))
        assert event.branch == "feat/xyz"

    def test_commit_sha(self, parser):
        event = parser.parse_pull_request(_pr_payload(head_sha="cafebabe" * 5))
        assert event.commit_sha == "cafebabe" * 5

    def test_action_opened(self, parser):
        event = parser.parse_pull_request(_pr_payload(action="opened"))
        assert event.action == "opened"

    def test_action_synchronize(self, parser):
        event = parser.parse_pull_request(_pr_payload(action="synchronize"))
        assert event.action == "synchronize"

    def test_action_closed_not_merged(self, parser):
        event = parser.parse_pull_request(_pr_payload(action="closed", merged=False))
        assert event.action == "closed"
        assert not event.is_merged

    def test_action_closed_merged_becomes_merged(self, parser):
        event = parser.parse_pull_request(_pr_payload(action="closed", merged=True))
        assert event.action == "merged"
        assert event.is_merged is True

    def test_action_reopened(self, parser):
        event = parser.parse_pull_request(_pr_payload(action="reopened"))
        assert event.action == "reopened"

    def test_title(self, parser):
        event = parser.parse_pull_request(_pr_payload(title="Add fancy feature"))
        assert event.title == "Add fancy feature"

    def test_base_branch(self, parser):
        event = parser.parse_pull_request(_pr_payload(base_ref="develop"))
        assert event.base_branch == "develop"

    def test_draft_true(self, parser):
        event = parser.parse_pull_request(_pr_payload(draft=True))
        assert event.draft is True

    def test_draft_false(self, parser):
        event = parser.parse_pull_request(_pr_payload(draft=False))
        assert event.draft is False

    def test_is_mergeable_action_opened(self, parser):
        event = parser.parse_pull_request(_pr_payload(action="opened"))
        assert event.is_mergeable_action is True

    def test_is_mergeable_action_synchronize(self, parser):
        event = parser.parse_pull_request(_pr_payload(action="synchronize"))
        assert event.is_mergeable_action is True

    def test_is_mergeable_action_closed(self, parser):
        event = parser.parse_pull_request(_pr_payload(action="closed"))
        assert event.is_mergeable_action is False

    def test_is_mergeable_action_labeled(self, parser):
        event = parser.parse_pull_request(_pr_payload(action="labeled"))
        assert event.is_mergeable_action is False

    def test_missing_repository_raises(self, parser):
        payload = _pr_payload()
        payload["repository"]["full_name"] = ""
        with pytest.raises(WebhookParseError):
            parser.parse_pull_request(payload)

    def test_missing_pull_request_object_raises(self, parser):
        payload = _pr_payload()
        del payload["pull_request"]
        with pytest.raises(WebhookParseError):
            parser.parse_pull_request(payload)

    def test_parse_dispatcher_pr(self, parser):
        event = parser.parse("pull_request", _pr_payload())
        assert isinstance(event, PullRequestEvent)

    def test_pr_event_is_frozen(self, parser):
        event = parser.parse_pull_request(_pr_payload())
        with pytest.raises((AttributeError, TypeError)):
            event.action = "hacked"  # type: ignore[misc]


# ===========================================================================
# PingEvent tests
# ===========================================================================

class TestPingEvent:
    def test_basic_ping(self, parser):
        event = parser.parse_ping(_ping_payload())
        assert isinstance(event, PingEvent)

    def test_hook_id(self, parser):
        event = parser.parse_ping(_ping_payload(hook_id=12345))
        assert event.hook_id == 12345

    def test_repository(self, parser):
        event = parser.parse_ping(_ping_payload(full_name="owner/repo"))
        assert event.repository == "owner/repo"

    def test_zen(self, parser):
        event = parser.parse_ping(_ping_payload(zen="Speak friend and enter."))
        assert event.zen == "Speak friend and enter."

    def test_org_level_ping_no_repo(self, parser):
        payload = {"zen": "hi", "hook": {"id": 1}, "repository": None}
        event = parser.parse_ping(payload)
        assert event.repository == ""

    def test_parse_dispatcher_ping(self, parser):
        event = parser.parse("ping", _ping_payload())
        assert isinstance(event, PingEvent)

    def test_ping_event_is_frozen(self, parser):
        event = parser.parse_ping(_ping_payload())
        with pytest.raises((AttributeError, TypeError)):
            event.zen = "hacked"  # type: ignore[misc]


# ===========================================================================
# WebhookParser dispatcher tests
# ===========================================================================

class TestWebhookParserDispatcher:
    def test_unsupported_event_raises(self, parser):
        with pytest.raises(WebhookParseError, match="Unsupported event type"):
            parser.parse("create", {"repository": {"full_name": "x/y"}})

    def test_non_dict_payload_raises(self, parser):
        with pytest.raises(WebhookParseError, match="must be a JSON object"):
            parser.parse("push", "not a dict")  # type: ignore[arg-type]

    def test_none_payload_raises(self, parser):
        with pytest.raises(WebhookParseError):
            parser.parse("push", None)  # type: ignore[arg-type]

    def test_list_payload_raises(self, parser):
        with pytest.raises(WebhookParseError):
            parser.parse("push", [])  # type: ignore[arg-type]

    def test_empty_dict_push_raises(self, parser):
        with pytest.raises(WebhookParseError):
            parser.parse("push", {})

    def test_case_sensitivity_event_type(self, parser):
        # Event type 'Push' (capitalised) should NOT match 'push'
        with pytest.raises(WebhookParseError, match="Unsupported"):
            parser.parse("Push", _push_payload())

    def test_unknown_event_error_message_lists_supported(self, parser):
        try:
            parser.parse("star", {})
        except WebhookParseError as exc:
            assert "push" in str(exc)
            assert "pull_request" in str(exc)
            assert "ping" in str(exc)
