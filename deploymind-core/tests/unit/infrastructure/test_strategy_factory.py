"""Tests for DeploymentStrategyFactory.

Covers:
- create("rolling") returns a RollingDeployer
- create("canary") returns a CanaryDeployer
- Unknown strategy raises ValueError
- Case-insensitive strategy name matching ("Rolling", "CANARY")
- Whitespace-tolerant strategy names (" rolling ")
- kwargs forwarded to deployer constructor
- supported_strategies() returns both names
- is_supported() returns True/False correctly
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deploymind.infrastructure.deployment.strategy_factory import DeploymentStrategyFactory
from deploymind.infrastructure.deployment.rolling_deployer import RollingDeployer
from deploymind.infrastructure.deployment.canary_deployer import CanaryDeployer


@pytest.fixture
def mock_ec2():
    return MagicMock()


@pytest.fixture
def mock_hc():
    return MagicMock()


class TestStrategyFactory:
    def test_rolling_creates_rolling_deployer(self, mock_ec2, mock_hc):
        deployer = DeploymentStrategyFactory.create("rolling", mock_ec2, mock_hc)
        assert isinstance(deployer, RollingDeployer)

    def test_canary_creates_canary_deployer(self, mock_ec2, mock_hc):
        deployer = DeploymentStrategyFactory.create("canary", mock_ec2, mock_hc)
        assert isinstance(deployer, CanaryDeployer)

    def test_unknown_strategy_raises_value_error(self, mock_ec2, mock_hc):
        with pytest.raises(ValueError, match="Unknown deployment strategy"):
            DeploymentStrategyFactory.create("blue_green", mock_ec2, mock_hc)

    def test_error_message_lists_supported(self, mock_ec2, mock_hc):
        try:
            DeploymentStrategyFactory.create("badstrat", mock_ec2, mock_hc)
        except ValueError as exc:
            assert "rolling" in str(exc)
            assert "canary" in str(exc)

    def test_case_insensitive_rolling(self, mock_ec2, mock_hc):
        deployer = DeploymentStrategyFactory.create("Rolling", mock_ec2, mock_hc)
        assert isinstance(deployer, RollingDeployer)

    def test_case_insensitive_canary(self, mock_ec2, mock_hc):
        deployer = DeploymentStrategyFactory.create("CANARY", mock_ec2, mock_hc)
        assert isinstance(deployer, CanaryDeployer)

    def test_whitespace_stripped(self, mock_ec2, mock_hc):
        deployer = DeploymentStrategyFactory.create(" rolling ", mock_ec2, mock_hc)
        assert isinstance(deployer, RollingDeployer)

    def test_kwargs_forwarded_to_canary(self, mock_ec2, mock_hc):
        deployer = DeploymentStrategyFactory.create(
            "canary", mock_ec2, mock_hc, stage_duration_seconds=60
        )
        assert isinstance(deployer, CanaryDeployer)
        assert deployer.stage_duration_seconds == 60

    def test_kwargs_forwarded_to_rolling(self, mock_ec2, mock_hc):
        deployer = DeploymentStrategyFactory.create(
            "rolling", mock_ec2, mock_hc, health_check_duration=30
        )
        assert isinstance(deployer, RollingDeployer)
        assert deployer.health_check_duration == 30

    def test_supported_strategies_contains_rolling(self, mock_ec2, mock_hc):
        assert "rolling" in DeploymentStrategyFactory.supported_strategies()

    def test_supported_strategies_contains_canary(self, mock_ec2, mock_hc):
        assert "canary" in DeploymentStrategyFactory.supported_strategies()

    def test_is_supported_rolling(self):
        assert DeploymentStrategyFactory.is_supported("rolling") is True

    def test_is_supported_canary(self):
        assert DeploymentStrategyFactory.is_supported("canary") is True

    def test_is_supported_unknown(self):
        assert DeploymentStrategyFactory.is_supported("kubernetes") is False

    def test_is_supported_case_insensitive(self):
        assert DeploymentStrategyFactory.is_supported("ROLLING") is True

    def test_rolling_deployer_has_deploy_method(self, mock_ec2, mock_hc):
        deployer = DeploymentStrategyFactory.create("rolling", mock_ec2, mock_hc)
        assert callable(getattr(deployer, "deploy", None))

    def test_canary_deployer_has_deploy_method(self, mock_ec2, mock_hc):
        deployer = DeploymentStrategyFactory.create("canary", mock_ec2, mock_hc)
        assert callable(getattr(deployer, "deploy", None))
