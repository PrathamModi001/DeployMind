"""Tests for the FastAPI GitHub webhook router.

Uses FastAPI's TestClient + httpx to drive the endpoint without a live server.
All HMAC verification uses a known test secret.

Covers:
- Signature verification: missing header, wrong header, valid signature
- Ping event: 202 + expected body shape
- Push event: default branch → 202 queued; non-default → 202 ignored
- Pull request event: opened/synchronize/reopened → queued; closed/labeled → ignored;
  draft PR → ignored
- Merged PR (closed + merged=True) → ignored (not a build trigger)
- Unsupported event type → 202 ignored (not 4xx, to prevent GitHub retries)
- Invalid JSON body → 400
- HMAC mismatch → 401
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

_fastapi_available = True
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
except ImportError:
    _fastapi_available = False

pytestmark = pytest.mark.skipif(
    not _fastapi_available, reason="fastapi/httpx not installed"
)


if _fastapi_available:
    from deploymind.presentation.api.routes.webhooks import create_webhook_router

TEST_SECRET = "super-secret-webhook-key"


def _sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture
def test_client():
    app = FastAPI()
    router = create_webhook_router(TEST_SECRET)
    app.include_router(router)
    return TestClient(app, raise_server_exceptions=True)


def _post(client, event_type: str, payload: dict, secret: str = TEST_SECRET):
    body = json.dumps(payload).encode()
    headers = {
        "X-GitHub-Event": event_type,
        "X-Hub-Signature-256": _sign(secret, body),
        "X-GitHub-Delivery": "test-delivery-id",
        "Content-Type": "application/json",
    }
    return client.post("/webhooks/github", content=body, headers=headers)


def _push_payload(branch="main"):
    return {
        "ref": f"refs/heads/{branch}",
        "before": "0" * 40,
        "after": "abc" * 13 + "a",
        "repository": {"full_name": "owner/repo"},
        "pusher": {"name": "alice"},
        "compare": "https://github.com/owner/repo/compare/abc...def",
        "commits": [{"message": "fix bug", "id": "abc"}],
        "head_commit": {"message": "fix bug"},
    }


def _pr_payload(action="opened", draft=False, merged=False):
    return {
        "action": action,
        "number": 10,
        "repository": {"full_name": "owner/repo"},
        "pull_request": {
            "title": "My PR",
            "draft": draft,
            "merged": merged,
            "head": {"ref": "feature/xyz", "sha": "deadbeef" * 5},
            "base": {"ref": "main"},
        },
    }


# ===========================================================================
# Signature verification
# ===========================================================================

class TestSignatureVerification:
    def test_missing_signature_header_returns_401(self, test_client):
        body = json.dumps(_push_payload()).encode()
        headers = {
            "X-GitHub-Event": "push",
            "Content-Type": "application/json",
        }
        resp = test_client.post("/webhooks/github", content=body, headers=headers)
        assert resp.status_code == 401

    def test_wrong_signature_returns_401(self, test_client):
        body = json.dumps(_push_payload()).encode()
        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": "sha256=wrongsignature",
            "Content-Type": "application/json",
        }
        resp = test_client.post("/webhooks/github", content=body, headers=headers)
        assert resp.status_code == 401

    def test_signature_without_sha256_prefix_returns_401(self, test_client):
        body = json.dumps(_push_payload()).encode()
        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": "badhex",
            "Content-Type": "application/json",
        }
        resp = test_client.post("/webhooks/github", content=body, headers=headers)
        assert resp.status_code == 401

    def test_wrong_secret_returns_401(self, test_client):
        resp = _post(test_client, "push", _push_payload(), secret="wrong-secret")
        assert resp.status_code == 401

    def test_valid_signature_accepted(self, test_client):
        resp = _post(test_client, "ping", {
            "zen": "hello",
            "hook": {"id": 1},
            "repository": {"full_name": "owner/repo"},
        })
        assert resp.status_code == 202


# ===========================================================================
# Ping event
# ===========================================================================

class TestPingEvent:
    def test_ping_returns_202(self, test_client):
        resp = _post(test_client, "ping", {
            "zen": "Keep it simple.",
            "hook": {"id": 42},
            "repository": {"full_name": "owner/repo"},
        })
        assert resp.status_code == 202

    def test_ping_response_has_ok_status(self, test_client):
        resp = _post(test_client, "ping", {
            "zen": "hi",
            "hook": {"id": 1},
            "repository": {"full_name": "owner/repo"},
        })
        data = resp.json()
        assert data["status"] == "ok"
        assert data["event"] == "ping"

    def test_ping_response_contains_hook_id(self, test_client):
        resp = _post(test_client, "ping", {
            "zen": "hi",
            "hook": {"id": 99},
            "repository": {"full_name": "owner/repo"},
        })
        assert resp.json()["hook_id"] == 99

    def test_ping_response_contains_zen(self, test_client):
        resp = _post(test_client, "ping", {
            "zen": "Speak friend and enter.",
            "hook": {"id": 1},
            "repository": {"full_name": "owner/repo"},
        })
        assert "Speak friend and enter." in resp.json()["zen"]


# ===========================================================================
# Push event
# ===========================================================================

class TestPushEvent:
    def test_push_to_main_returns_queued(self, test_client):
        resp = _post(test_client, "push", _push_payload(branch="main"))
        assert resp.status_code == 202
        assert resp.json()["status"] == "queued"

    def test_push_to_master_returns_queued(self, test_client):
        resp = _post(test_client, "push", _push_payload(branch="master"))
        assert resp.json()["status"] == "queued"

    def test_push_to_feature_branch_returns_ignored(self, test_client):
        resp = _post(test_client, "push", _push_payload(branch="feature/xyz"))
        assert resp.json()["status"] == "ignored"

    def test_push_to_develop_returns_ignored(self, test_client):
        resp = _post(test_client, "push", _push_payload(branch="develop"))
        assert resp.json()["status"] == "ignored"

    def test_push_response_contains_repo(self, test_client):
        resp = _post(test_client, "push", _push_payload())
        assert resp.json()["repository"] == "owner/repo"

    def test_push_response_contains_branch(self, test_client):
        resp = _post(test_client, "push", _push_payload())
        assert resp.json()["branch"] == "main"

    def test_push_response_contains_pusher(self, test_client):
        resp = _post(test_client, "push", _push_payload())
        assert resp.json()["pusher"] == "alice"


# ===========================================================================
# Pull request event
# ===========================================================================

class TestPullRequestEvent:
    def test_opened_pr_returns_queued(self, test_client):
        resp = _post(test_client, "pull_request", _pr_payload(action="opened"))
        assert resp.status_code == 202
        assert resp.json()["status"] == "queued"

    def test_synchronize_pr_returns_queued(self, test_client):
        resp = _post(test_client, "pull_request", _pr_payload(action="synchronize"))
        assert resp.json()["status"] == "queued"

    def test_reopened_pr_returns_queued(self, test_client):
        resp = _post(test_client, "pull_request", _pr_payload(action="reopened"))
        assert resp.json()["status"] == "queued"

    def test_closed_pr_returns_ignored(self, test_client):
        resp = _post(test_client, "pull_request", _pr_payload(action="closed"))
        assert resp.json()["status"] == "ignored"

    def test_labeled_pr_returns_ignored(self, test_client):
        resp = _post(test_client, "pull_request", _pr_payload(action="labeled"))
        assert resp.json()["status"] == "ignored"

    def test_merged_pr_returns_ignored(self, test_client):
        resp = _post(test_client, "pull_request", _pr_payload(action="closed", merged=True))
        # The action resolves to "merged" which is not in mergeable actions
        assert resp.json()["status"] == "ignored"

    def test_draft_pr_opened_returns_ignored(self, test_client):
        resp = _post(test_client, "pull_request", _pr_payload(action="opened", draft=True))
        assert resp.json()["status"] == "ignored"

    def test_draft_pr_sync_returns_ignored(self, test_client):
        resp = _post(test_client, "pull_request", _pr_payload(action="synchronize", draft=True))
        assert resp.json()["status"] == "ignored"

    def test_queued_pr_response_has_pr_number(self, test_client):
        resp = _post(test_client, "pull_request", _pr_payload(action="opened"))
        assert resp.json()["pr_number"] == 10

    def test_queued_pr_response_has_branch(self, test_client):
        resp = _post(test_client, "pull_request", _pr_payload(action="opened"))
        assert resp.json()["branch"] == "feature/xyz"


# ===========================================================================
# Unsupported events and invalid body
# ===========================================================================

class TestEdgeCases:
    def test_unsupported_event_returns_202_not_4xx(self, test_client):
        resp = _post(test_client, "star", {"repository": {"full_name": "owner/repo"}})
        assert resp.status_code == 202
        assert resp.json()["status"] == "ignored"

    def test_invalid_json_body_returns_400(self, test_client):
        body = b"not json at all"
        headers = {
            "X-GitHub-Event": "push",
            "X-Hub-Signature-256": _sign(TEST_SECRET, body),
            "Content-Type": "application/json",
        }
        resp = test_client.post("/webhooks/github", content=body, headers=headers)
        assert resp.status_code == 400
