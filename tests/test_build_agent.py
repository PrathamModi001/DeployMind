"""Tests for the Build Agent."""

import pytest

from agents.build_agent import create_build_agent


@pytest.mark.unit
class TestBuildAgent:
    def test_agent_creation(self):
        """Build agent should be created with correct role and tools."""
        agent = create_build_agent()
        assert agent.role == "Build Specialist"
        assert len(agent.tools) == 4

    def test_agent_does_not_delegate(self):
        """Build agent should not delegate tasks."""
        agent = create_build_agent()
        assert agent.allow_delegation is False

    def test_detect_language_not_implemented(self):
        """detect_language tool should raise NotImplementedError until Day 3."""
        from agents.build_agent import detect_language

        with pytest.raises(NotImplementedError):
            detect_language.run("/repo")

    def test_generate_dockerfile_not_implemented(self):
        """generate_dockerfile tool should raise NotImplementedError until Day 3."""
        from agents.build_agent import generate_dockerfile

        with pytest.raises(NotImplementedError):
            generate_dockerfile.run("/repo", "python")

    def test_build_docker_image_not_implemented(self):
        """build_docker_image tool should raise NotImplementedError until Day 3."""
        from agents.build_agent import build_docker_image

        with pytest.raises(NotImplementedError):
            build_docker_image.run("Dockerfile", "app:latest")
