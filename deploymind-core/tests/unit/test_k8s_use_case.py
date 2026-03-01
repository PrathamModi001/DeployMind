"""Intensive unit tests for DeployToKubernetesUseCase.

All KubernetesClient calls are mocked — no live cluster required.
Covers rolling, canary, blue-green strategies and all validation paths.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from deploymind.application.use_cases.deploy_to_kubernetes import (
    DeployToKubernetesUseCase,
    K8sDeployRequest,
    K8sDeployResponse,
)
from deploymind.config.settings import Settings
from deploymind.shared.exceptions import DeploymentError, ValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def settings():
    return Settings(
        groq_api_key="test",
        aws_access_key_id="AKIATEST",
        aws_secret_access_key="secret",
        github_token="ghp_test",
        kubeconfig_path="/fake/.kube/config",
        kubernetes_namespace="default",
    )


@pytest.fixture
def mock_k8s_client():
    """Pre-configured mock KubernetesClient."""
    m = MagicMock()
    m.create_namespace.return_value = True
    m.deploy_to_kubernetes.return_value = True
    m.apply_service.return_value = True
    m.apply_ingress.return_value = True
    m.get_kubernetes_status.return_value = {
        "ready_replicas": 2,
        "desired_replicas": 2,
        "available": True,
    }
    m.rollback_kubernetes.return_value = True
    return m


@pytest.fixture
def use_case(settings, mock_k8s_client):
    with patch(
        "deploymind.application.use_cases.deploy_to_kubernetes.KubernetesClient",
        return_value=mock_k8s_client,
    ):
        uc = DeployToKubernetesUseCase(settings)
    return uc, mock_k8s_client


def _req(**kwargs):
    """Build a minimal valid K8sDeployRequest."""
    defaults = dict(
        deployment_id="deploy-test",
        name="myapp",
        image="myrepo/myapp:abc1234",
        namespace="default",
        replicas=2,
        port=8080,
        strategy="rolling",
    )
    defaults.update(kwargs)
    return K8sDeployRequest(**defaults)


# ---------------------------------------------------------------------------
# Rolling strategy
# ---------------------------------------------------------------------------

class TestRollingDeploy:
    def test_rolling_success(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req())
        assert response.success is True
        mock_k8s.deploy_to_kubernetes.assert_called_once()

    def test_rolling_creates_service_by_default(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req())
        assert response.service_created is True
        mock_k8s.apply_service.assert_called_once()

    def test_rolling_no_service_when_disabled(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req(create_service=False))
        assert response.service_created is False
        mock_k8s.apply_service.assert_not_called()

    def test_rolling_creates_ingress_when_requested(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req(create_ingress=True, ingress_host="myapp.example.com"))
        assert response.ingress_created is True
        assert response.ingress_host == "myapp.example.com"
        mock_k8s.apply_ingress.assert_called_once()

    def test_rolling_response_fields(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req(namespace="prod"))
        assert response.deployment_id == "deploy-test"
        assert response.name == "myapp"
        assert response.namespace == "prod"
        assert response.strategy == "rolling"
        assert response.image == "myrepo/myapp:abc1234"
        assert response.ready_replicas == 2
        assert response.desired_replicas == 2

    def test_rolling_duration_recorded(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req())
        assert response.duration_seconds is not None
        assert response.duration_seconds >= 0

    def test_rolling_applied_manifests_populated(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req())
        assert len(response.applied_manifests) >= 1

    def test_rolling_namespace_created(self, use_case):
        uc, mock_k8s = use_case
        uc.execute(_req(namespace="new-ns"))
        mock_k8s.create_namespace.assert_called_with("new-ns")

    def test_rolling_failure_propagated(self, use_case):
        uc, mock_k8s = use_case
        mock_k8s.deploy_to_kubernetes.side_effect = DeploymentError("cluster unreachable")
        response = uc.execute(_req())
        assert response.success is False
        assert "cluster unreachable" in response.error_message
        assert response.error_phase == "deploy"

    def test_rolling_unexpected_error_caught(self, use_case):
        uc, mock_k8s = use_case
        mock_k8s.deploy_to_kubernetes.side_effect = RuntimeError("unexpected boom")
        response = uc.execute(_req())
        assert response.success is False
        assert response.error_phase == "unknown"

    def test_rolling_timestamps_set(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req())
        assert response.started_at is not None
        assert response.completed_at is not None
        assert response.completed_at >= response.started_at

    def test_rolling_status_fallback_on_get_status_failure(self, use_case):
        uc, mock_k8s = use_case
        mock_k8s.get_kubernetes_status.side_effect = DeploymentError("not found")
        response = uc.execute(_req(replicas=3))
        assert response.success is True  # Overall still succeeded
        assert response.desired_replicas == 3  # Fallback to request value


# ---------------------------------------------------------------------------
# Canary strategy
# ---------------------------------------------------------------------------

class TestCanaryDeploy:
    def test_canary_success(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req(strategy="canary", stable_image="myapp:v1"))
        assert response.success is True
        # Two deploy_to_kubernetes calls: stable + canary
        assert mock_k8s.deploy_to_kubernetes.call_count == 2

    def test_canary_stable_image_required(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req(strategy="canary", stable_image=None))
        assert response.success is False
        assert "stable_image" in response.error_message

    def test_canary_deploys_two_deployments(self, use_case):
        uc, mock_k8s = use_case
        uc.execute(_req(strategy="canary", stable_image="myapp:v1"))
        calls = mock_k8s.deploy_to_kubernetes.call_args_list
        names = [c[0][1].get("metadata", {}).get("name", "") for c in calls]
        assert any("stable" in n for n in names)
        assert any("canary" in n for n in names)

    def test_canary_custom_replica_split(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req(
            strategy="canary", stable_image="myapp:v1",
            stable_replicas=4, canary_replicas=1
        ))
        assert response.success is True
        calls = mock_k8s.deploy_to_kubernetes.call_args_list
        stable_manifest = next(
            c[0][1] for c in calls
            if "stable" in c[0][1].get("metadata", {}).get("name", "")
        )
        assert stable_manifest["spec"]["replicas"] == 4


# ---------------------------------------------------------------------------
# Blue-green strategy
# ---------------------------------------------------------------------------

class TestBlueGreenDeploy:
    def test_blue_green_success(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req(strategy="blue-green", active_color="blue"))
        assert response.success is True

    def test_blue_green_deploys_both_colors(self, use_case):
        uc, mock_k8s = use_case
        uc.execute(_req(strategy="blue-green", active_color="blue"))
        calls = mock_k8s.deploy_to_kubernetes.call_args_list
        names = [c[0][1].get("metadata", {}).get("name", "") for c in calls]
        assert any("blue" in n for n in names)
        assert any("green" in n for n in names)

    def test_blue_green_updates_service_selector(self, use_case):
        uc, mock_k8s = use_case
        uc.execute(_req(strategy="blue-green", active_color="blue"))
        # apply_service called for the BG promotion + possibly create_service
        mock_k8s.apply_service.assert_called()

    def test_blue_green_accepts_underscore_variant(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req(strategy="blue_green", active_color="green"))
        assert response.success is True

    def test_blue_green_invalid_color(self, use_case):
        uc, mock_k8s = use_case
        response = uc.execute(_req(strategy="blue-green", active_color="purple"))
        assert response.success is False
        assert "active_color" in response.error_message


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestValidation:
    def test_empty_deployment_id_fails(self, use_case):
        uc, _ = use_case
        response = uc.execute(_req(deployment_id=""))
        assert response.success is False
        assert response.error_phase == "validation"

    def test_empty_name_fails(self, use_case):
        uc, _ = use_case
        response = uc.execute(_req(name=""))
        assert response.success is False
        assert response.error_phase == "validation"

    def test_empty_image_fails(self, use_case):
        uc, _ = use_case
        response = uc.execute(_req(image=""))
        assert response.success is False
        assert response.error_phase == "validation"

    def test_empty_namespace_fails(self, use_case):
        uc, _ = use_case
        response = uc.execute(_req(namespace=""))
        assert response.success is False

    def test_zero_replicas_fails(self, use_case):
        uc, _ = use_case
        response = uc.execute(_req(replicas=0))
        assert response.success is False
        assert "replicas" in response.error_message

    def test_invalid_port_zero(self, use_case):
        uc, _ = use_case
        response = uc.execute(_req(port=0))
        assert response.success is False
        assert "port" in response.error_message

    def test_invalid_port_too_high(self, use_case):
        uc, _ = use_case
        response = uc.execute(_req(port=99999))
        assert response.success is False

    def test_invalid_health_check_path(self, use_case):
        uc, _ = use_case
        response = uc.execute(_req(health_check_path="health"))
        assert response.success is False

    def test_unknown_strategy_fails(self, use_case):
        uc, _ = use_case
        response = uc.execute(_req(strategy="magic"))
        assert response.success is False
        assert "strategy" in response.error_message.lower()

    def test_canary_requires_stable_image_validation(self, use_case):
        uc, _ = use_case
        response = uc.execute(_req(strategy="canary"))
        assert response.success is False
        assert "stable_image" in response.error_message

    def test_ingress_requires_host_validation(self, use_case):
        uc, _ = use_case
        response = uc.execute(_req(create_ingress=True, ingress_host=None))
        assert response.success is False
        assert "ingress_host" in response.error_message

    def test_valid_port_boundaries(self, use_case):
        uc, _ = use_case
        # Port 1 (minimum)
        assert uc.execute(_req(port=1)).success is True
        # Port 65535 (maximum)
        assert uc.execute(_req(port=65535)).success is True

    def test_valid_replicas_1(self, use_case):
        uc, _ = use_case
        assert uc.execute(_req(replicas=1)).success is True


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettings:
    def test_k8s_settings_have_defaults(self):
        s = Settings(groq_api_key="t", aws_access_key_id="A",
                     aws_secret_access_key="s", github_token="g")
        assert s.kubeconfig_path == ""
        assert s.kubernetes_namespace == "default"
        assert s.kubernetes_cluster_name == ""

    def test_k8s_settings_loaded_from_env(self, monkeypatch):
        monkeypatch.setenv("KUBECONFIG_PATH", "/home/user/.kube/config")
        monkeypatch.setenv("KUBERNETES_NAMESPACE", "production")
        monkeypatch.setenv("KUBERNETES_CLUSTER_NAME", "my-cluster")
        s = Settings.load()
        assert s.kubeconfig_path == "/home/user/.kube/config"
        assert s.kubernetes_namespace == "production"
        assert s.kubernetes_cluster_name == "my-cluster"
