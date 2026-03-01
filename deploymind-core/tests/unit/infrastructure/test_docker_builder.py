"""Intensive tests for DockerBuilder.

All tests mock subprocess so Docker is not required to run the test suite.

Covers:
- Successful build: returncode 0, metadata extracted via inspect
- Failed build: returncode != 0, error extraction from log tail
- Input validation: missing Dockerfile, non-dir context, empty tag
- Docker not installed: FileNotFoundError → clean error result
- Unexpected exception propagation
- Warning detection in build output
- _extract_error heuristics (error lines, failed lines, fallback)
- _inspect_image: success, returncode != 0, malformed JSON, timeout, list vs dict
- image_exists, remove_image, pull_image utility methods
- build_args, no_cache, pull, target flags in constructed command
- Streaming output via _stream_output
- Duration is always populated
- BuildResult dataclass defaults
"""

from __future__ import annotations

import json
import subprocess
from io import StringIO
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, Mock, patch, PropertyMock, call

import pytest

from deploymind.infrastructure.build.docker_builder import BuildResult, DockerBuilder


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def builder() -> DockerBuilder:
    return DockerBuilder()


@pytest.fixture
def tmp_dockerfile(tmp_path: Path) -> Path:
    """Create a minimal Dockerfile and return its path."""
    df = tmp_path / "Dockerfile"
    df.write_text("FROM python:3.12-slim\nUSER 1001")
    return df


def _make_popen(returncode: int = 0, output_lines: list[str] | None = None) -> MagicMock:
    """Return a mock Popen that yields *output_lines* from stdout."""
    lines = output_lines or []
    mock = MagicMock()
    mock.stdout = iter(line + "\n" for line in lines)
    mock.wait.return_value = returncode
    mock.returncode = returncode
    return mock


def _inspect_response(image_id: str = "sha256:abcdef123456", size: int = 100_000_000, layers: int = 5) -> str:
    """JSON that `docker image inspect` would return (as a list)."""
    return json.dumps([{
        "Id": image_id,
        "Size": size,
        "RootFS": {"Layers": [f"sha256:{i}" * 4 for i in range(layers)]},
    }])


# ===========================================================================
# Input validation
# ===========================================================================

class TestInputValidation:
    def test_missing_dockerfile_returns_failure(self, builder, tmp_path):
        result = builder.build(
            image_tag="myapp:test",
            dockerfile_path=str(tmp_path / "nonexistent_Dockerfile"),
            context_path=str(tmp_path),
        )
        assert result.success is False
        assert "Dockerfile not found" in result.error_message

    def test_context_not_directory_returns_failure(self, builder, tmp_path):
        df = tmp_path / "Dockerfile"
        df.write_text("FROM python:3.12-slim")
        result = builder.build(
            image_tag="myapp:test",
            dockerfile_path=str(df),
            context_path=str(df),  # <-- a file, not a dir
        )
        assert result.success is False
        assert "not a directory" in result.error_message

    def test_empty_image_tag_returns_failure(self, builder, tmp_path, tmp_dockerfile):
        result = builder.build(
            image_tag="",
            dockerfile_path=str(tmp_dockerfile),
            context_path=str(tmp_path),
        )
        assert result.success is False
        assert "empty" in result.error_message.lower()

    def test_whitespace_image_tag_returns_failure(self, builder, tmp_path, tmp_dockerfile):
        result = builder.build(
            image_tag="   ",
            dockerfile_path=str(tmp_dockerfile),
            context_path=str(tmp_path),
        )
        assert result.success is False


# ===========================================================================
# Successful build
# ===========================================================================

