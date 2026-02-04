"""Tests for the Deploy Agent."""

import pytest

from agents.deploy_agent import create_deploy_agent


@pytest.mark.unit
class TestDeployAgent:
    def test_agent_creation(self):
        """Deploy agent should be created with correct role and tools."""
        agent = create_deploy_agent()
        assert agent.role == "Deployment Specialist"
        assert len(agent.tools) == 4

    def test_agent_does_not_delegate(self):
        """Deploy agent should not delegate tasks."""
        agent = create_deploy_agent()
        assert agent.allow_delegation is False

    def test_deploy_container_not_implemented(self):
        """deploy_container tool should raise NotImplementedError until Day 4."""
        from agents.deploy_agent import deploy_container

        with pytest.raises(NotImplementedError):
            deploy_container.run("i-123456", "app:latest")

    def test_health_check_not_implemented(self):
        """health_check tool should raise NotImplementedError until Day 4."""
        from agents.deploy_agent import health_check

        with pytest.raises(NotImplementedError):
            health_check.run("i-123456")

    def test_rollback_not_implemented(self):
        """rollback_deployment tool should raise NotImplementedError until Day 4."""
        from agents.deploy_agent import rollback_deployment

        with pytest.raises(NotImplementedError):
            rollback_deployment.run("i-123456", "app:v1")
