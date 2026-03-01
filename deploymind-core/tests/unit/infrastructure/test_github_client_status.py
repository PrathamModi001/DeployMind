"""Tests for the new GitHub status / PR-comment methods on GitHubClient.

All GitHub API calls are mocked — no real network required.

Covers:
- post_deployment_status: valid states, description truncation, target_url optional,
  invalid state raises ValueError, GithubException propagated
- create_pr_comment: body forwarded, GithubException propagated
- get_pr_for_branch: open PR found, no PR found, GithubException propagated
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from github import GithubException

from deploymind.infrastructure.vcs.github.github_client import GitHubClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_settings():
    s = MagicMock()
    s.github_token = "ghp_test_token"
    return s


@pytest.fixture
def client(mock_settings):
    return GitHubClient(settings=mock_settings)


@pytest.fixture
def mock_repo():
    """A MagicMock representing a PyGithub Repository object."""
    repo = MagicMock()
    repo.owner.login = "owner"
    return repo


def _patch_get_repo(client, mock_repo):
    """Convenience: make client.get_repository always return mock_repo."""
    client.get_repository = MagicMock(return_value=mock_repo)


# ===========================================================================
# post_deployment_status
# ===========================================================================

class TestPostDeploymentStatus:
    def test_valid_pending_state(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_commit = MagicMock()
        mock_repo.get_commit.return_value = mock_commit

        client.post_deployment_status(
            "owner/repo", "abc123", "pending", "Building…"
        )

        mock_commit.create_status.assert_called_once()
        call_kwargs = mock_commit.create_status.call_args.kwargs
        assert call_kwargs["state"] == "pending"

    def test_valid_success_state(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_commit = MagicMock()
        mock_repo.get_commit.return_value = mock_commit

        client.post_deployment_status("owner/repo", "sha", "success", "Deployed!")

        call_kwargs = mock_commit.create_status.call_args.kwargs
        assert call_kwargs["state"] == "success"

    def test_valid_failure_state(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_commit = MagicMock()
        mock_repo.get_commit.return_value = mock_commit

        client.post_deployment_status("owner/repo", "sha", "failure", "Build failed")
        call_kwargs = mock_commit.create_status.call_args.kwargs
        assert call_kwargs["state"] == "failure"

    def test_valid_error_state(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_commit = MagicMock()
        mock_repo.get_commit.return_value = mock_commit

        client.post_deployment_status("owner/repo", "sha", "error", "Internal error")
        call_kwargs = mock_commit.create_status.call_args.kwargs
        assert call_kwargs["state"] == "error"

    def test_invalid_state_raises_value_error(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        with pytest.raises(ValueError, match="state must be one of"):
            client.post_deployment_status("owner/repo", "sha", "running", "msg")

    def test_description_truncated_to_140_chars(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_commit = MagicMock()
        mock_repo.get_commit.return_value = mock_commit

        long_desc = "x" * 200
        client.post_deployment_status("owner/repo", "sha", "pending", long_desc)

        call_kwargs = mock_commit.create_status.call_args.kwargs
        assert len(call_kwargs["description"]) == 140

    def test_description_not_truncated_when_short(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_commit = MagicMock()
        mock_repo.get_commit.return_value = mock_commit

        client.post_deployment_status("owner/repo", "sha", "success", "OK")
        call_kwargs = mock_commit.create_status.call_args.kwargs
        assert call_kwargs["description"] == "OK"

    def test_default_context(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_commit = MagicMock()
        mock_repo.get_commit.return_value = mock_commit

        client.post_deployment_status("owner/repo", "sha", "pending", "msg")
        call_kwargs = mock_commit.create_status.call_args.kwargs
        assert call_kwargs["context"] == "deploymind/deployment"

    def test_custom_context(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_commit = MagicMock()
        mock_repo.get_commit.return_value = mock_commit

        client.post_deployment_status(
            "owner/repo", "sha", "pending", "msg", context="ci/tests"
        )
        call_kwargs = mock_commit.create_status.call_args.kwargs
        assert call_kwargs["context"] == "ci/tests"

    def test_target_url_included_when_provided(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_commit = MagicMock()
        mock_repo.get_commit.return_value = mock_commit

        client.post_deployment_status(
            "owner/repo", "sha", "success", "ok",
            target_url="https://logs.example.com/build/123"
        )
        call_kwargs = mock_commit.create_status.call_args.kwargs
        assert call_kwargs["target_url"] == "https://logs.example.com/build/123"

    def test_target_url_omitted_when_empty(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_commit = MagicMock()
        mock_repo.get_commit.return_value = mock_commit

        client.post_deployment_status("owner/repo", "sha", "pending", "msg")
        call_kwargs = mock_commit.create_status.call_args.kwargs
        assert "target_url" not in call_kwargs

    def test_github_exception_propagated(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_commit = MagicMock()
        mock_repo.get_commit.return_value = mock_commit
        mock_commit.create_status.side_effect = GithubException(403, "Forbidden", {})

        with pytest.raises(GithubException):
            client.post_deployment_status("owner/repo", "sha", "success", "ok")


# ===========================================================================
# create_pr_comment
# ===========================================================================

class TestCreatePrComment:
    def test_comment_body_forwarded(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_pr = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        client.create_pr_comment("owner/repo", 7, "Deployment successful! 🎉")

        mock_pr.create_issue_comment.assert_called_once_with("Deployment successful! 🎉")

    def test_pr_number_used_to_fetch(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_pr = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        client.create_pr_comment("owner/repo", 42, "hello")

        mock_repo.get_pull.assert_called_once_with(42)

    def test_multiline_markdown_body(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_pr = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        body = "## Result\n- Success\n- Image: `myapp:v1.0`"
        client.create_pr_comment("owner/repo", 1, body)

        mock_pr.create_issue_comment.assert_called_once_with(body)

    def test_github_exception_propagated(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_repo.get_pull.side_effect = GithubException(404, "Not Found", {})

        with pytest.raises(GithubException):
            client.create_pr_comment("owner/repo", 999, "oops")


# ===========================================================================
# get_pr_for_branch
# ===========================================================================

class TestGetPrForBranch:
    def test_returns_pr_number_when_found(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_pr = MagicMock()
        mock_pr.number = 55
        mock_repo.get_pulls.return_value = iter([mock_pr])

        result = client.get_pr_for_branch("owner/repo", "feature/xyz")

        assert result == 55

    def test_returns_none_when_no_open_pr(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_repo.get_pulls.return_value = iter([])

        result = client.get_pr_for_branch("owner/repo", "feature/no-pr")

        assert result is None

    def test_returns_first_pr_when_multiple(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        pr1 = MagicMock()
        pr1.number = 10
        pr2 = MagicMock()
        pr2.number = 20
        mock_repo.get_pulls.return_value = iter([pr1, pr2])

        result = client.get_pr_for_branch("owner/repo", "shared-branch")

        assert result == 10

    def test_head_filter_includes_owner_prefix(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_repo.get_pulls.return_value = iter([])

        client.get_pr_for_branch("owner/repo", "feat/login")

        call_kwargs = mock_repo.get_pulls.call_args.kwargs
        assert call_kwargs["state"] == "open"
        assert "owner:feat/login" in call_kwargs["head"]

    def test_github_exception_propagated(self, client, mock_repo):
        _patch_get_repo(client, mock_repo)
        mock_repo.get_pulls.side_effect = GithubException(500, "Server Error", {})

        with pytest.raises(GithubException):
            client.get_pr_for_branch("owner/repo", "main")
