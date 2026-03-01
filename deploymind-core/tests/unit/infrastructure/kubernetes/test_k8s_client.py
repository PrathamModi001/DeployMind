"""Intensive unit tests for KubernetesClient.

All Kubernetes API calls are mocked — no live cluster required.
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from deploymind.infrastructure.cloud.kubernetes.k8s_client import KubernetesClient
from deploymind.config.settings import Settings
from deploymind.shared.exceptions import DeploymentError
from kubernetes.client.rest import ApiException


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def settings():
    return Settings(
        groq_api_key="test",
        aws_access_key_id="AKIATEST",
        aws_secret_access_key="test-secret",
        aws_region="us-east-1",
        github_token="ghp_test",
        kubeconfig_path="/fake/.kube/config",
        kubernetes_namespace="test-ns",
    )


@pytest.fixture
def mock_apps_v1():
    return MagicMock()


@pytest.fixture
def mock_core_v1():
    return MagicMock()


@pytest.fixture
def mock_networking_v1():
    return MagicMock()


@pytest.fixture
def k8s_client_with_mocks(settings, mock_apps_v1, mock_core_v1, mock_networking_v1):
    """KubernetesClient with all API clients pre-mocked."""
    with patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.k8s_config") as cfg, \
         patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.k8s_client") as sdk:
        sdk.AppsV1Api.return_value = mock_apps_v1
        sdk.CoreV1Api.return_value = mock_core_v1
        sdk.NetworkingV1Api.return_value = mock_networking_v1
        client = KubernetesClient(settings)
    return client


def _make_deployment(name="app", ready=2, desired=2, updated=2, available=2,
                     gen=1, meta_gen=1):
    """Helper: create a mock Deployment k8s object."""
    d = MagicMock()
    d.metadata.name = name
    d.metadata.generation = meta_gen
    d.metadata.annotations = {"deployment.kubernetes.io/revision": "2"}
    d.spec.replicas = desired
    d.status.ready_replicas = ready
    d.status.updated_replicas = updated
    d.status.available_replicas = available
    d.status.observed_generation = gen
    d.status.conditions = []
    return d


def _api_exc(status: int, reason: str = "Error") -> ApiException:
    """Create a real ApiException — the only type that can be raised/caught."""
    return ApiException(status=status, reason=reason)


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

class TestKubernetesClientInit:
    def test_init_loads_from_kubeconfig_path(self, settings):
        with patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.k8s_config") as cfg, \
             patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.k8s_client") as sdk:
            sdk.AppsV1Api.return_value = MagicMock()
            sdk.CoreV1Api.return_value = MagicMock()
            sdk.NetworkingV1Api.return_value = MagicMock()
            client = KubernetesClient(settings)
            cfg.load_kube_config.assert_called_once_with(config_file="/fake/.kube/config")

    def test_init_falls_back_to_incluster(self):
        s = Settings(groq_api_key="t", aws_access_key_id="A",
                     aws_secret_access_key="s", github_token="g", kubeconfig_path="")
        with patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.k8s_config") as cfg, \
             patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.k8s_client") as sdk:
            sdk.AppsV1Api.return_value = MagicMock()
            sdk.CoreV1Api.return_value = MagicMock()
            sdk.NetworkingV1Api.return_value = MagicMock()
            client = KubernetesClient(s)
            cfg.load_incluster_config.assert_called_once()

    def test_init_falls_back_to_default_kubeconfig_on_incluster_failure(self):
        s = Settings(groq_api_key="t", aws_access_key_id="A",
                     aws_secret_access_key="s", github_token="g", kubeconfig_path="")
        with patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.k8s_config") as cfg, \
             patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.k8s_client") as sdk:
            cfg.ConfigException = Exception
            cfg.load_incluster_config.side_effect = Exception("not in cluster")
            sdk.AppsV1Api.return_value = MagicMock()
            sdk.CoreV1Api.return_value = MagicMock()
            sdk.NetworkingV1Api.return_value = MagicMock()
            client = KubernetesClient(s)
            cfg.load_kube_config.assert_called_once_with()

    def test_init_sets_default_namespace(self, settings):
        with patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.k8s_config"), \
             patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.k8s_client") as sdk:
            sdk.AppsV1Api.return_value = MagicMock()
            sdk.CoreV1Api.return_value = MagicMock()
            sdk.NetworkingV1Api.return_value = MagicMock()
            client = KubernetesClient(settings)
            assert client.default_namespace == "test-ns"


# ---------------------------------------------------------------------------
# _require_client guard
# ---------------------------------------------------------------------------

class TestRequireClient:
    def test_raises_when_client_not_initialised(self, settings):
        client = KubernetesClient.__new__(KubernetesClient)
        client.settings = settings
        client.default_namespace = "default"
        client._apps_v1 = None
        client._core_v1 = None
        client._networking_v1 = None
        with pytest.raises(DeploymentError, match="not initialised"):
            client.deploy_to_kubernetes("ns", {})


# ---------------------------------------------------------------------------
# deploy_to_kubernetes
# ---------------------------------------------------------------------------

class TestDeployToKubernetes:
    def test_creates_deployment_on_first_call(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.create_namespaced_deployment.return_value = MagicMock()
        dep = _make_deployment()
        mock_apps_v1.read_namespaced_deployment.return_value = dep

        manifest = {"metadata": {"name": "app"}, "spec": {"replicas": 2}}
        with patch.object(k8s_client_with_mocks, "_wait_for_rollout", return_value=True):
            result = k8s_client_with_mocks.deploy_to_kubernetes("ns", manifest)
        assert result is True

    def test_patches_existing_deployment(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.create_namespaced_deployment.side_effect = _api_exc(409, "Conflict")

        manifest = {"metadata": {"name": "app"}, "spec": {"replicas": 2}}
        with patch.object(k8s_client_with_mocks, "_wait_for_rollout", return_value=True):
            result = k8s_client_with_mocks.deploy_to_kubernetes("ns", manifest)
        mock_apps_v1.patch_namespaced_deployment.assert_called_once()
        assert result is True

    def test_raises_on_rollout_timeout(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.create_namespaced_deployment.return_value = MagicMock()
        manifest = {"metadata": {"name": "app"}, "spec": {"replicas": 2}}
        with patch.object(k8s_client_with_mocks, "_wait_for_rollout", return_value=False):
            with pytest.raises(DeploymentError, match="timed out"):
                k8s_client_with_mocks.deploy_to_kubernetes("ns", manifest)

    def test_raises_on_api_exception(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.create_namespaced_deployment.side_effect = _api_exc(500, "Internal Server Error")
        manifest = {"metadata": {"name": "app"}, "spec": {}}
        with pytest.raises(DeploymentError, match="Kubernetes API error"):
            k8s_client_with_mocks.deploy_to_kubernetes("ns", manifest)

    def test_raises_on_unexpected_exception(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.create_namespaced_deployment.side_effect = RuntimeError("boom")
        manifest = {"metadata": {"name": "app"}, "spec": {}}
        with pytest.raises(DeploymentError, match="Unexpected error"):
            k8s_client_with_mocks.deploy_to_kubernetes("ns", manifest)


# ---------------------------------------------------------------------------
# get_kubernetes_status
# ---------------------------------------------------------------------------

class TestGetKubernetesStatus:
    def test_returns_status_dict(self, k8s_client_with_mocks, mock_apps_v1):
        dep = _make_deployment(name="myapp", ready=3, desired=3, available=3)
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        status = k8s_client_with_mocks.get_kubernetes_status("ns", "myapp")
        assert status["name"] == "myapp"
        assert status["ready_replicas"] == 3
        assert status["desired_replicas"] == 3
        assert status["available"] is True

    def test_not_fully_ready(self, k8s_client_with_mocks, mock_apps_v1):
        dep = _make_deployment(ready=1, desired=3, available=1)
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        status = k8s_client_with_mocks.get_kubernetes_status("ns", "app")
        assert status["available"] is False
        assert status["ready_replicas"] == 1

    def test_raises_on_404(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.read_namespaced_deployment.side_effect = _api_exc(404, "Not Found")
        with pytest.raises(DeploymentError, match="not found"):
            k8s_client_with_mocks.get_kubernetes_status("ns", "missing-app")

    def test_raises_on_other_api_error(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.read_namespaced_deployment.side_effect = _api_exc(403, "Forbidden")
        with pytest.raises(DeploymentError, match="Kubernetes API error"):
            k8s_client_with_mocks.get_kubernetes_status("ns", "app")

    def test_parses_conditions(self, k8s_client_with_mocks, mock_apps_v1):
        dep = _make_deployment()
        cond = MagicMock()
        cond.type = "Available"
        cond.status = "True"
        cond.reason = "MinimumReplicasAvailable"
        cond.message = "Deployment has minimum availability."
        dep.status.conditions = [cond]
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        status = k8s_client_with_mocks.get_kubernetes_status("ns", "app")
        assert status["conditions"][0]["type"] == "Available"


# ---------------------------------------------------------------------------
# rollback_kubernetes
# ---------------------------------------------------------------------------

class TestRollbackKubernetes:
    def test_rollback_patches_deployment(self, k8s_client_with_mocks, mock_apps_v1):
        dep = _make_deployment()
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        with patch.object(k8s_client_with_mocks, "_wait_for_rollout", return_value=True):
            result = k8s_client_with_mocks.rollback_kubernetes("ns", "app")
        mock_apps_v1.patch_namespaced_deployment.assert_called_once()
        assert result is True

    def test_rollback_returns_false_on_timeout(self, k8s_client_with_mocks, mock_apps_v1):
        dep = _make_deployment()
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        with patch.object(k8s_client_with_mocks, "_wait_for_rollout", return_value=False):
            result = k8s_client_with_mocks.rollback_kubernetes("ns", "app")
        assert result is False

    def test_rollback_raises_on_api_error(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.read_namespaced_deployment.side_effect = _api_exc(500, "Server Error")
        with pytest.raises(DeploymentError, match="rollback"):
            k8s_client_with_mocks.rollback_kubernetes("ns", "app")

    def test_rollback_targets_previous_revision(self, k8s_client_with_mocks, mock_apps_v1):
        dep = _make_deployment()
        dep.metadata.annotations = {"deployment.kubernetes.io/revision": "5"}
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        with patch.object(k8s_client_with_mocks, "_wait_for_rollout", return_value=True):
            k8s_client_with_mocks.rollback_kubernetes("ns", "app")
        call_kwargs = mock_apps_v1.patch_namespaced_deployment.call_args
        body = call_kwargs[1]["body"] if call_kwargs[1] else call_kwargs[0][2]
        annotation = body["spec"]["template"]["metadata"]["annotations"]
        assert annotation["deploymind.io/rollback-revision"] == "4"

    def test_rollback_does_not_go_below_revision_1(self, k8s_client_with_mocks, mock_apps_v1):
        dep = _make_deployment()
        dep.metadata.annotations = {"deployment.kubernetes.io/revision": "1"}
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        with patch.object(k8s_client_with_mocks, "_wait_for_rollout", return_value=True):
            k8s_client_with_mocks.rollback_kubernetes("ns", "app")
        call_kwargs = mock_apps_v1.patch_namespaced_deployment.call_args
        body = call_kwargs[1]["body"] if call_kwargs[1] else call_kwargs[0][2]
        annotation = body["spec"]["template"]["metadata"]["annotations"]
        assert annotation["deploymind.io/rollback-revision"] == "1"


# ---------------------------------------------------------------------------
# create_namespace
# ---------------------------------------------------------------------------

class TestCreateNamespace:
    def test_creates_new_namespace(self, k8s_client_with_mocks, mock_core_v1):
        mock_core_v1.create_namespace.return_value = MagicMock()
        result = k8s_client_with_mocks.create_namespace("my-ns")
        assert result is True
        mock_core_v1.create_namespace.assert_called_once()

    def test_returns_true_if_already_exists(self, k8s_client_with_mocks, mock_core_v1):
        mock_core_v1.create_namespace.side_effect = _api_exc(409, "Conflict")
        result = k8s_client_with_mocks.create_namespace("existing-ns")
        assert result is True

    def test_raises_on_unexpected_error(self, k8s_client_with_mocks, mock_core_v1):
        mock_core_v1.create_namespace.side_effect = _api_exc(403, "Forbidden")
        with pytest.raises(DeploymentError, match="Failed to create namespace"):
            k8s_client_with_mocks.create_namespace("ns")


# ---------------------------------------------------------------------------
# apply_service
# ---------------------------------------------------------------------------

class TestApplyService:
    def test_creates_new_service(self, k8s_client_with_mocks, mock_core_v1):
        mock_core_v1.create_namespaced_service.return_value = MagicMock()
        result = k8s_client_with_mocks.apply_service("ns", {"metadata": {"name": "svc"}})
        assert result is True

    def test_patches_existing_service(self, k8s_client_with_mocks, mock_core_v1):
        mock_core_v1.create_namespaced_service.side_effect = _api_exc(409, "Conflict")
        result = k8s_client_with_mocks.apply_service("ns", {"metadata": {"name": "svc"}})
        mock_core_v1.patch_namespaced_service.assert_called_once()
        assert result is True

    def test_raises_on_api_error(self, k8s_client_with_mocks, mock_core_v1):
        mock_core_v1.create_namespaced_service.side_effect = _api_exc(500, "Error")
        with pytest.raises(DeploymentError, match="Failed to apply service"):
            k8s_client_with_mocks.apply_service("ns", {"metadata": {"name": "svc"}})


# ---------------------------------------------------------------------------
# scale_deployment
# ---------------------------------------------------------------------------

class TestScaleDeployment:
    def test_scales_to_desired_replicas(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.patch_namespaced_deployment_scale.return_value = MagicMock()
        result = k8s_client_with_mocks.scale_deployment("ns", "app", replicas=5)
        assert result is True
        call_args = mock_apps_v1.patch_namespaced_deployment_scale.call_args
        assert call_args[1]["body"]["spec"]["replicas"] == 5

    def test_scales_to_zero(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.patch_namespaced_deployment_scale.return_value = MagicMock()
        result = k8s_client_with_mocks.scale_deployment("ns", "app", replicas=0)
        assert result is True

    def test_raises_on_negative_replicas(self, k8s_client_with_mocks):
        with pytest.raises(ValueError, match="replicas must be >= 0"):
            k8s_client_with_mocks.scale_deployment("ns", "app", replicas=-1)

    def test_raises_on_api_error(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.patch_namespaced_deployment_scale.side_effect = _api_exc(404, "Not Found")
        with pytest.raises(DeploymentError, match="Failed to scale"):
            k8s_client_with_mocks.scale_deployment("ns", "app", replicas=3)


# ---------------------------------------------------------------------------
# delete_deployment
# ---------------------------------------------------------------------------

class TestDeleteDeployment:
    def test_deletes_deployment(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.delete_namespaced_deployment.return_value = MagicMock()
        result = k8s_client_with_mocks.delete_deployment("ns", "app")
        assert result is True

    def test_returns_true_when_already_deleted(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.delete_namespaced_deployment.side_effect = _api_exc(404, "Not Found")
        result = k8s_client_with_mocks.delete_deployment("ns", "app")
        assert result is True

    def test_raises_on_other_error(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.delete_namespaced_deployment.side_effect = _api_exc(403, "Forbidden")
        with pytest.raises(DeploymentError, match="Failed to delete"):
            k8s_client_with_mocks.delete_deployment("ns", "app")


# ---------------------------------------------------------------------------
# list_deployments
# ---------------------------------------------------------------------------

class TestListDeployments:
    def test_returns_deployment_list(self, k8s_client_with_mocks, mock_apps_v1):
        d1 = _make_deployment("app1", ready=2, desired=2, available=2)
        d2 = _make_deployment("app2", ready=0, desired=3, available=0)
        mock_apps_v1.list_namespaced_deployment.return_value.items = [d1, d2]
        result = k8s_client_with_mocks.list_deployments("ns")
        assert len(result) == 2
        assert result[0]["name"] == "app1"
        assert result[0]["available"] is True
        assert result[1]["name"] == "app2"
        assert result[1]["available"] is False

    def test_returns_empty_list(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.list_namespaced_deployment.return_value.items = []
        result = k8s_client_with_mocks.list_deployments("ns")
        assert result == []

    def test_raises_on_api_error(self, k8s_client_with_mocks, mock_apps_v1):
        mock_apps_v1.list_namespaced_deployment.side_effect = _api_exc(403, "Forbidden")
        with pytest.raises(DeploymentError, match="Failed to list deployments"):
            k8s_client_with_mocks.list_deployments("ns")


# ---------------------------------------------------------------------------
# EC2 stub methods
# ---------------------------------------------------------------------------

class TestEC2Stubs:
    def test_deploy_container_raises_not_implemented(self, k8s_client_with_mocks):
        with pytest.raises(NotImplementedError):
            k8s_client_with_mocks.deploy_container("i-123", "myapp:latest")

    def test_check_instance_status_raises_not_implemented(self, k8s_client_with_mocks):
        with pytest.raises(NotImplementedError):
            k8s_client_with_mocks.check_instance_status("i-123")


# ---------------------------------------------------------------------------
# _wait_for_rollout
# ---------------------------------------------------------------------------

class TestWaitForRollout:
    def test_returns_true_when_ready(self, k8s_client_with_mocks, mock_apps_v1):
        dep = _make_deployment(ready=3, desired=3, updated=3, available=3, gen=2, meta_gen=2)
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        result = k8s_client_with_mocks._wait_for_rollout("ns", "app", timeout=1)
        assert result is True

    def test_returns_false_on_timeout(self, k8s_client_with_mocks, mock_apps_v1):
        dep = _make_deployment(ready=0, desired=3, updated=0, available=0)
        mock_apps_v1.read_namespaced_deployment.return_value = dep
        with patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.time.sleep"):
            result = k8s_client_with_mocks._wait_for_rollout("ns", "app", timeout=1)
        assert result is False

    def test_handles_api_exception_during_poll(self, k8s_client_with_mocks, mock_apps_v1):
        # First two calls raise transient ApiException, third returns ready deployment
        exc = _api_exc(503, "Service Unavailable")
        dep = _make_deployment(ready=2, desired=2, updated=2, available=2, gen=1, meta_gen=1)
        mock_apps_v1.read_namespaced_deployment.side_effect = [exc, exc, dep]
        with patch("deploymind.infrastructure.cloud.kubernetes.k8s_client.time.sleep"):
            result = k8s_client_with_mocks._wait_for_rollout("ns", "app", timeout=60)
        assert result is True
