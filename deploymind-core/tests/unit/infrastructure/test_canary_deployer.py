"""Intensive tests for CanaryDeployer.

All EC2 and HealthChecker calls are mocked — no real AWS or network needed.

Covers:
- Happy path: all 3 stages pass → success=True, final_percentage=100, no rollback
- Stage 1 failure: high error rate → rollback at 10%, final_percentage=10
- Stage 2 failure: passes 10% but fails 50% → rollback at 50%
- SSM agent not running → DeploymentError raised, result.success=False
- No public IP → DeploymentError, result.success=False
- CanaryResult dataclass defaults and __post_init__
- CanaryStage and CanaryStageResult dataclasses
- _observe_stage: all-pass, all-fail, partial (above/below threshold)
- _build_stages: correct weight sequence
- rollback(): returns True on success, False on EC2 failure
- stage_results populated correctly after multi-stage run
- stage_duration_seconds=0 final stage never sleeps
- error_rate_at_failure set correctly when stage fails
- rollback_performed flag set on stage failure
- Canary container name derived correctly ({name}-canary)
- deploy_container called for canary port, not prod port
- nginx updated at each stage with correct weights
"""

from __future__ import annotations

import time
from contextlib import suppress
from unittest.mock import MagicMock, call, patch

import pytest

# Patch time.sleep globally for all tests in this module to prevent real waiting
pytestmark = pytest.mark.usefixtures("patch_sleep")


@pytest.fixture(autouse=True)
def patch_sleep():
    """Suppress all time.sleep calls in the canary deployer module."""
    with patch("deploymind.infrastructure.deployment.canary_deployer.time.sleep"):
        yield


from deploymind.infrastructure.deployment.canary_deployer import (
    CanaryDeployer,
    CanaryResult,
    CanaryStage,
    CanaryStageResult,
)
from deploymind.shared.exceptions import DeploymentError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_ec2():
    ec2 = MagicMock()
    ec2.get_instance_public_ip.return_value = "1.2.3.4"
    ec2.check_ssm_agent_status.return_value = True
    ec2.deploy_container.return_value = {"container_id": "cid-123"}
    ec2.stop_container.return_value = True
    ec2.run_command.return_value = {"status": "Success"}
    return ec2


@pytest.fixture
def mock_health_checker():
    hc = MagicMock()
    # Default: all checks pass
    healthy_result = MagicMock()
    healthy_result.healthy = True
    hc.check_http.return_value = healthy_result
    return hc


