"""Canary deployment strategy.

Traffic is split between the production container (stable) and the canary
container (new version) using nginx upstream weights controlled via AWS SSM.

Traffic shifting stages:
  Stage 1  — 10% canary, 90% production — observe for ``stage_duration_s``
  Stage 2  — 50% canary, 50% production — observe for ``stage_duration_s``
  Stage 3  — 100% canary (full rollout) — production container stopped

If the canary error rate exceeds ``error_rate_threshold`` at any stage,
the nginx config is reverted to 100% production and the canary container
is stopped (instant rollback, no downtime on production traffic).

Port conventions:
  Production container: port ``prod_port``   (default 8080)
  Canary container:     port ``canary_port`` (default 8081)
  Nginx listens on:     port 80 / 443
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client
from deploymind.infrastructure.monitoring.health_checker import HealthChecker, HealthCheckResult
from deploymind.shared.secure_logging import get_logger
from deploymind.shared.exceptions import DeploymentError

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CanaryStage:
    """Represents a single traffic-shifting stage."""

    canary_weight: int       # Canary share (0–100)
    prod_weight: int         # Production share (0–100)
    duration_seconds: int    # How long to observe this stage


@dataclass
class CanaryStageResult:
    """Outcome of a single canary stage."""

    stage_index: int          # 0-based
    canary_weight: int
    prod_weight: int
    duration_seconds: int
    completed: bool           # False means we bailed early
    error_rate: float = 0.0   # Observed error rate at end of stage
    health_checks_passed: int = 0
    health_checks_total: int = 0


@dataclass
class CanaryResult:
    """Overall result of the canary deployment."""

    success: bool
    deployment_id: str
    image_tag: str
    instance_id: str
    stages_completed: int = 0       # How many stages ran before success/failure
    final_percentage: int = 0       # 0, 10, 50, or 100
    error_rate_at_failure: Optional[float] = None
    rollback_performed: bool = False
    duration_seconds: int = 0
    stage_results: list[CanaryStageResult] = field(default_factory=list)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    def __post_init__(self):
        if self.started_at is None:
            self.started_at = datetime.utcnow()


# ---------------------------------------------------------------------------
# nginx config snippets sent via SSM
# ---------------------------------------------------------------------------

_NGINX_UPSTREAM_TEMPLATE = """\
upstream deploymind_backend {{
    server localhost:{prod_port} weight={prod_weight};
    server localhost:{canary_port} weight={canary_weight};
}}
"""

_NGINX_UPSTREAM_PRODUCTION_ONLY = """\
upstream deploymind_backend {{
    server localhost:{prod_port} weight=1;
}}
"""

_NGINX_RELOAD_CMD = "nginx -s reload"
_NGINX_CONF_PATH = "/etc/nginx/conf.d/deploymind_upstream.conf"


# ---------------------------------------------------------------------------
# Canary deployer
# ---------------------------------------------------------------------------


class CanaryDeployer:
    """Canary deployment strategy with automatic traffic shifting and rollback.

    Args:
        ec2_client: EC2Client for SSM commands and container operations.
        health_checker: HealthChecker for HTTP/TCP probes.
        stage_duration_seconds: Seconds to observe each traffic stage.
        health_check_interval_seconds: Seconds between HTTP probes.
        error_rate_threshold: Maximum allowed error rate before rollback (0.0–1.0).
        prod_port: Port of the production container.
        canary_port: Port of the canary container.
    """

    DEFAULT_STAGES = [
        CanaryStage(canary_weight=1,  prod_weight=9, duration_seconds=300),  # ~10%
        CanaryStage(canary_weight=1,  prod_weight=1, duration_seconds=300),  # ~50%
        CanaryStage(canary_weight=1,  prod_weight=0, duration_seconds=0),    # 100%
    ]

    def __init__(
        self,
        ec2_client: EC2Client,
        health_checker: HealthChecker,
        stage_duration_seconds: int = 300,
        health_check_interval_seconds: int = 30,
        error_rate_threshold: float = 0.05,
        prod_port: int = 8080,
        canary_port: int = 8081,
    ) -> None:
        self.ec2_client = ec2_client
        self.health_checker = health_checker
        self.stage_duration_seconds = stage_duration_seconds
        self.health_check_interval_seconds = health_check_interval_seconds
        self.error_rate_threshold = error_rate_threshold
        self.prod_port = prod_port
        self.canary_port = canary_port

        logger.info(
            "CanaryDeployer initialized",
            extra={
                "stage_duration_seconds": stage_duration_seconds,
                "error_rate_threshold": error_rate_threshold,
                "prod_port": prod_port,
                "canary_port": canary_port,
            },
        )

    def deploy(
        self,
        deployment_id: str,
        instance_id: str,
        image_tag: str,
        container_name: str = "app",
        health_check_path: str = "/health",
        env_vars: Optional[dict[str, str]] = None,
        previous_image_tag: Optional[str] = None,
    ) -> CanaryResult:
        """Execute a canary deployment.

        Args:
            deployment_id: Unique deployment identifier.
            instance_id: EC2 instance ID.
            image_tag: New Docker image tag to deploy as canary.
            container_name: Base container name; canary will be ``{name}-canary``.
            health_check_path: HTTP path for health probes.
            env_vars: Environment variables for the canary container.
            previous_image_tag: Previous stable image tag (used for records).

        Returns:
            CanaryResult with full outcome details.
        """
        start_time = datetime.utcnow()
        result = CanaryResult(
            success=False,
            deployment_id=deployment_id,
            image_tag=image_tag,
            instance_id=instance_id,
            started_at=start_time,
        )

        try:
            public_ip = self.ec2_client.get_instance_public_ip(instance_id)
            if not public_ip:
                raise DeploymentError(f"Instance {instance_id} has no public IP")

            if not self.ec2_client.check_ssm_agent_status(instance_id):
                raise DeploymentError(
                    f"SSM agent not running on {instance_id}"
                )

            canary_container_name = f"{container_name}-canary"
            logger.info(
                "Starting canary deployment",
                extra={
                    "deployment_id": deployment_id,
                    "image_tag": image_tag,
                    "canary_container": canary_container_name,
                },
            )

            # --- Step 1: Start canary container on canary_port ---
            self._start_canary_container(
                instance_id=instance_id,
                image_tag=image_tag,
                canary_container_name=canary_container_name,
                env_vars=env_vars,
            )
            logger.info("Canary container started; waiting 15s for startup")
            time.sleep(15)

            # --- Step 2: Run traffic stages ---
            stages = self._build_stages()
            all_stages_passed = True

            for idx, stage in enumerate(stages):
                logger.info(
                    f"Canary stage {idx + 1}/{len(stages)}: "
                    f"{stage.canary_weight}:{stage.prod_weight} "
                    f"(canary:prod) for {stage.duration_seconds}s"
                )

                # Update nginx weights
                if stage.prod_weight > 0:
                    self._update_nginx_weights(
                        instance_id=instance_id,
                        prod_port=self.prod_port,
                        canary_port=self.canary_port,
                        prod_weight=stage.prod_weight,
                        canary_weight=stage.canary_weight,
                    )
                else:
                    # Final stage — route all traffic to canary port
                    self._update_nginx_weights(
                        instance_id=instance_id,
                        prod_port=self.prod_port,
                        canary_port=self.canary_port,
                        prod_weight=0,
                        canary_weight=1,
                    )

                # Observe canary for this stage's duration
                stage_result = self._observe_stage(
                    idx=idx,
                    stage=stage,
                    public_ip=public_ip,
                    health_check_path=health_check_path,
                )
                result.stage_results.append(stage_result)
                result.stages_completed += 1
                canary_pct = round(
                    stage.canary_weight / (stage.canary_weight + stage.prod_weight) * 100
                ) if (stage.canary_weight + stage.prod_weight) > 0 else 100
                result.final_percentage = canary_pct

                if not stage_result.completed:
                    # Rollback — restore nginx + stop canary
                    logger.error(
                        f"Canary failed at stage {idx + 1} "
                        f"(error_rate={stage_result.error_rate:.1%}); rolling back"
                    )
                    result.error_rate_at_failure = stage_result.error_rate
                    self._rollback_nginx(instance_id)
                    self._stop_canary_container(instance_id, canary_container_name)
                    result.rollback_performed = True
                    all_stages_passed = False
                    result.error_message = (
                        f"Canary aborted at stage {idx + 1}: "
                        f"error rate {stage_result.error_rate:.1%} > threshold "
                        f"{self.error_rate_threshold:.1%}"
                    )
                    break

            if all_stages_passed:
                # Full rollout: stop production container and rename canary
                self._promote_canary(
                    instance_id=instance_id,
                    container_name=container_name,
                    canary_container_name=canary_container_name,
                    image_tag=image_tag,
                    env_vars=env_vars,
                )
                result.success = True
                result.final_percentage = 100
                logger.info(
                    "Canary deployment fully promoted to production",
                    extra={"deployment_id": deployment_id},
                )

        except Exception as exc:
            result.success = False
            result.error_message = str(exc)
            logger.exception(
                "Canary deployment failed with exception",
                extra={"deployment_id": deployment_id},
            )
            # Best-effort rollback
            try:
                self._rollback_nginx(instance_id)
                self._stop_canary_container(
                    instance_id, f"{container_name}-canary"
                )
                result.rollback_performed = True
            except Exception:
                pass

        finally:
            result.completed_at = datetime.utcnow()
            result.duration_seconds = int(
                (result.completed_at - start_time).total_seconds()
            )

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_stages(self) -> list[CanaryStage]:
        return [
            CanaryStage(
                canary_weight=1,
                prod_weight=9,
                duration_seconds=self.stage_duration_seconds,
            ),
            CanaryStage(
                canary_weight=1,
                prod_weight=1,
                duration_seconds=self.stage_duration_seconds,
            ),
            CanaryStage(
                canary_weight=1,
                prod_weight=0,
                duration_seconds=0,  # No need to observe full-rollout stage
            ),
        ]

    def _start_canary_container(
        self,
        instance_id: str,
        image_tag: str,
        canary_container_name: str,
        env_vars: Optional[dict[str, str]],
    ) -> None:
        self.ec2_client.deploy_container(
            instance_id=instance_id,
            image_tag=image_tag,
            container_name=canary_container_name,
            port=self.canary_port,
            env_vars=env_vars,
            stop_existing=True,
        )

    def _stop_canary_container(
        self, instance_id: str, canary_container_name: str
    ) -> None:
        try:
            self.ec2_client.stop_container(
                instance_id=instance_id,
                container_name=canary_container_name,
                force=True,
            )
        except Exception as exc:
            logger.warning(
                f"Failed to stop canary container (non-fatal): {exc}"
            )

    def _promote_canary(
        self,
        instance_id: str,
        container_name: str,
        canary_container_name: str,
        image_tag: str,
        env_vars: Optional[dict[str, str]],
    ) -> None:
        """Stop the production container and redeploy canary image on prod port."""
        # Stop old production container
        try:
            self.ec2_client.stop_container(
                instance_id=instance_id,
                container_name=container_name,
                force=True,
            )
        except Exception:
            pass  # may already be stopped

        # Stop the canary container (running on canary port)
        self._stop_canary_container(instance_id, canary_container_name)

        # Redeploy the new image on the production port
        self.ec2_client.deploy_container(
            instance_id=instance_id,
            image_tag=image_tag,
            container_name=container_name,
            port=self.prod_port,
            env_vars=env_vars,
            stop_existing=True,
        )

        # Restore nginx to single upstream (production port only)
        self._restore_nginx_single_upstream(instance_id)

    def _update_nginx_weights(
        self,
        instance_id: str,
        prod_port: int,
        canary_port: int,
        prod_weight: int,
        canary_weight: int,
    ) -> None:
        """Write nginx upstream config via SSM and reload nginx."""
        if prod_weight == 0:
            conf = _NGINX_UPSTREAM_TEMPLATE.format(
                prod_port=canary_port,
                prod_weight=1,
                canary_port=canary_port,
                canary_weight=1,
            )
        else:
            conf = _NGINX_UPSTREAM_TEMPLATE.format(
                prod_port=prod_port,
                prod_weight=prod_weight,
                canary_port=canary_port,
                canary_weight=canary_weight,
            )

        cmd = (
            f"cat > {_NGINX_CONF_PATH} <<'NGINX_EOF'\n{conf}\nNGINX_EOF\n"
            f"{_NGINX_RELOAD_CMD}"
        )
        self.ec2_client.run_command(instance_id=instance_id, command=cmd)
        logger.debug(
            "nginx upstream updated",
            extra={
                "prod_weight": prod_weight,
                "canary_weight": canary_weight,
                "prod_port": prod_port,
                "canary_port": canary_port,
            },
        )

    def _rollback_nginx(self, instance_id: str) -> None:
        """Restore nginx to production-only upstream and reload."""
        conf = _NGINX_UPSTREAM_PRODUCTION_ONLY.format(prod_port=self.prod_port)
        cmd = (
            f"cat > {_NGINX_CONF_PATH} <<'NGINX_EOF'\n{conf}\nNGINX_EOF\n"
            f"{_NGINX_RELOAD_CMD}"
        )
        try:
            self.ec2_client.run_command(instance_id=instance_id, command=cmd)
            logger.info("nginx rolled back to production-only upstream")
        except Exception as exc:
            logger.error(f"nginx rollback failed: {exc}")

    def _restore_nginx_single_upstream(self, instance_id: str) -> None:
        """After full promotion, restore nginx to single production upstream."""
        self._rollback_nginx(instance_id)

    def _observe_stage(
        self,
        idx: int,
        stage: CanaryStage,
        public_ip: str,
        health_check_path: str,
    ) -> CanaryStageResult:
        """Run health checks against the canary endpoint for the stage duration."""
        if stage.duration_seconds == 0:
            # Final full-rollout stage — skip observation
            return CanaryStageResult(
                stage_index=idx,
                canary_weight=stage.canary_weight,
                prod_weight=stage.prod_weight,
                duration_seconds=0,
                completed=True,
            )

        canary_url = (
            f"http://{public_ip}:{self.canary_port}{health_check_path}"
        )
        interval = self.health_check_interval_seconds
        num_checks = max(1, stage.duration_seconds // interval)

        passed = 0
        total = 0

        for i in range(num_checks):
            total += 1
            try:
                hc: HealthCheckResult = self.health_checker.check_http(canary_url)
                if hc.healthy:
                    passed += 1
            except Exception as exc:
                logger.warning(
                    f"Stage {idx + 1} health check error: {exc}"
                )

            if i < num_checks - 1:
                time.sleep(interval)

        error_rate = 1.0 - (passed / total) if total > 0 else 1.0
        completed = error_rate <= self.error_rate_threshold

        logger.info(
            f"Stage {idx + 1} observation complete",
            extra={
                "passed": passed,
                "total": total,
                "error_rate": f"{error_rate:.1%}",
                "completed": completed,
            },
        )

        return CanaryStageResult(
            stage_index=idx,
            canary_weight=stage.canary_weight,
            prod_weight=stage.prod_weight,
            duration_seconds=stage.duration_seconds,
            completed=completed,
            error_rate=error_rate,
            health_checks_passed=passed,
            health_checks_total=total,
        )

    def rollback(
        self,
        deployment_id: str,
        instance_id: str,
        container_name: str,
    ) -> bool:
        """Emergency rollback — restore nginx and stop canary.

        Returns:
            True if rollback succeeded; False otherwise.
        """
        try:
            self._rollback_nginx(instance_id)
            self._stop_canary_container(
                instance_id, f"{container_name}-canary"
            )
            logger.info(
                "Emergency canary rollback complete",
                extra={"deployment_id": deployment_id},
            )
            return True
        except Exception as exc:
            logger.error(f"Emergency rollback failed: {exc}")
            return False