class TestSuccessfulBuild:
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.run")
    def test_success_returns_true(self, mock_run, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(0, ["Step 1/5", "Step 2/5", "Successfully built abc123"])
        mock_run.return_value = Mock(returncode=0, stdout=_inspect_response())
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert result.success is True
        assert result.image_tag == "myapp:test"

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.run")
    def test_success_populates_image_metadata(self, mock_run, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(0, ["Built"])
        mock_run.return_value = Mock(returncode=0, stdout=_inspect_response(
            image_id="sha256:deadbeef1234", size=52_428_800, layers=7
        ))
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert result.success is True
        assert result.image_size_mb == pytest.approx(50.0, rel=0.01)
        assert result.layers == 7
        assert result.image_id is not None

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.run")
    def test_build_log_captured(self, mock_run, mock_popen, builder, tmp_path, tmp_dockerfile):
        lines = ["Step 1/4: FROM python", "Step 2/4: COPY", "Successfully built"]
        mock_popen.return_value = _make_popen(0, lines)
        mock_run.return_value = Mock(returncode=0, stdout=_inspect_response())
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        for line in lines:
            assert line in result.build_log

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.run")
    def test_duration_populated_on_success(self, mock_run, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(0, ["Done"])
        mock_run.return_value = Mock(returncode=0, stdout=_inspect_response())
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert result.duration_seconds is not None
        assert result.duration_seconds >= 0

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.run")
    def test_warning_detection_in_output(self, mock_run, mock_popen, builder, tmp_path, tmp_dockerfile):
        lines = ["Step 1: FROM", "DeprecationWarning: MAINTAINER is deprecated", "Built"]
        mock_popen.return_value = _make_popen(0, lines)
        mock_run.return_value = Mock(returncode=0, stdout=_inspect_response())
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert len(result.warnings) >= 1
        assert any("deprecated" in w.lower() or "DeprecationWarning" in w for w in result.warnings)


# ===========================================================================
# Failed build
# ===========================================================================

class TestFailedBuild:
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    def test_failure_returns_false(self, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(1, ["Step 1/2", "ERROR: something went wrong"])
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert result.success is False

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    def test_error_message_extracted_from_log(self, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(1, [
            "Step 1", "Step 2", "ERROR: permission denied"
        ])
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert result.error_message is not None
        assert len(result.error_message) > 0

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    def test_build_log_captured_on_failure(self, mock_popen, builder, tmp_path, tmp_dockerfile):
        lines = ["Step 1", "Error: build failed"]
        mock_popen.return_value = _make_popen(1, lines)
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert "Step 1" in result.build_log

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    def test_duration_populated_on_failure(self, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(1, ["Failed"])
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert result.duration_seconds is not None

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    def test_empty_log_produces_fallback_error(self, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(1, [])
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert result.error_message is not None


# ===========================================================================
# Docker not installed
# ===========================================================================

class TestDockerNotInstalled:
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen",
           side_effect=FileNotFoundError("docker: command not found"))
    def test_file_not_found_returns_clean_error(self, mock_popen, builder, tmp_path, tmp_dockerfile):
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert result.success is False
        assert "not installed" in result.error_message.lower() or "PATH" in result.error_message

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen",
           side_effect=FileNotFoundError())
    def test_duration_set_even_when_docker_missing(self, mock_popen, builder, tmp_path, tmp_dockerfile):
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert result.duration_seconds is not None


# ===========================================================================
# Unexpected exception
# ===========================================================================

class TestUnexpectedException:
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen",
           side_effect=RuntimeError("Kernel panic"))
    def test_unexpected_exception_returns_failure(self, mock_popen, builder, tmp_path, tmp_dockerfile):
        result = builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        assert result.success is False
        assert result.error_message is not None


# ===========================================================================
# Command construction
# ===========================================================================

class TestCommandConstruction:
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.run")
    def test_build_args_included(self, mock_run, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(0, ["Built"])
        mock_run.return_value = Mock(returncode=0, stdout=_inspect_response())
        builder.build(
            "myapp:test", str(tmp_dockerfile), str(tmp_path),
            build_args={"NODE_ENV": "production", "VERSION": "1.0"},
        )
        cmd = mock_popen.call_args[0][0]
        assert "--build-arg" in cmd
        assert "NODE_ENV=production" in cmd
        assert "VERSION=1.0" in cmd

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.run")
    def test_no_cache_flag(self, mock_run, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(0, ["Built"])
        mock_run.return_value = Mock(returncode=0, stdout=_inspect_response())
        builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path), no_cache=True)
        cmd = mock_popen.call_args[0][0]
        assert "--no-cache" in cmd

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.run")
    def test_pull_flag(self, mock_run, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(0, ["Built"])
        mock_run.return_value = Mock(returncode=0, stdout=_inspect_response())
        builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path), pull=True)
        cmd = mock_popen.call_args[0][0]
        assert "--pull" in cmd

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.run")
    def test_target_flag(self, mock_run, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(0, ["Built"])
        mock_run.return_value = Mock(returncode=0, stdout=_inspect_response())
        builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path), target="runner")
        cmd = mock_popen.call_args[0][0]
        assert "--target" in cmd
        assert "runner" in cmd

    @patch("deploymind.infrastructure.build.docker_builder.subprocess.Popen")
    @patch("deploymind.infrastructure.build.docker_builder.subprocess.run")
    def test_no_extra_flags_by_default(self, mock_run, mock_popen, builder, tmp_path, tmp_dockerfile):
        mock_popen.return_value = _make_popen(0, ["Built"])
        mock_run.return_value = Mock(returncode=0, stdout=_inspect_response())
        builder.build("myapp:test", str(tmp_dockerfile), str(tmp_path))
        cmd = mock_popen.call_args[0][0]
        assert "--no-cache" not in cmd
        assert "--pull" not in cmd
        assert "--target" not in cmd


# ===========================================================================
# _inspect_image
# ===========================================================================

class TestInspectImage:
    def test_successful_inspect(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=_inspect_response(size=10_485_760, layers=3),
            )
            image_id, size_mb, layers = builder._inspect_image("myapp:test")
        assert size_mb == pytest.approx(10.0, rel=0.01)
        assert layers == 3
        assert image_id is not None

    def test_inspect_nonzero_returncode_returns_nones(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="")
            result = builder._inspect_image("notexist:latest")
        assert result == (None, None, 0)

    def test_inspect_malformed_json_returns_nones(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="{{{ bad json")
            result = builder._inspect_image("myapp:test")
        assert result == (None, None, 0)

    def test_inspect_timeout_returns_nones(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=30)):
            result = builder._inspect_image("myapp:test")
        assert result == (None, None, 0)

    def test_inspect_dict_format_also_handled(self, builder):
        """docker inspect can return a bare dict (not a list) in some versions."""
        data = {
            "Id": "sha256:abc123",
            "Size": 20_971_520,
            "RootFS": {"Layers": ["a", "b", "c", "d"]},
        }
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=json.dumps(data))
            image_id, size_mb, layers = builder._inspect_image("myapp:test")
        assert size_mb == pytest.approx(20.0, rel=0.01)
        assert layers == 4

    def test_zero_size_returns_none_mb(self, builder):
        data = [{"Id": "sha256:abc", "Size": 0, "RootFS": {"Layers": []}}]
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=json.dumps(data))
            _, size_mb, _ = builder._inspect_image("myapp:test")
        assert size_mb is None


