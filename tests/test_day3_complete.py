"""
Comprehensive Day 3 Tests - Build Agent System

Tests all components:
1. Language Detector
2. Dockerfile Optimizer
3. Docker Builder
4. Build Agent with CrewAI
"""

import pytest
import os
import tempfile
from pathlib import Path
from infrastructure.build.language_detector import LanguageDetector, ProjectInfo
from infrastructure.build.dockerfile_optimizer import DockerfileOptimizer
from infrastructure.build.docker_builder import DockerBuilder
from agents.build.build_agent import BuildAgent


class TestLanguageDetector:
    """Test Language Detector functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.detector = LanguageDetector()

    def test_detect_python_project(self):
        """Test Python project detection."""
        # Use current project (DeployMind)
        project_path = os.path.join(os.path.dirname(__file__), '..')

        result = self.detector.detect(project_path)

        assert result.language == "python"
        assert result.framework == "fastapi"
        assert result.package_manager == "pip"
        assert result.dependencies_file == "requirements.txt"

    def test_detect_python_framework(self):
        """Test framework detection for Python."""
        project_path = os.path.join(os.path.dirname(__file__), '..')
        result = self.detector.detect(project_path)

        # DeployMind uses FastAPI
        assert result.framework == "fastapi"

    def test_has_files_python(self):
        """Test _has_files method for Python files."""
        project_path = os.path.join(os.path.dirname(__file__), '..')

        # Should find .py files
        has_py = self.detector._has_files(project_path, ["*.py"])
        assert has_py is True

    def test_read_file_safe(self):
        """Test safe file reading."""
        # Test with existing file
        project_path = os.path.join(os.path.dirname(__file__), '..')
        content = self.detector._read_file_safe(
            os.path.join(project_path, "requirements.txt")
        )
        assert content is not None
        assert "crewai" in content

        # Test with non-existent file
        content = self.detector._read_file_safe("nonexistent_file.txt")
        assert content is None


class TestDockerfileOptimizer:
    """Test Dockerfile Optimizer functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.optimizer = DockerfileOptimizer()
        self.detector = LanguageDetector()

    def test_optimize_python_project(self):
        """Test Dockerfile optimization for Python project."""
        project_path = os.path.join(os.path.dirname(__file__), '..')
        project_info = self.detector.detect(project_path)

        dockerfile = self.optimizer.optimize(project_path, project_info)

        # Check Dockerfile content
        assert "FROM python:" in dockerfile
        assert "multi-stage" in dockerfile.lower() or "AS" in dockerfile
        assert "USER appuser" in dockerfile
        assert "EXPOSE" in dockerfile

    def test_analyze_project(self):
        """Test project analysis."""
        project_path = os.path.join(os.path.dirname(__file__), '..')
        project_info = self.detector.detect(project_path)

        analysis = self.optimizer._analyze_project(project_path, project_info)

        # Check analysis results
        assert len(analysis.runtime_deps) > 0
        assert len(analysis.env_vars) > 0
        assert len(analysis.exposes_ports) > 0

    def test_parse_python_deps(self):
        """Test Python dependency parsing."""
        project_path = os.path.join(os.path.dirname(__file__), '..')

        deps = self.optimizer._parse_python_deps(project_path)

        # DeployMind has these dependencies
        assert len(deps) > 0
        assert "crewai" in [d.lower() for d in deps]

    def test_detect_ports(self):
        """Test port detection from code."""
        project_path = os.path.join(os.path.dirname(__file__), '..')
        project_info = self.detector.detect(project_path)

        ports = self.optimizer._detect_ports(project_path, project_info)

        # Should detect port 8000
        assert len(ports) > 0
        assert 8000 in ports

    def test_detect_env_vars(self):
        """Test environment variable extraction."""
        project_path = os.path.join(os.path.dirname(__file__), '..')
        project_info = self.detector.detect(project_path)

        env_vars = self.optimizer._detect_env_vars(project_path, project_info)

        # Should have env vars from .env.example
        assert len(env_vars) > 0
        assert "GROQ_API_KEY" in env_vars

    def test_generate_dockerignore(self):
        """Test .dockerignore generation."""
        project_path = os.path.join(os.path.dirname(__file__), '..')
        project_info = self.detector.detect(project_path)

        dockerignore = self.optimizer.generate_dockerignore(project_info)

        # Check basic patterns
        assert "__pycache__" in dockerignore
        assert "*.pyc" in dockerignore
        assert ".git" in dockerignore


