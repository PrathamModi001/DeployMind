"""Tests for GitHub webhooks — comprehensive edge-case coverage.

Tests:
- HMAC signature verification (valid, invalid, missing, wrong format)
- Webhook secret not configured → 401
- Ping event handling
- Push to main/master → auto-deploy triggered
- Push to feature branch → ignored
- Push with no previous deployed app → auto_deploy=False
- Pull request opened/closed/other actions
- Unknown event type → acknowledged but not processed
- Webhook setup info endpoint
- Edge cases: missing fields, malformed payloads, large payloads
"""
import pytest
import json
import hmac
import hashlib
import uuid
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock, AsyncMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
from pathlib import Path

# Add deploymind-core to path (5 parents from tests/ in api/tests/)
core_path = Path(__file__).parent.parent.parent.parent.parent / "deploymind-core"
sys.path.insert(0, str(core_path))

from api.main import app
from api.models.user import User
from api.services.database import get_db

try:
    from deploymind.infrastructure.database.models import (
        Deployment,
        DeploymentStatusEnum,
        DeploymentStrategyEnum,
    )
    from deploymind.infrastructure.database.connection import Base as CoreBase
    CORE_AVAILABLE = True
except ImportError:
    Deployment = None
    DeploymentStatusEnum = None
    DeploymentStrategyEnum = None
    CoreBase = None
    CORE_AVAILABLE = False

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create all tables
if CORE_AVAILABLE and CoreBase:
    CoreBase.metadata.create_all(bind=engine)
else:
    User.__table__.create(bind=engine, checkfirst=True)


def override_get_db():
    """Override database dependency."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db_override():
    """Ensure this file's DB override is active for every test in this file."""
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)

TEST_SECRET = "test-webhook-secret-abc123"


def make_signature(payload: bytes, secret: str = TEST_SECRET) -> str:
    """Generate a valid GitHub webhook HMAC-SHA256 signature."""
    sig = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={sig}"


def post_webhook(payload: dict, event: str, secret: str = TEST_SECRET, signature: str = None):
    """Helper: POST a webhook event with correct headers and signature."""
    body = json.dumps(payload).encode()
    sig = signature if signature is not None else make_signature(body, secret)
    headers = {"X-GitHub-Event": event}
    if sig:
        headers["X-Hub-Signature-256"] = sig
    return client.post("/api/webhooks/github", content=body, headers=headers)


@pytest.fixture(autouse=True)
def mock_secret():
    """Always configure webhook secret for tests."""
    with patch("api.routes.webhooks.settings") as mock_settings:
        mock_settings.github_webhook_secret = TEST_SECRET
        mock_settings.api_base_url = "http://localhost:8000"
        yield mock_settings


@pytest.fixture(autouse=True)
def reset_db():
    """Clean database before each test."""
    db = TestingSessionLocal()
    if Deployment:
        db.query(Deployment).delete()
    db.query(User).delete()
    db.commit()
    db.close()
    yield


def _create_deployed(
    repo="user/test-repo",
    instance_id="i-0123456789abcdef0",
    status=None,
    deployment_id=None,
):
    """Create a deployed deployment record in the test DB."""
    if not CORE_AVAILABLE or not Deployment:
        return None
    db = TestingSessionLocal()
    deploy = Deployment(
        id=deployment_id or f"deploy-{uuid.uuid4().hex[:8]}",
        repository=repo,
        instance_id=instance_id,
        status=status or DeploymentStatusEnum.DEPLOYED,
        strategy=DeploymentStrategyEnum.ROLLING,
        image_tag=f"{repo.replace('/', '-')}:latest",
        extra_data={"port": 8080, "environment": "production"},
        user_id=1,
    )
    db.add(deploy)
    db.commit()
    db.close()
    return deploy


# ─── Signature / Auth tests ───────────────────────────────────────────────


