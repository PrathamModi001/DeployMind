"""Deploy-to-Kubernetes use case.

Orchestrates deploying a Docker image to a Kubernetes cluster, supporting
rolling, canary, and blue-green strategies.

Pipeline:
1. Validate inputs
2. Ensure target namespace exists
3. Generate resource manifests via ManifestGenerator
4. Apply resources via KubernetesClient
5. Optionally apply a Service and Ingress
6. Wait for rollout (handled inside KubernetesClient)
7. Return structured response
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from deploymind.config.settings import Settings
from deploymind.infrastructure.cloud.kubernetes.k8s_client import KubernetesClient
from deploymind.infrastructure.cloud.kubernetes.manifest_generator import ManifestGenerator
from deploymind.shared.validators import SecurityValidator
from deploymind.shared.secure_logging import get_logger
from deploymind.shared.exceptions import ValidationError, DeploymentError

logger = get_logger(__name__)

# Valid strategies understood by this use case
_VALID_STRATEGIES = {"rolling", "canary", "blue-green", "blue_green"}


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------


@dataclass
class K8sDeployRequest:
    """Input for a Kubernetes deployment."""

    deployment_id: str
    name: str                          # Kubernetes Deployment / app name
    image: str                         # Full image:tag reference
    namespace: str = "default"
    replicas: int = 2
    port: int = 8080
    strategy: str = "rolling"
    health_check_path: str = "/health"
    env_vars: Optional[dict[str, str]] = None

    # Canary specific
    stable_image: Optional[str] = None    # Required when strategy=="canary"
    stable_replicas: int = 9
    canary_replicas: int = 1

    # Blue-Green specific
    active_color: str = "blue"            # Which color is currently live

    # Optional extras
    create_service: bool = True
    service_type: str = "ClusterIP"
    create_ingress: bool = False
    ingress_host: Optional[str] = None
    ingress_tls_secret: Optional[str] = None

    # Resource limits (forwarded to ManifestGenerator)
    cpu_request: str = "100m"
    cpu_limit: str = "500m"
    memory_request: str = "128Mi"
    memory_limit: str = "512Mi"


@dataclass
class K8sDeployResponse:
    """Result of a Kubernetes deployment."""

    success: bool
    deployment_id: str
    name: str
    namespace: str
    strategy: str
    image: str

    # Replica counts from the cluster after deployment
    ready_replicas: int = 0
    desired_replicas: int = 0

    # URLs / routing info
    service_created: bool = False
    ingress_created: bool = False
    ingress_host: Optional[str] = None

    # Error info
    error_message: Optional[str] = None
    error_phase: Optional[str] = None  # "validation" | "namespace" | "deploy" | "service"

    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None

    # Applied manifests (useful for auditing / debugging)
    applied_manifests: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------


class DeployToKubernetesUseCase:
    """Orchestrates Kubernetes deployments.

    Supports three strategies:
    - ``rolling``    — standard Kubernetes RollingUpdate (default)
    - ``canary``     — two Deployments (stable + canary) with weighted replicas
    - ``blue-green`` — two Deployments (blue + green) with Service selector switch

    Example::

        use_case = DeployToKubernetesUseCase(settings)
        response = use_case.execute(K8sDeployRequest(
            deployment_id="deploy-abc123",
            name="myapp",
            image="myrepo/myapp:abc1234",
            namespace="production",
            replicas=3,
            strategy="rolling",
        ))
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.validator = SecurityValidator()
        self.k8s_client = KubernetesClient(settings)
        self.manifest_gen = ManifestGenerator()
        logger.info("DeployToKubernetesUseCase initialised")

    def execute(self, request: K8sDeployRequest) -> K8sDeployResponse:
        """Execute the Kubernetes deployment workflow.

        Args:
            request: K8sDeployRequest with all deployment parameters.

        Returns:
            K8sDeployResponse describing the outcome.
        """
        started_at = datetime.utcnow()

        response = K8sDeployResponse(
            success=False,
            deployment_id=request.deployment_id,
            name=request.name,
            namespace=request.namespace,
            strategy=request.strategy,
            image=request.image,
            started_at=started_at,
        )

        logger.info(
            "Starting Kubernetes deployment",
            extra={
                "deployment_id": request.deployment_id,
                "name": request.name,
                "strategy": request.strategy,
                "namespace": request.namespace,
            },
        )

        try:
            # Phase 1 — Validate
            self._validate(request)

            # Phase 2 — Ensure namespace exists
            try:
                self.k8s_client.create_namespace(request.namespace)
            except Exception as exc:
                logger.warning("Namespace creation skipped", extra={"error": str(exc)})

            # Phase 3 — Deploy according to strategy
            strategy_norm = request.strategy.lower().replace("-", "_")

            if strategy_norm == "rolling":
                manifests = self._rolling_deploy(request, response)
            elif strategy_norm == "canary":
                manifests = self._canary_deploy(request, response)
            elif strategy_norm in ("blue_green",):
                manifests = self._blue_green_deploy(request, response)
            else:  # pragma: no cover  (already validated above)
                raise ValidationError(f"Unknown strategy: {request.strategy}")

            response.applied_manifests = manifests

            # Phase 4 — Optional Service
            if request.create_service:
                svc_manifest = self.manifest_gen.generate_service(
                    name=request.name,
                    port=request.port,
                    namespace=request.namespace,
                    service_type=request.service_type,
                )
                self.k8s_client.apply_service(request.namespace, svc_manifest)
                response.service_created = True

            # Phase 5 — Optional Ingress
            if request.create_ingress and request.ingress_host:
                ingress_manifest = self.manifest_gen.generate_ingress(
                    name=request.name,
                    host=request.ingress_host,
                    service_name=request.name,
                    port=request.port,
                    namespace=request.namespace,
                    tls_secret=request.ingress_tls_secret,
                )
                self.k8s_client.apply_ingress(request.namespace, ingress_manifest)
                response.ingress_created = True
                response.ingress_host = request.ingress_host

            # Phase 6 — Read back status
            try:
                status = self.k8s_client.get_kubernetes_status(request.namespace, request.name)
                response.ready_replicas = status.get("ready_replicas", 0)
                response.desired_replicas = status.get("desired_replicas", request.replicas)
            except Exception:
                response.desired_replicas = request.replicas

            response.success = True

        except (ValidationError, DeploymentError) as exc:
            phase = "validation" if isinstance(exc, ValidationError) else "deploy"
            response.error_phase = phase
            response.error_message = str(exc)
            logger.error(f"Deployment failed [{phase}]", extra={"error": str(exc)})

        except Exception as exc:
            response.error_phase = "unknown"
            response.error_message = f"Unexpected error: {exc}"
            logger.error("Unexpected deployment error", exc_info=True)

        finally:
            response.completed_at = datetime.utcnow()
            if response.started_at:
                response.duration_seconds = (
                    response.completed_at - response.started_at
                ).total_seconds()

        return response

    # ------------------------------------------------------------------
    # Strategy implementations
    # ------------------------------------------------------------------

    def _rolling_deploy(
        self, request: K8sDeployRequest, response: K8sDeployResponse
    ) -> list[dict]:
        """Standard rolling update — single Deployment object."""
        manifest = self.manifest_gen.generate_deployment(
            name=request.name,
            image=request.image,
            replicas=request.replicas,
            port=request.port,
            namespace=request.namespace,
            env_vars=request.env_vars,
            health_check_path=request.health_check_path,
            cpu_request=request.cpu_request,
            cpu_limit=request.cpu_limit,
            memory_request=request.memory_request,
            memory_limit=request.memory_limit,
        )
        self.k8s_client.deploy_to_kubernetes(request.namespace, manifest, strategy="rolling")
        return [manifest]

    def _canary_deploy(
        self, request: K8sDeployRequest, response: K8sDeployResponse
    ) -> list[dict]:
        """Canary: stable Deployment + canary Deployment, shared Service."""
        stable_image = request.stable_image
        if not stable_image:
            raise ValidationError(
                "stable_image is required for canary strategy. "
                "Pass the currently running image tag."
            )

        manifests = self.manifest_gen.generate_canary_manifests(
            name=request.name,
            stable_image=stable_image,
            canary_image=request.image,
            stable_replicas=request.stable_replicas,
            canary_replicas=request.canary_replicas,
            port=request.port,
            namespace=request.namespace,
            health_check_path=request.health_check_path,
        )

        all_applied: list[dict] = []
        for m in manifests["stable"]:
            self.k8s_client.deploy_to_kubernetes(request.namespace, m, strategy="canary")
            all_applied.append(m)
        for m in manifests["canary"]:
            self.k8s_client.deploy_to_kubernetes(request.namespace, m, strategy="canary")
            all_applied.append(m)
        # The service is applied separately (create_service path) but we
        # include it in applied_manifests for auditing
        all_applied.extend(manifests["service"])
        return all_applied

    def _blue_green_deploy(
        self, request: K8sDeployRequest, response: K8sDeployResponse
    ) -> list[dict]:
        """Blue-Green: two Deployments, Service switches to inactive color."""
        # Determine colors: request.image goes to the *inactive* color slot
        active = request.active_color
        inactive = "green" if active == "blue" else "blue"

        # We don't know the active image; generate both with request.image for
        # the new slot and a placeholder for the existing slot.
        # In production the caller should provide stable_image for the active side.
        blue_image = request.image if active == "green" else (request.stable_image or request.image)
        green_image = request.image if active == "blue" else (request.stable_image or request.image)

        manifests = self.manifest_gen.generate_blue_green_manifests(
            name=request.name,
            blue_image=blue_image,
            green_image=green_image,
            active_color=inactive,   # Promote the inactive side
            replicas=request.replicas,
            port=request.port,
            namespace=request.namespace,
            health_check_path=request.health_check_path,
        )

        # Deploy both sides
        for m in (manifests["blue"], manifests["green"]):
            self.k8s_client.deploy_to_kubernetes(request.namespace, m, strategy="blue-green")

        # Apply updated Service pointing to the new (inactive→active) color
        self.k8s_client.apply_service(request.namespace, manifests["service"])

        return [manifests["blue"], manifests["green"], manifests["service"]]

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self, request: K8sDeployRequest) -> None:
        """Validate request fields.

        Raises:
            ValidationError: On any invalid value.
        """
        if not request.deployment_id:
            raise ValidationError("deployment_id must not be empty")
        if not request.name:
            raise ValidationError("name must not be empty")
        if not request.image:
            raise ValidationError("image must not be empty")
        if not request.namespace:
            raise ValidationError("namespace must not be empty")
        if request.replicas < 1:
            raise ValidationError(f"replicas must be >= 1, got {request.replicas}")
        if not (1 <= request.port <= 65535):
            raise ValidationError(f"port must be 1-65535, got {request.port}")
        if not request.health_check_path.startswith("/"):
            raise ValidationError(
                f"health_check_path must start with '/', got {request.health_check_path!r}"
            )

        strategy_norm = request.strategy.lower().replace("-", "_")
        valid = {"rolling", "canary", "blue_green"}
        if strategy_norm not in valid:
            raise ValidationError(
                f"Unknown strategy {request.strategy!r}. Valid: {sorted(valid)}"
            )

        if strategy_norm == "canary" and not request.stable_image:
            raise ValidationError(
                "stable_image is required when strategy='canary'"
            )

        if strategy_norm == "blue_green" and request.active_color not in ("blue", "green"):
            raise ValidationError(
                f"active_color must be 'blue' or 'green', got {request.active_color!r}"
            )

        if request.create_ingress and not request.ingress_host:
            raise ValidationError("ingress_host is required when create_ingress=True")

        logger.info("K8s request validation passed")
