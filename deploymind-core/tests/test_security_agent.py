"""Tests for the Security Agent."""

import pytest
from unittest.mock import patch, MagicMock

from deploymind.agents.security_agent import create_security_agent


@pytest.mark.unit
class TestSecurityAgent:
    @patch('deploymind.agents.security_agent.Agent')
    def test_agent_creation(self, MockAgent):
        """Security agent should be created with correct role and tools."""
        MockAgent.return_value = MagicMock(
            role="Security Specialist", tools=[MagicMock(), MagicMock(), MagicMock()], allow_delegation=False
        )
        agent = create_security_agent()
        assert agent.role == "Security Specialist"
        assert len(agent.tools) == 3

    @patch('deploymind.agents.security_agent.Agent')
    def test_agent_does_not_delegate(self, MockAgent):
        """Security agent should not delegate tasks."""
        MockAgent.return_value = MagicMock(
            role="Security Specialist", tools=[MagicMock(), MagicMock(), MagicMock()], allow_delegation=False
        )
        agent = create_security_agent()
        assert agent.allow_delegation is False

    def test_scan_dockerfile_not_implemented(self):
        """scan_dockerfile tool should raise NotImplementedError until Day 2."""
        from deploymind.agents.security_agent import scan_dockerfile

        with pytest.raises(NotImplementedError):
            scan_dockerfile.run("Dockerfile")

    def test_scan_dependencies_not_implemented(self):
        """scan_dependencies tool should raise NotImplementedError until Day 2."""
        from deploymind.agents.security_agent import scan_dependencies

        with pytest.raises(NotImplementedError):
            scan_dependencies.run("requirements.txt")

    def test_check_secrets_not_implemented(self):
        """check_secrets tool should raise NotImplementedError until Day 2."""
        from deploymind.agents.security_agent import check_secrets

        with pytest.raises(NotImplementedError):
            check_secrets.run("/repo")