class TestDockerBuilder:
    """Test Docker Builder functionality."""

    def setup_method(self):
        """Setup test fixtures."""
        self.builder = DockerBuilder()

    def test_docker_client_initialization(self):
        """Test Docker client initialization."""
        assert self.builder.client is not None

    def test_generate_tag(self):
        """Test tag generation."""
        project_info = ProjectInfo(
            language="python",
            framework="fastapi",
            version="3.11",
            package_manager="pip",
            entry_point="app.py",
            dependencies_file="requirements.txt",
            build_command="pip install",
            start_command="python app.py"
        )

        tag = self.builder._generate_tag(project_info)

        assert "deploymind-python-" in tag
        assert len(tag) > 10

    def test_list_images(self):
        """Test listing Docker images."""
        images = self.builder.list_images()

        # Should return a list (may be empty)
        assert isinstance(images, list)

    def test_prune_images(self):
        """Test pruning dangling images."""
        result = self.builder.prune_images(dangling_only=True)

        # Should return dict with results
        assert isinstance(result, dict)


class TestBuildAgent:
    """Test Build Agent with CrewAI integration."""

    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Setup test fixtures."""
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            pytest.skip("GROQ_API_KEY not set")

        self.agent = BuildAgent(groq_api_key=groq_api_key)

    def test_agent_initialization(self):
        """Test Build Agent initialization."""
        assert self.agent.detector is not None
        assert self.agent.optimizer is not None
        assert self.agent.builder is not None
        assert self.agent.groq_client is not None
        assert self.agent.agent is not None

    def test_generate_dockerfile_only(self):
        """Test Dockerfile generation without building."""
        project_path = os.path.join(os.path.dirname(__file__), '..')

        dockerfile = self.agent.generate_dockerfile_only(project_path)

        assert isinstance(dockerfile, str)
        assert len(dockerfile) > 100
        assert "FROM python:" in dockerfile

    def test_analyze_dockerfile_with_ai(self):
        """Test AI-powered Dockerfile analysis."""
        test_dockerfile = """FROM python:3.11-slim
RUN pip install flask
COPY . /app
WORKDIR /app
CMD ["python", "app.py"]"""

        analysis = self.agent._analyze_dockerfile_with_ai(test_dockerfile)

        assert isinstance(analysis, str)
        assert len(analysis) > 50

    def test_get_recommendations_with_ai(self):
        """Test AI-powered recommendations."""
        project_info = {
            "language": "python",
            "framework": "fastapi",
            "package_manager": "pip"
        }

        recommendations = self.agent._get_recommendations_with_ai(project_info)

        assert isinstance(recommendations, str)
        assert len(recommendations) > 50


class TestIntegration:
    """Integration tests for complete pipeline."""

    def test_complete_pipeline_no_build(self):
        """Test complete pipeline without actual Docker build."""
        # Step 1: Detect language
        detector = LanguageDetector()
        project_path = os.path.join(os.path.dirname(__file__), '..')
        project_info = detector.detect(project_path)

        assert project_info.language == "python"

        # Step 2: Optimize Dockerfile
        optimizer = DockerfileOptimizer()
        dockerfile = optimizer.optimize(project_path, project_info)

        assert "FROM python:" in dockerfile

        # Step 3: Analyze
        analysis = optimizer._analyze_project(project_path, project_info)

        assert len(analysis.runtime_deps) > 0
        assert len(analysis.env_vars) > 0

    @pytest.mark.slow
    def test_build_agent_full_pipeline(self):
        """Test Build Agent full pipeline (slow test)."""
        groq_api_key = os.getenv("GROQ_API_KEY")
        if not groq_api_key:
            pytest.skip("GROQ_API_KEY not set")

        agent = BuildAgent(groq_api_key=groq_api_key)
        project_path = os.path.join(os.path.dirname(__file__), '..')

        # Generate Dockerfile only (fast)
        dockerfile = agent.generate_dockerfile_only(project_path)

        assert isinstance(dockerfile, str)
        assert len(dockerfile) > 100


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