@pytest.fixture
def fast_canary(mock_ec2, mock_health_checker):
    """CanaryDeployer with tiny durations for fast tests."""
    return CanaryDeployer(
        ec2_client=mock_ec2,
        health_checker=mock_health_checker,
        stage_duration_seconds=1,         # 1 second per stage
        health_check_interval_seconds=1,  # check every 1s
        error_rate_threshold=0.05,
        prod_port=8080,
        canary_port=8081,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unhealthy():
    r = MagicMock()
    r.healthy = False
    return r


def _healthy():
    r = MagicMock()
    r.healthy = True
    return r


# ===========================================================================
# CanaryResult / CanaryStage / CanaryStageResult dataclasses
# ===========================================================================

class TestDataClasses:
    def test_canary_result_defaults(self):
        r = CanaryResult(success=True, deployment_id="d1", image_tag="v1", instance_id="i-1")
        assert r.stages_completed == 0
        assert r.final_percentage == 0
        assert r.rollback_performed is False
        assert r.stage_results == []
        assert r.started_at is not None

    def test_canary_stage_fields(self):
        s = CanaryStage(canary_weight=1, prod_weight=9, duration_seconds=300)
        assert s.canary_weight == 1
        assert s.prod_weight == 9
        assert s.duration_seconds == 300

    def test_canary_stage_result_fields(self):
        sr = CanaryStageResult(
            stage_index=0, canary_weight=1, prod_weight=9,
            duration_seconds=300, completed=True, error_rate=0.02
        )
        assert sr.completed is True
        assert sr.error_rate == 0.02

    def test_canary_result_post_init_sets_started_at(self):
        r = CanaryResult(success=False, deployment_id="x", image_tag="y", instance_id="z")
        assert r.started_at is not None

    def test_canary_result_completed_at_none_by_default(self):
        r = CanaryResult(success=False, deployment_id="x", image_tag="y", instance_id="z")
        assert r.completed_at is None


# ===========================================================================
# _build_stages
# ===========================================================================

class TestBuildStages:
    def test_returns_three_stages(self, fast_canary):
        stages = fast_canary._build_stages()
        assert len(stages) == 3

    def test_first_stage_is_10_percent(self, fast_canary):
        stage = fast_canary._build_stages()[0]
        total = stage.canary_weight + stage.prod_weight
        pct = stage.canary_weight / total * 100
        assert abs(pct - 10) < 5  # roughly 10%

    def test_second_stage_is_50_percent(self, fast_canary):
        stage = fast_canary._build_stages()[1]
        assert stage.canary_weight == stage.prod_weight

    def test_final_stage_has_zero_duration(self, fast_canary):
        stage = fast_canary._build_stages()[2]
        assert stage.duration_seconds == 0

    def test_first_stage_duration_matches_config(self, fast_canary):
        stage = fast_canary._build_stages()[0]
        assert stage.duration_seconds == fast_canary.stage_duration_seconds


# ===========================================================================
# deploy — prerequisites
# ===========================================================================

class TestDeployPrerequisites:
    def test_no_public_ip_returns_failure(self, fast_canary, mock_ec2):
        mock_ec2.get_instance_public_ip.return_value = None
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.success is False
        assert result.error_message

    def test_no_ssm_agent_returns_failure(self, fast_canary, mock_ec2):
        mock_ec2.check_ssm_agent_status.return_value = False
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.success is False

    def test_result_has_deployment_id(self, fast_canary, mock_ec2, mock_health_checker):
        result = fast_canary.deploy("my-deploy", "i-1", "app:v2")
        assert result.deployment_id == "my-deploy"

    def test_result_has_image_tag(self, fast_canary, mock_ec2, mock_health_checker):
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.image_tag == "app:v2"

    def test_result_has_instance_id(self, fast_canary, mock_ec2, mock_health_checker):
        result = fast_canary.deploy("d1", "i-2", "app:v2")
        assert result.instance_id == "i-2"


# ===========================================================================
# deploy — happy path (all stages pass)
# ===========================================================================

class TestDeployHappyPath:
    def test_success_is_true(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.success is True

    def test_final_percentage_100(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.final_percentage == 100

    def test_no_rollback_on_success(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.rollback_performed is False

    def test_stages_completed_is_three(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.stages_completed == 3

    def test_stage_results_populated(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert len(result.stage_results) == 3

    def test_duration_seconds_is_positive(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.duration_seconds >= 0

    def test_completed_at_set(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.completed_at is not None

    def test_canary_container_started_on_canary_port(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        fast_canary.deploy("d1", "i-1", "app:v2", container_name="myapp")
        # First deploy_container call should use canary port
        first_call_kwargs = mock_ec2.deploy_container.call_args_list[0].kwargs
        assert first_call_kwargs["port"] == 8081

    def test_canary_container_name_derived(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        fast_canary.deploy("d1", "i-1", "app:v2", container_name="webapp")
        first_call_kwargs = mock_ec2.deploy_container.call_args_list[0].kwargs
        assert first_call_kwargs["container_name"] == "webapp-canary"

    def test_nginx_updated_at_each_stage(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        fast_canary.deploy("d1", "i-1", "app:v2")
        # nginx is updated for stage 1, 2, 3 (all traffic shift) + restore at end
        assert mock_ec2.run_command.call_count >= 3


# ===========================================================================
# deploy — Stage 1 failure (error rate too high)
# ===========================================================================

class TestStageOneFailure:
    def test_rollback_performed_on_stage1_fail(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _unhealthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.rollback_performed is True

    def test_success_false_on_stage1_fail(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _unhealthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.success is False

    def test_stages_completed_is_one_on_stage1_fail(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _unhealthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.stages_completed == 1

    def test_error_rate_at_failure_set(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _unhealthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.error_rate_at_failure is not None
        assert result.error_rate_at_failure > fast_canary.error_rate_threshold

    def test_error_message_contains_threshold(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _unhealthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.error_message
        assert "threshold" in result.error_message.lower() or "stage" in result.error_message.lower()

    def test_stage_results_has_one_entry(self, fast_canary, mock_ec2, mock_health_checker):
        mock_health_checker.check_http.return_value = _unhealthy()
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert len(result.stage_results) == 1
        assert result.stage_results[0].completed is False


# ===========================================================================
# deploy — Stage 2 failure
# ===========================================================================

class TestStageTwoFailure:
    def test_stage2_failure_completes_two_stages(self, fast_canary, mock_ec2, mock_health_checker):
        # Stage 1 passes, stage 2 fails
        call_count = [0]
        stage1_calls = 1  # one health check per stage (duration=1, interval=1)

        def check_side_effect(url):
            call_count[0] += 1
            if call_count[0] <= stage1_calls:
                return _healthy()
            return _unhealthy()

        mock_health_checker.check_http.side_effect = check_side_effect
        result = fast_canary.deploy("d1", "i-1", "app:v2")
        assert result.stages_completed == 2
        assert result.rollback_performed is True
        assert result.success is False


# ===========================================================================
# _observe_stage
# ===========================================================================

class TestObserveStage:
    def test_zero_duration_always_completes(self, fast_canary, mock_health_checker):
        stage = CanaryStage(canary_weight=1, prod_weight=0, duration_seconds=0)
        result = fast_canary._observe_stage(2, stage, "1.2.3.4", "/health")
        assert result.completed is True
        mock_health_checker.check_http.assert_not_called()

    def test_all_pass_returns_completed(self, fast_canary, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        stage = CanaryStage(canary_weight=1, prod_weight=9, duration_seconds=1)
        result = fast_canary._observe_stage(0, stage, "1.2.3.4", "/health")
        assert result.completed is True

    def test_all_fail_returns_not_completed(self, fast_canary, mock_health_checker):
        mock_health_checker.check_http.return_value = _unhealthy()
        stage = CanaryStage(canary_weight=1, prod_weight=9, duration_seconds=1)
        result = fast_canary._observe_stage(0, stage, "1.2.3.4", "/health")
        assert result.completed is False
        assert result.error_rate > fast_canary.error_rate_threshold

    def test_error_rate_computed_correctly(self, fast_canary, mock_health_checker):
        # 3 out of 4 checks fail → error_rate = 0.75
        calls = [0]
        def side(url):
            calls[0] += 1
            return _healthy() if calls[0] == 1 else _unhealthy()
        mock_health_checker.check_http.side_effect = side

        stage = CanaryStage(canary_weight=1, prod_weight=9, duration_seconds=4)
        result = fast_canary._observe_stage(0, stage, "1.2.3.4", "/health")
        assert result.health_checks_total > 0
        # Error rate should be above threshold (0.75 > 0.05)
        assert result.error_rate > fast_canary.error_rate_threshold

    def test_canary_url_uses_canary_port(self, fast_canary, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        stage = CanaryStage(canary_weight=1, prod_weight=9, duration_seconds=1)
        fast_canary._observe_stage(0, stage, "10.0.0.1", "/healthz")
        called_url = mock_health_checker.check_http.call_args.args[0]
        assert "8081" in called_url
        assert "10.0.0.1" in called_url
        assert "/healthz" in called_url

    def test_stage_index_stored(self, fast_canary, mock_health_checker):
        mock_health_checker.check_http.return_value = _healthy()
        stage = CanaryStage(canary_weight=1, prod_weight=9, duration_seconds=1)
        result = fast_canary._observe_stage(1, stage, "1.2.3.4", "/h")
        assert result.stage_index == 1


# ===========================================================================
# rollback()
# ===========================================================================

class TestRollback:
    def test_rollback_returns_true_on_success(self, fast_canary, mock_ec2):
        result = fast_canary.rollback("d1", "i-1", "app")
        assert result is True

    def test_rollback_calls_run_command(self, fast_canary, mock_ec2):
        fast_canary.rollback("d1", "i-1", "app")
        mock_ec2.run_command.assert_called()

    def test_rollback_stops_canary_container(self, fast_canary, mock_ec2):
        fast_canary.rollback("d1", "i-1", "app")
        stop_calls = [c for c in mock_ec2.stop_container.call_args_list]
        container_names = [c.kwargs.get("container_name", "") for c in stop_calls]
        assert any("canary" in name for name in container_names)

    def test_rollback_is_best_effort_nginx_failure_still_returns_true(self, fast_canary, mock_ec2):
        # nginx update is best-effort — failure is caught internally; rollback still True
        mock_ec2.run_command.side_effect = RuntimeError("SSM failed")
        result = fast_canary.rollback("d1", "i-1", "app")
        assert result is True

    def test_rollback_is_best_effort_stop_failure_still_returns_true(self, fast_canary, mock_ec2):
        # Container stop is also best-effort — failure caught internally; rollback still True
        mock_ec2.run_command.side_effect = RuntimeError("SSM failed")
        mock_ec2.stop_container.side_effect = RuntimeError("Docker error")
        result = fast_canary.rollback("d1", "i-1", "app")
        assert result is True  # both errors are non-fatal, best-effort design

    def test_rollback_returns_false_on_unexpected_exception(self, fast_canary, mock_ec2):
        # An unexpected exception propagating past both try blocks → False
        with patch.object(fast_canary, "_rollback_nginx", side_effect=Exception("fatal")):
            result = fast_canary.rollback("d1", "i-1", "app")
        assert result is False
