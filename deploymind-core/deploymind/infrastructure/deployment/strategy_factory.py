"""Deployment strategy factory.

Centralises the mapping from strategy name → concrete deployer instance.
Application code calls ``DeploymentStrategyFactory.create(strategy, ...)``
and never imports ``RollingDeployer`` or ``CanaryDeployer`` directly.

Supported strategies:
    "rolling"  — Zero-downtime rolling update (replaces running container).
    "canary"   — Gradual traffic shift 10% → 50% → 100% with auto-rollback.

Adding a new strategy:
    1. Create ``deploymind/infrastructure/deployment/{name}_deployer.py``.
    2. Register it in ``_REGISTRY`` below.
    3. No other file needs to change (Open/Closed Principle).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from deploymind.infrastructure.deployment.rolling_deployer import RollingDeployer
from deploymind.infrastructure.deployment.canary_deployer import CanaryDeployer

if TYPE_CHECKING:
    from deploymind.infrastructure.cloud.aws.ec2_client import EC2Client
    from deploymind.infrastructure.monitoring.health_checker import HealthChecker


# ---------------------------------------------------------------------------
# Type alias for deployer union
# ---------------------------------------------------------------------------

Deployer = RollingDeployer | CanaryDeployer


class DeploymentStrategyFactory:
    """Factory that instantiates deployment strategy objects by name.

    Example::

        deployer = DeploymentStrategyFactory.create(
            strategy="canary",
            ec2_client=container.ec2_client,
            health_checker=health_checker,
        )
        result = deployer.deploy(...)
    """

    _REGISTRY: dict[str, type] = {
        "rolling": RollingDeployer,
        "canary": CanaryDeployer,
    }

    @classmethod
    def create(
        cls,
        strategy: str,
        ec2_client: "EC2Client",
        health_checker: "HealthChecker",
        **kwargs,
    ) -> Deployer:
        """Create a deployer for the named strategy.

        Args:
            strategy: Strategy name — ``"rolling"`` or ``"canary"``.
            ec2_client: Injected EC2 client.
            health_checker: Injected health checker.
            **kwargs: Extra keyword arguments forwarded to the deployer constructor
                (e.g. ``stage_duration_seconds=60`` for canary testing).

        Returns:
            A deployer instance with a ``deploy(...)`` method.

        Raises:
            ValueError: If the strategy name is not recognised.
        """
        normalised = strategy.lower().strip()
        deployer_class = cls._REGISTRY.get(normalised)
        if deployer_class is None:
            supported = list(cls._REGISTRY)
            raise ValueError(
                f"Unknown deployment strategy {strategy!r}. "
                f"Supported: {supported}"
            )
        return deployer_class(
            ec2_client=ec2_client,
            health_checker=health_checker,
            **kwargs,
        )

    @classmethod
    def supported_strategies(cls) -> list[str]:
        """Return list of supported strategy names."""
        return list(cls._REGISTRY)

    @classmethod
    def is_supported(cls, strategy: str) -> bool:
        """Return True if strategy is supported."""
        return strategy.lower().strip() in cls._REGISTRY
