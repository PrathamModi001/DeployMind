"""Cloud service interface.

Defines the abstract contract for cloud operations used by the Application
layer.  Infrastructure implementations (EC2Client, KubernetesClient) fulfil
this contract — the Application layer never imports them directly.
"""

from abc import ABC, abstractmethod
from typing import Optional


class CloudService(ABC):
    """Interface for cloud operations (EC2 and Kubernetes)."""

    # ------------------------------------------------------------------
    # EC2 / container operations
    # ------------------------------------------------------------------

    @abstractmethod
    def deploy_container(self, instance_id: str, image: str) -> bool:
        """Deploy container to EC2 instance."""

    @abstractmethod
    def check_instance_status(self, instance_id: str) -> dict:
        """Check instance health status."""

    # ------------------------------------------------------------------
    # Kubernetes operations
    # ------------------------------------------------------------------

    @abstractmethod
    def deploy_to_kubernetes(
        self,
        namespace: str,
        manifest: dict,
        strategy: str = "rolling",
    ) -> bool:
        """Apply a Deployment manifest to a Kubernetes cluster.

        Args:
            namespace: Target Kubernetes namespace.
            manifest: Kubernetes Deployment manifest dict.
            strategy: ``"rolling"`` or ``"canary"`` or ``"blue_green"``.

        Returns:
            True if the rollout completed successfully.
        """

    @abstractmethod
    def get_kubernetes_status(self, namespace: str, name: str) -> dict:
        """Return the current status of a Kubernetes Deployment.

        Returns a dict with at least::

            {
                "ready_replicas": int,
                "desired_replicas": int,
                "available": bool,
                "conditions": list[dict],
            }
        """

    @abstractmethod
    def rollback_kubernetes(self, namespace: str, name: str) -> bool:
        """Roll back a Kubernetes Deployment to its previous revision.

        Equivalent to ``kubectl rollout undo deployment/{name}``.

        Returns:
            True if rollback was initiated successfully.
        """