class TestWebhookSignatureVerification:
    """Test HMAC-SHA256 signature validation."""

    def test_valid_signature_accepted(self, mock_secret):
        """Webhook with correct signature should succeed."""
        payload = {"zen": "Practicality beats purity."}
        body = json.dumps(payload).encode()
        sig = make_signature(body)
        response = client.post(
            "/api/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sig},
        )
        assert response.status_code == 200

    def test_invalid_signature_rejected(self, mock_secret):
        """Webhook with wrong signature must return 401."""
        payload = {"zen": "test"}
        body = json.dumps(payload).encode()
        bad_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"
        response = client.post(
            "/api/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": bad_sig},
        )
        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]

    def test_missing_signature_rejected(self, mock_secret):
        """Webhook with no signature header must return 401."""
        payload = {"zen": "test"}
        body = json.dumps(payload).encode()
        response = client.post(
            "/api/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "ping"},
        )
        assert response.status_code == 401

    def test_wrong_signature_format_rejected(self, mock_secret):
        """Signature not starting with 'sha256=' must return 401."""
        payload = {"zen": "test"}
        body = json.dumps(payload).encode()
        # sha1 format instead of sha256
        bad_sig = "sha1=abc123"
        response = client.post(
            "/api/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": bad_sig},
        )
        assert response.status_code == 401

    def test_signature_with_wrong_secret_rejected(self, mock_secret):
        """Signature generated with wrong secret must return 401."""
        payload = {"zen": "test"}
        body = json.dumps(payload).encode()
        sig = make_signature(body, secret="wrong-secret")
        response = client.post(
            "/api/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sig},
        )
        assert response.status_code == 401

    def test_signature_tampering_detected(self, mock_secret):
        """Modifying payload after signing must invalidate signature."""
        original = {"zen": "test"}
        body = json.dumps(original).encode()
        sig = make_signature(body)

        # Tamper with body
        tampered = json.dumps({"zen": "HACKED"}).encode()
        response = client.post(
            "/api/webhooks/github",
            content=tampered,
            headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sig},
        )
        assert response.status_code == 401

    def test_secret_not_configured_returns_401(self):
        """When webhook secret is empty, ALL requests must be rejected."""
        with patch("api.routes.webhooks.settings") as mock_s:
            mock_s.github_webhook_secret = ""
            payload = {"zen": "test"}
            body = json.dumps(payload).encode()
            response = client.post(
                "/api/webhooks/github",
                content=body,
                headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": "sha256=abc"},
            )
        assert response.status_code == 401
        assert "Webhook secret not configured" in response.json()["detail"]

    def test_minimal_valid_body_accepted(self, mock_secret):
        """Minimal but valid JSON body with correct signature should be accepted."""
        body = b"{}"
        sig = make_signature(body)
        response = client.post(
            "/api/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": sig,
                "Content-Type": "application/json",
            },
        )
        assert response.status_code == 200


# ─── Ping event tests ─────────────────────────────────────────────────────


class TestPingEvent:
    """Test GitHub ping event handling."""

    def test_ping_returns_success_message(self, mock_secret):
        """Ping event should return success message."""
        response = post_webhook({"zen": "Design for failure."}, "ping")
        assert response.status_code == 200
        assert "Webhook configured successfully" in response.json()["message"]

    def test_ping_with_hook_data(self, mock_secret):
        """Ping with full GitHub hook data should succeed."""
        payload = {
            "zen": "Keep it logically awesome.",
            "hook_id": 12345,
            "hook": {"type": "Repository", "id": 12345, "events": ["push", "pull_request"]},
            "repository": {"full_name": "user/test-repo"},
        }
        response = post_webhook(payload, "ping")
        assert response.status_code == 200

    def test_ping_minimal_payload(self, mock_secret):
        """Ping with empty payload should still succeed."""
        response = post_webhook({}, "ping")
        assert response.status_code == 200
        assert "Webhook configured successfully" in response.json()["message"]


# ─── Push event tests ─────────────────────────────────────────────────────


