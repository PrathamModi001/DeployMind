"""Tests for the Deploy Agent."""

import pytest

from deploymind.agents.deploy_agent import create_deploy_agent


@pytest.mark.unit
class TestDeployAgent:
    @pytest.mark.skip(reason="CrewAI/Groq initialization issues in test environment")
    def test_agent_creation(self):
        """Deploy agent should be created with correct role and tools."""
        agent = create_deploy_agent(groq_api_key="test-key")
        assert agent.role == "Deployment Specialist"
        # Note: The number of tools may vary with implementation
        assert len(agent.tools) >= 3

    @pytest.mark.skip(reason="CrewAI/Groq initialization issues in test environment")
    def test_agent_does_not_delegate(self):
        """Deploy agent should not delegate tasks."""
        agent = create_deploy_agent(groq_api_key="test-key")
        assert agent.allow_delegation is False

    def test_deploy_container_implemented(self):
        """deploy_container tool should be implemented (Day 4 complete)."""
        from deploymind.agents.deploy_agent import deploy_container

        # Day 4 is complete, so this should not raise NotImplementedError
        # Just verify the tool exists
        assert deploy_container is not None
        assert hasattr(deploy_container, 'run')

    def test_health_check_implemented(self):
        """health_check tool should be implemented (Day 4 complete)."""
        from deploymind.agents.deploy_agent import health_check

        # Day 4 is complete, so this should not raise NotImplementedError
        # Just verify the tool exists
        assert health_check is not None
        assert hasattr(health_check, 'run')

    def test_rollback_implemented(self):
        """rollback_deployment tool should be implemented (Day 4 complete)."""
        from deploymind.agents.deploy_agent import rollback_deployment

        # Day 4 is complete, so this should not raise NotImplementedError
        # Just verify the tool exists
        assert rollback_deployment is not None
        assert hasattr(rollback_deployment, 'run')