# ===========================================================================
# _extract_error
# ===========================================================================

class TestExtractError:
    def test_picks_error_line_from_tail(self, builder):
        lines = ["Step 1", "Step 2", "ERROR: permission denied writing /app"]
        assert "permission denied" in builder._extract_error(lines)

    def test_picks_failed_line(self, builder):
        lines = ["Step 1", "The command failed: npm install"]
        assert "failed" in builder._extract_error(lines).lower()

    def test_falls_back_to_last_line(self, builder):
        lines = ["Some output", "More output", "Last line of build"]
        result = builder._extract_error(lines)
        assert result == "Last line of build"

    def test_empty_log_returns_fallback_string(self, builder):
        result = builder._extract_error([])
        assert isinstance(result, str)
        assert len(result) > 0

    def test_only_empty_lines_returns_fallback(self, builder):
        result = builder._extract_error(["", "  ", "\t"])
        assert isinstance(result, str)


# ===========================================================================
# Utility methods
# ===========================================================================

class TestUtilityMethods:
    def test_image_exists_true(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as m:
            m.return_value = Mock(returncode=0)
            assert builder.image_exists("myapp:test") is True

    def test_image_exists_false_on_nonzero(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as m:
            m.return_value = Mock(returncode=1)
            assert builder.image_exists("myapp:test") is False

    def test_image_exists_false_on_exception(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run",
                   side_effect=Exception("error")):
            assert builder.image_exists("myapp:test") is False

    def test_remove_image_success(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as m:
            m.return_value = Mock(returncode=0)
            assert builder.remove_image("myapp:test") is True

    def test_remove_image_failure(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as m:
            m.return_value = Mock(returncode=1)
            assert builder.remove_image("myapp:test") is False

    def test_remove_image_force_flag(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as m:
            m.return_value = Mock(returncode=0)
            builder.remove_image("myapp:test", force=True)
            cmd = m.call_args[0][0]
            assert "--force" in cmd

    def test_pull_image_success(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as m:
            m.return_value = Mock(returncode=0)
            assert builder.pull_image("python:3.12-slim") is True

    def test_pull_image_failure(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run") as m:
            m.return_value = Mock(returncode=1)
            assert builder.pull_image("nonexistent:image") is False

    def test_pull_image_exception(self, builder):
        with patch("deploymind.infrastructure.build.docker_builder.subprocess.run",
                   side_effect=Exception("network error")):
            assert builder.pull_image("python:3.12") is False


# ===========================================================================
# BuildResult dataclass
# ===========================================================================

class TestBuildResultDefaults:
    def test_defaults(self):
        r = BuildResult(success=True, image_tag="myapp:v1")
        assert r.image_size_mb is None
        assert r.image_id is None
        assert r.build_log == ""
        assert r.duration_seconds is None
        assert r.error_message is None
        assert r.layers == 0
        assert r.warnings == []

    def test_warnings_independent_across_instances(self):
        r1 = BuildResult(success=True, image_tag="a:1")
        r2 = BuildResult(success=True, image_tag="b:2")
        r1.warnings.append("warn")
        assert r2.warnings == []