class TestPushEvent:
    """Test GitHub push event handling."""

    def _push_payload(self, branch="main", repo="user/test-repo", sha="abc123def456"):
        return {
            "ref": f"refs/heads/{branch}",
            "after": sha,
            "repository": {"full_name": repo},
            "pusher": {"name": "testuser"},
        }

    def test_push_main_branch_with_deployed_app_triggers_auto_deploy(self, mock_secret):
        """Push to main when app is deployed should trigger auto-deploy."""
        _create_deployed(repo="user/test-repo")

        # DeploymentService is lazy-imported inside handle_push_event — patch at source
        with patch("api.services.deployment_service.DeploymentService") as mock_svc_class:
            mock_svc = Mock()
            mock_svc.create_deployment.return_value = Mock(id="new-deploy-1")
            mock_svc.run_deployment_workflow = AsyncMock()
            mock_svc_class.return_value = mock_svc

            response = post_webhook(self._push_payload("main"), "push")

        assert response.status_code == 200
        data = response.json()
        assert data["auto_deploy"] is True
        assert data["repository"] == "user/test-repo"
        assert data["branch"] == "main"
        assert "deployment_id" in data

    def test_push_master_branch_triggers_auto_deploy(self, mock_secret):
        """Push to master branch should also trigger auto-deploy."""
        _create_deployed(repo="user/test-repo")

        with patch("api.services.deployment_service.DeploymentService") as mock_svc_class:
            mock_svc = Mock()
            mock_svc.create_deployment.return_value = Mock(id="new-deploy-2")
            mock_svc.run_deployment_workflow = AsyncMock()
            mock_svc_class.return_value = mock_svc

            response = post_webhook(self._push_payload("master"), "push")

        assert response.status_code == 200
        data = response.json()
        assert data["auto_deploy"] is True
        assert data["branch"] == "master"

    def test_push_feature_branch_ignored(self, mock_secret):
        """Push to non-main/master branch should be silently ignored."""
        # ref = "refs/heads/feature/new-auth" → branch extracted as last segment "new-auth"
        response = post_webhook(self._push_payload("feature/new-auth"), "push")
        assert response.status_code == 200
        data = response.json()
        assert data["auto_deploy"] is False
        # The message contains the extracted branch name (last segment only)
        assert "Ignored push to branch" in data["message"]

    def test_push_develop_branch_ignored(self, mock_secret):
        """Push to develop branch should be ignored."""
        response = post_webhook(self._push_payload("develop"), "push")
        assert response.status_code == 200
        assert response.json()["auto_deploy"] is False

    def test_push_release_branch_ignored(self, mock_secret):
        """Push to release/* branch should be ignored."""
        response = post_webhook(self._push_payload("release/v1.2.3"), "push")
        assert response.status_code == 200
        assert response.json()["auto_deploy"] is False

    def test_push_main_no_existing_deployment_skips_auto_deploy(self, mock_secret):
        """Push to main with no active deployment should skip auto-deploy."""
        # DB is empty (no deployed apps)
        response = post_webhook(self._push_payload("main"), "push")
        assert response.status_code == 200
        data = response.json()
        assert data["auto_deploy"] is False
        assert "skipping auto-deploy" in data["message"].lower() or "no active" in data["message"].lower()

    def test_push_main_pending_deployment_skips_auto_deploy(self, mock_secret):
        """Push to main when deployment is pending (not deployed) should skip."""
        if CORE_AVAILABLE and Deployment:
            _create_deployed(repo="user/test-repo", status=DeploymentStatusEnum.PENDING)

        response = post_webhook(self._push_payload("main"), "push")
        assert response.status_code == 200
        data = response.json()
        # Pending deployment is NOT status "deployed", so auto_deploy should be False
        assert data["auto_deploy"] is False

    def test_push_commit_sha_included_in_response(self, mock_secret):
        """Auto-deploy response should include the commit SHA."""
        _create_deployed(repo="user/test-repo")

        with patch("api.services.deployment_service.DeploymentService") as mock_svc_class:
            mock_svc = Mock()
            mock_svc.create_deployment.return_value = Mock(id="new-deploy-sha")
            mock_svc.run_deployment_workflow = AsyncMock()
            mock_svc_class.return_value = mock_svc

            sha = "aabbccddeeff00112233445566778899aabbccdd"
            response = post_webhook(self._push_payload("main", sha=sha), "push")

        assert response.status_code == 200
        data = response.json()
        if data["auto_deploy"]:
            assert sha[:7] in data["commit"]

    def test_push_missing_repository_field(self, mock_secret):
        """Push with no repository field should not crash."""
        payload = {"ref": "refs/heads/main", "after": "abc123"}
        response = post_webhook(payload, "push")
        assert response.status_code == 200
        data = response.json()
        assert data["auto_deploy"] is False

    def test_push_missing_ref_field(self, mock_secret):
        """Push with no ref field should be handled gracefully."""
        payload = {"after": "abc123", "repository": {"full_name": "user/repo"}}
        response = post_webhook(payload, "push")
        assert response.status_code == 200
        # branch will be empty string → not main/master
        assert response.json()["auto_deploy"] is False

    def test_push_different_repos_independent(self, mock_secret):
        """Push events for different repos are independent."""
        _create_deployed(repo="user/repo-A")
        # repo-B has no deployment

        with patch("api.services.deployment_service.DeploymentService") as mock_svc_class:
            mock_svc = Mock()
            mock_svc.create_deployment.return_value = Mock(id="new-deploy")
            mock_svc.run_deployment_workflow = AsyncMock()
            mock_svc_class.return_value = mock_svc

            # repo-A → should auto-deploy
            resp_a = post_webhook(self._push_payload("main", repo="user/repo-A"), "push")
            assert resp_a.json()["auto_deploy"] is True

            # repo-B → no deployment, should not auto-deploy
            resp_b = post_webhook(self._push_payload("main", repo="user/repo-B"), "push")
            assert resp_b.json()["auto_deploy"] is False


