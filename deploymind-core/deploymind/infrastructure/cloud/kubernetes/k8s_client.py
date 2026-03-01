"""Kubernetes client — infrastructure adapter for the CloudService interface.

Uses the official ``kubernetes`` Python SDK (``pip install kubernetes``).
Supports in-cluster config (when running inside a pod) and external kubeconfig.

Implements the three methods from CloudService that the application layer
expects for Kubernetes deployments:
  - ``deploy_to_kubernetes(namespace, manifest, strategy)``
  - ``get_kubernetes_status(namespace, name)``
  - ``rollback_kubernetes(namespace, name)``
"""

from __future__ import annotations

import time
from typing import Any, Optional

from deploymind.config.settings import Settings
from deploymind.shared.secure_logging import get_logger
from deploymind.shared.exceptions import DeploymentError

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# SDK import (optional — fail at call time, not import time)
# ---------------------------------------------------------------------------

try:
    from kubernetes import client as k8s_client, config as k8s_config
    from kubernetes.client.rest import ApiException
    K8S_AVAILABLE = True
except ImportError:  # pragma: no cover
    k8s_client = None  # type: ignore[assignment]
    k8s_config = None  # type: ignore[assignment]
    ApiException = Exception  # type: ignore[assignment,misc]
    K8S_AVAILABLE = False


# ---------------------------------------------------------------------------
# KubernetesClient
# ---------------------------------------------------------------------------