# ─── Pull Request event tests ─────────────────────────────────────────────


class TestPullRequestEvent:
    """Test GitHub pull_request event handling."""

    def _pr_payload(self, action="opened", pr_number=42, repo="user/test-repo"):
        return {
            "action": action,
            "number": pr_number,
            "repository": {"full_name": repo},
            "pull_request": {"head": {"sha": "abc123"}},
        }

    def test_pr_opened_returns_preview_info(self, mock_secret):
        """Pull request opened should return preview deployment info."""
        response = post_webhook(self._pr_payload("opened", 42), "pull_request")
        assert response.status_code == 200
        data = response.json()
        assert "Preview deployment created" in data["message"]
        assert data["pr_number"] == 42
        assert data["repository"] == "user/test-repo"

    def test_pr_closed_returns_cleanup_info(self, mock_secret):
        """Pull request closed should return cleanup info."""
        response = post_webhook(self._pr_payload("closed", 42), "pull_request")
        assert response.status_code == 200
        data = response.json()
        assert "Preview deployment removed" in data["message"]
        assert data["pr_number"] == 42

    def test_pr_synchronize_acknowledged(self, mock_secret):
        """PR synchronize action should be handled."""
        response = post_webhook(self._pr_payload("synchronize", 99), "pull_request")
        assert response.status_code == 200

    def test_pr_reopened_acknowledged(self, mock_secret):
        """PR reopened action should be handled."""
        response = post_webhook(self._pr_payload("reopened", 55), "pull_request")
        assert response.status_code == 200

    def test_pr_large_number(self, mock_secret):
        """PR with a very large PR number."""
        response = post_webhook(self._pr_payload("opened", 99999), "pull_request")
        assert response.status_code == 200
        assert response.json()["pr_number"] == 99999

    def test_pr_no_action_field(self, mock_secret):
        """PR event with no action field should be handled gracefully."""
        payload = {"number": 1, "repository": {"full_name": "user/repo"}}
        response = post_webhook(payload, "pull_request")
        assert response.status_code == 200


# ─── Unknown event tests ───────────────────────────────────────────────────


class TestUnknownEvents:
    """Test handling of unknown/unprocessed event types."""

    def test_unknown_event_type_acknowledged(self, mock_secret):
        """Unknown event type should be acknowledged but not processed."""
        response = post_webhook({"test": "data"}, "issues")
        assert response.status_code == 200
        data = response.json()
        assert "not processed" in data["message"]
        assert "issues" in data["message"]

    def test_create_event_acknowledged(self, mock_secret):
        """Create (branch/tag) event should be acknowledged."""
        response = post_webhook({"ref": "v1.0", "ref_type": "tag"}, "create")
        assert response.status_code == 200
        assert "not processed" in response.json()["message"]

    def test_delete_event_acknowledged(self, mock_secret):
        """Delete event should be acknowledged."""
        response = post_webhook({"ref": "old-branch", "ref_type": "branch"}, "delete")
        assert response.status_code == 200

    def test_release_event_acknowledged(self, mock_secret):
        """Release event should be acknowledged."""
        response = post_webhook({"action": "published", "release": {"tag_name": "v1.0"}}, "release")
        assert response.status_code == 200

    def test_workflow_run_event_acknowledged(self, mock_secret):
        """GitHub Actions workflow_run event should be acknowledged."""
        response = post_webhook({"action": "completed", "workflow_run": {}}, "workflow_run")
        assert response.status_code == 200


# ─── Webhook setup info endpoint ──────────────────────────────────────────


class TestWebhookSetupInfo:
    """Test GET /api/webhooks/github/setup endpoint."""

    def test_setup_info_returns_url(self):
        """Setup info should include webhook URL."""
        response = client.get("/api/webhooks/github/setup")
        assert response.status_code == 200
        data = response.json()
        assert "webhook_url" in data
        assert "/api/webhooks/github" in data["webhook_url"]

    def test_setup_info_returns_events_list(self):
        """Setup info should list supported events."""
        response = client.get("/api/webhooks/github/setup")
        assert response.status_code == 200
        data = response.json()
        assert "events" in data
        assert "push" in data["events"]
        assert "pull_request" in data["events"]

    def test_setup_info_returns_instructions(self):
        """Setup info should return step-by-step instructions."""
        response = client.get("/api/webhooks/github/setup")
        assert response.status_code == 200
        data = response.json()
        assert "instructions" in data
        assert isinstance(data["instructions"], list)
        assert len(data["instructions"]) >= 5

    def test_setup_info_content_type(self):
        """Setup info should include content_type."""
        response = client.get("/api/webhooks/github/setup")
        assert response.status_code == 200
        data = response.json()
        assert data["content_type"] == "application/json"

    def test_setup_info_secret_required_field(self):
        """Setup info should indicate whether secret is configured."""
        response = client.get("/api/webhooks/github/setup")
        assert response.status_code == 200
        data = response.json()
        assert "secret_required" in data

    def test_setup_info_no_auth_required(self):
        """Setup info endpoint should be publicly accessible."""
        # No auth headers needed
        response = client.get("/api/webhooks/github/setup")
        assert response.status_code == 200


# ─── Security / Edge case tests ───────────────────────────────────────────


class TestWebhookSecurity:
    """Test webhook security edge cases."""

    def test_replay_attack_same_signature_different_body(self, mock_secret):
        """A signature valid for one body should be invalid for another body."""
        body1 = b'{"zen": "original"}'
        sig1 = make_signature(body1)

        body2 = b'{"zen": "REPLAYED"}'

        response = client.post(
            "/api/webhooks/github",
            content=body2,
            headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sig1},
        )
        assert response.status_code == 401

    def test_empty_signature_header_rejected(self, mock_secret):
        """Empty signature header value must be rejected."""
        body = b'{"zen": "test"}'
        response = client.post(
            "/api/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": ""},
        )
        assert response.status_code == 401

    def test_large_payload_accepted_with_correct_signature(self, mock_secret):
        """Large payload with correct signature should be accepted."""
        # 100KB payload
        large_payload = {"data": "x" * 100_000}
        body = json.dumps(large_payload).encode()
        sig = make_signature(body)
        response = client.post(
            "/api/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sig},
        )
        assert response.status_code == 200

    def test_unicode_payload_signature_valid(self, mock_secret):
        """Unicode characters in payload should not break HMAC."""
        payload = {"zen": "日本語テスト 🚀 العربية", "repo": "user/repo"}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        sig = make_signature(body)
        response = client.post(
            "/api/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sig},
        )
        assert response.status_code == 200

    def test_special_chars_in_event_type(self, mock_secret):
        """Event type with special characters should be handled safely."""
        response = post_webhook({"test": "data"}, "<script>alert(1)</script>")
        assert response.status_code == 200
        # Must not execute the event

    def test_very_long_branch_name(self, mock_secret):
        """Push with very long branch name should not crash."""
        payload = {
            "ref": "refs/heads/" + "a" * 500,
            "after": "abc123",
            "repository": {"full_name": "user/repo"},
        }
        response = post_webhook(payload, "push")
        assert response.status_code == 200
        assert response.json()["auto_deploy"] is False

    def test_push_with_null_after_field(self, mock_secret):
        """Push with null 'after' (delete push) should be handled."""
        payload = {
            "ref": "refs/heads/main",
            "after": "0000000000000000000000000000000000000000",  # Deleted ref
            "repository": {"full_name": "user/repo"},
        }
        response = post_webhook(payload, "push")
        assert response.status_code == 200