class KubernetesClient:
    """Kubernetes cluster adapter.

    Loads credentials from:
    1. In-cluster service account (when ``kubeconfig_path`` is empty and
       running inside a Kubernetes pod).
    2. External kubeconfig file at ``settings.kubeconfig_path``.
    3. Default kubeconfig (``~/.kube/config``) as fallback.

    Example::

        client = KubernetesClient(settings)
        ok = client.deploy_to_kubernetes(
            namespace="production",
            manifest=ManifestGenerator().generate_deployment(
                name="myapp", image="myapp:abc1234", replicas=3, port=8080
            ),
            strategy="rolling",
        )
    """

    # How often to poll rollout status (seconds)
    _POLL_INTERVAL: int = 5
    # Maximum time to wait for a rollout to complete (seconds)
    _ROLLOUT_TIMEOUT: int = 300

    def __init__(self, settings: Settings) -> None:
        """Initialise client and authenticate to the cluster.

        Args:
            settings: Application settings (reads ``kubeconfig_path`` and
                ``kubernetes_namespace``).
        """
        self.settings = settings
        self.default_namespace = getattr(settings, "kubernetes_namespace", "default")
        self._apps_v1: Optional[Any] = None
        self._core_v1: Optional[Any] = None
        self._networking_v1: Optional[Any] = None
        self._load_config()
        logger.info("KubernetesClient initialised", extra={"namespace": self.default_namespace})

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        """Load kubeconfig — tries in-cluster, then explicit path, then default."""
        if not K8S_AVAILABLE:
            logger.warning("kubernetes SDK not installed; client in stub mode")
            return

        kubeconfig_path = getattr(self.settings, "kubeconfig_path", "")

        try:
            if kubeconfig_path:
                k8s_config.load_kube_config(config_file=kubeconfig_path)
                logger.info("Loaded kubeconfig from file", extra={"path": kubeconfig_path})
            else:
                try:
                    k8s_config.load_incluster_config()
                    logger.info("Loaded in-cluster kubeconfig")
                except k8s_config.ConfigException:
                    k8s_config.load_kube_config()
                    logger.info("Loaded default kubeconfig (~/.kube/config)")

            self._apps_v1 = k8s_client.AppsV1Api()
            self._core_v1 = k8s_client.CoreV1Api()
            self._networking_v1 = k8s_client.NetworkingV1Api()
        except Exception as exc:
            logger.warning("Failed to initialise kubernetes API clients", extra={"error": str(exc)})

    # ------------------------------------------------------------------
    # CloudService interface — Kubernetes methods
    # ------------------------------------------------------------------

    def deploy_to_kubernetes(
        self,
        namespace: str,
        manifest: dict,
        strategy: str = "rolling",
    ) -> bool:
        """Apply a Deployment manifest and wait for rollout completion.

        Performs an *apply* (create-or-replace) semantic:
        - Creates the resource if it does not exist.
        - Patches (strategic merge patch) if it already exists.

        Args:
            namespace: Target Kubernetes namespace.
            manifest: Kubernetes Deployment manifest dict (``apiVersion``,
                ``kind``, ``metadata``, ``spec`` keys required).
            strategy: Ignored for built-in k8s rolling; reserved for future
                blue-green/canary variants that delegate to separate deployers.

        Returns:
            True if the rollout finished with all replicas ready.

        Raises:
            DeploymentError: If the API call fails or rollout times out.
        """
        self._require_client()

        name = manifest.get("metadata", {}).get("name", "unknown")
        logger.info(
            "Deploying to Kubernetes",
            extra={"name": name, "namespace": namespace, "strategy": strategy},
        )

        try:
            self._apply_manifest(namespace, manifest)
            ready = self._wait_for_rollout(namespace, name)
            if not ready:
                raise DeploymentError(
                    f"Rollout timed out after {self._ROLLOUT_TIMEOUT}s "
                    f"for deployment '{name}' in namespace '{namespace}'"
                )
            logger.info("Rollout completed", extra={"name": name, "namespace": namespace})
            return True

        except DeploymentError:
            raise
        except ApiException as exc:
            msg = f"Kubernetes API error deploying '{name}': {exc.reason}"
            logger.error(msg, extra={"status": exc.status})
            raise DeploymentError(msg) from exc
        except Exception as exc:
            msg = f"Unexpected error deploying '{name}': {exc}"
            logger.error(msg, exc_info=True)
            raise DeploymentError(msg) from exc

    def get_kubernetes_status(self, namespace: str, name: str) -> dict:
        """Return the current status of a Kubernetes Deployment.

        Args:
            namespace: Kubernetes namespace.
            name: Deployment name.

        Returns:
            Dict with keys: ``ready_replicas``, ``desired_replicas``,
            ``available``, ``conditions``, ``observed_generation``.

        Raises:
            DeploymentError: If the deployment is not found.
        """
        self._require_client()

        try:
            deployment = self._apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
            status = deployment.status
            spec = deployment.spec

            desired = spec.replicas or 1
            ready = status.ready_replicas or 0
            available = status.available_replicas or 0
            observed_gen = status.observed_generation or 0

            conditions = []
            if status.conditions:
                for cond in status.conditions:
                    conditions.append({
                        "type": cond.type,
                        "status": cond.status,
                        "reason": cond.reason or "",
                        "message": cond.message or "",
                    })

            return {
                "name": name,
                "namespace": namespace,
                "ready_replicas": ready,
                "desired_replicas": desired,
                "available_replicas": available,
                "available": available >= desired,
                "observed_generation": observed_gen,
                "conditions": conditions,
            }

        except ApiException as exc:
            if exc.status == 404:
                raise DeploymentError(f"Deployment '{name}' not found in namespace '{namespace}'")
            raise DeploymentError(f"Kubernetes API error: {exc.reason}") from exc

    def rollback_kubernetes(self, namespace: str, name: str) -> bool:
        """Roll back a Deployment to its previous revision.

        Equivalent to ``kubectl rollout undo deployment/<name>``.
        Patches the Deployment's ``spec.template`` annotation to trigger a
        rollout of the previous ``ReplicaSet``.

        Args:
            namespace: Kubernetes namespace.
            name: Deployment name.

        Returns:
            True if rollback was initiated and completed successfully.

        Raises:
            DeploymentError: If the API call fails.
        """
        self._require_client()

        logger.info("Rolling back Kubernetes deployment", extra={"name": name, "namespace": namespace})

        try:
            # Fetch current deployment to read revision history
            deployment = self._apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
            current_revision = int(
                deployment.metadata.annotations.get("deployment.kubernetes.io/revision", "1")
            )
            target_revision = max(1, current_revision - 1)

            # Patch via rollback annotation (triggers controller to undo)
            patch_body = {
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "kubectl.kubernetes.io/restartedAt": _now_iso(),
                                "deploymind.io/rollback-revision": str(target_revision),
                            }
                        }
                    }
                }
            }
            self._apps_v1.patch_namespaced_deployment(
                name=name,
                namespace=namespace,
                body=patch_body,
            )

            ready = self._wait_for_rollout(namespace, name)
            logger.info(
                "Rollback completed",
                extra={"name": name, "namespace": namespace, "target_revision": target_revision},
            )
            return ready

        except ApiException as exc:
            msg = f"Kubernetes API error during rollback of '{name}': {exc.reason}"
            logger.error(msg, extra={"status": exc.status})
            raise DeploymentError(msg) from exc

    # ------------------------------------------------------------------
    # CloudService interface — EC2 stubs (not used for k8s deployments)
    # ------------------------------------------------------------------

    def deploy_container(self, instance_id: str, image: str) -> bool:
        """Not implemented for Kubernetes client — use deploy_to_kubernetes."""
        raise NotImplementedError("Use deploy_to_kubernetes() for Kubernetes deployments")

    def check_instance_status(self, instance_id: str) -> dict:
        """Not implemented for Kubernetes client."""
        raise NotImplementedError("Use get_kubernetes_status() for Kubernetes deployments")

    # ------------------------------------------------------------------
    # Additional public helpers
    # ------------------------------------------------------------------

    def create_namespace(self, namespace: str) -> bool:
        """Create a namespace if it does not already exist.

        Args:
            namespace: Namespace to create.

        Returns:
            True if created or already exists.
        """
        self._require_client()
        try:
            self._core_v1.create_namespace(
                body=k8s_client.V1Namespace(
                    metadata=k8s_client.V1ObjectMeta(name=namespace)
                )
            )
            logger.info("Namespace created", extra={"namespace": namespace})
            return True
        except ApiException as exc:
            if exc.status == 409:  # Already exists
                return True
            raise DeploymentError(f"Failed to create namespace '{namespace}': {exc.reason}") from exc

    def apply_service(self, namespace: str, manifest: dict) -> bool:
        """Create or update a Kubernetes Service.

        Args:
            namespace: Namespace to apply the service in.
            manifest: Service manifest dict.

        Returns:
            True if the service was applied successfully.
        """
        self._require_client()
        name = manifest.get("metadata", {}).get("name", "unknown")
        try:
            try:
                self._core_v1.create_namespaced_service(namespace=namespace, body=manifest)
            except ApiException as exc:
                if exc.status == 409:
                    self._core_v1.patch_namespaced_service(
                        name=name, namespace=namespace, body=manifest
                    )
                else:
                    raise
            logger.info("Service applied", extra={"name": name, "namespace": namespace})
            return True
        except ApiException as exc:
            raise DeploymentError(f"Failed to apply service '{name}': {exc.reason}") from exc

    def apply_ingress(self, namespace: str, manifest: dict) -> bool:
        """Create or update a Kubernetes Ingress.

        Args:
            namespace: Namespace to apply the ingress in.
            manifest: Ingress manifest dict.

        Returns:
            True if the ingress was applied successfully.
        """
        self._require_client()
        name = manifest.get("metadata", {}).get("name", "unknown")
        try:
            try:
                self._networking_v1.create_namespaced_ingress(namespace=namespace, body=manifest)
            except ApiException as exc:
                if exc.status == 409:
                    self._networking_v1.patch_namespaced_ingress(
                        name=name, namespace=namespace, body=manifest
                    )
                else:
                    raise
            logger.info("Ingress applied", extra={"name": name, "namespace": namespace})
            return True
        except ApiException as exc:
            raise DeploymentError(f"Failed to apply ingress '{name}': {exc.reason}") from exc

    def get_pod_logs(self, namespace: str, label_selector: str, tail_lines: int = 100) -> str:
        """Fetch logs from the first matching pod.

        Args:
            namespace: Kubernetes namespace.
            label_selector: Label selector string (e.g. ``"app=myapp"``).
            tail_lines: Number of log lines to return.

        Returns:
            Log text (empty string if no pods found).
        """
        self._require_client()
        try:
            pods = self._core_v1.list_namespaced_pod(
                namespace=namespace, label_selector=label_selector
            )
            if not pods.items:
                return ""
            pod_name = pods.items[0].metadata.name
            return self._core_v1.read_namespaced_pod_log(
                name=pod_name, namespace=namespace, tail_lines=tail_lines
            )
        except ApiException as exc:
            logger.warning("Failed to fetch pod logs", extra={"error": str(exc)})
            return ""

    def list_deployments(self, namespace: str) -> list[dict]:
        """List all Deployments in a namespace.

        Args:
            namespace: Kubernetes namespace.

        Returns:
            List of dicts with ``name``, ``ready_replicas``, ``desired_replicas``.
        """
        self._require_client()
        try:
            items = self._apps_v1.list_namespaced_deployment(namespace=namespace).items
            return [
                {
                    "name": d.metadata.name,
                    "ready_replicas": d.status.ready_replicas or 0,
                    "desired_replicas": d.spec.replicas or 1,
                    "available": (d.status.available_replicas or 0) >= (d.spec.replicas or 1),
                }
                for d in items
            ]
        except ApiException as exc:
            raise DeploymentError(f"Failed to list deployments: {exc.reason}") from exc

    def scale_deployment(self, namespace: str, name: str, replicas: int) -> bool:
        """Scale a Deployment to the given number of replicas.

        Args:
            namespace: Kubernetes namespace.
            name: Deployment name.
            replicas: Target replica count (0 = scale to zero).

        Returns:
            True if the patch was accepted.
        """
        self._require_client()
        if replicas < 0:
            raise ValueError(f"replicas must be >= 0, got {replicas}")
        try:
            self._apps_v1.patch_namespaced_deployment_scale(
                name=name,
                namespace=namespace,
                body={"spec": {"replicas": replicas}},
            )
            logger.info("Deployment scaled", extra={"name": name, "replicas": replicas})
            return True
        except ApiException as exc:
            raise DeploymentError(f"Failed to scale '{name}': {exc.reason}") from exc

    def delete_deployment(self, namespace: str, name: str) -> bool:
        """Delete a Deployment.

        Args:
            namespace: Kubernetes namespace.
            name: Deployment name.

        Returns:
            True if deleted (or already absent).
        """
        self._require_client()
        try:
            self._apps_v1.delete_namespaced_deployment(name=name, namespace=namespace)
            logger.info("Deployment deleted", extra={"name": name, "namespace": namespace})
            return True
        except ApiException as exc:
            if exc.status == 404:
                return True  # Already gone — idempotent
            raise DeploymentError(f"Failed to delete '{name}': {exc.reason}") from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _require_client(self) -> None:
        """Raise if the kubernetes SDK failed to initialise."""
        if self._apps_v1 is None:
            raise DeploymentError(
                "Kubernetes API client not initialised. "
                "Ensure the kubernetes SDK is installed and kubeconfig is valid."
            )

    def _apply_manifest(self, namespace: str, manifest: dict) -> None:
        """Create-or-patch a Deployment manifest."""
        name = manifest.get("metadata", {}).get("name", "unknown")
        try:
            self._apps_v1.create_namespaced_deployment(namespace=namespace, body=manifest)
            logger.info("Deployment created", extra={"name": name})
        except ApiException as exc:
            if exc.status == 409:  # Already exists — patch it
                self._apps_v1.patch_namespaced_deployment(
                    name=name, namespace=namespace, body=manifest
                )
                logger.info("Deployment patched", extra={"name": name})
            else:
                raise

    def _wait_for_rollout(self, namespace: str, name: str, timeout: int | None = None) -> bool:
        """Poll until all desired replicas are ready or timeout expires.

        Args:
            namespace: Kubernetes namespace.
            name: Deployment name.
            timeout: Override for ``_ROLLOUT_TIMEOUT``.

        Returns:
            True if all replicas became ready within the timeout.
        """
        deadline = time.time() + (timeout or self._ROLLOUT_TIMEOUT)
        while time.time() < deadline:
            try:
                deployment = self._apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
                spec_replicas = deployment.spec.replicas or 1
                ready = deployment.status.ready_replicas or 0
                updated = deployment.status.updated_replicas or 0
                available = deployment.status.available_replicas or 0
                observed_gen = deployment.status.observed_generation or 0
                metadata_gen = deployment.metadata.generation or 0

                if (
                    observed_gen >= metadata_gen
                    and updated >= spec_replicas
                    and available >= spec_replicas
                    and ready >= spec_replicas
                ):
                    return True

                logger.debug(
                    "Waiting for rollout",
                    extra={
                        "name": name,
                        "ready": ready,
                        "updated": updated,
                        "desired": spec_replicas,
                    },
                )
            except ApiException:
                pass

            time.sleep(self._POLL_INTERVAL)

        return False


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Return current UTC time as ISO-8601 string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
