"""
Complete Day 3 Manual Test Suite

Run all manual tests in sequence.
Works on Windows (PowerShell, CMD, Git Bash).
"""

import os
import sys

# Add project root to Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def print_header(title):
    """Print section header."""
    print("\n" + "=" * 70)
    print(f" {title}")
    print("=" * 70)


def print_test(name, passed):
    """Print test result."""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"{status} {name}")


def test_imports():
    """Test that all required modules can be imported."""
    print_header("TEST 1: Verify Imports")

    modules = [
        ("Language Detector", "infrastructure.build.language_detector"),
        ("Dockerfile Optimizer", "infrastructure.build.dockerfile_optimizer"),
        ("Docker Builder", "infrastructure.build.docker_builder"),
        ("Build Agent", "agents.build.build_agent"),
    ]

    results = []
    for name, module in modules:
        try:
            __import__(module)
            print_test(name, True)
            results.append(True)
        except ImportError as e:
            print_test(f"{name}: {e}", False)
            results.append(False)

    return all(results)


def test_language_detector():
    """Test Language Detector."""
    print_header("TEST 2: Language Detector")

    try:
        from infrastructure.build.language_detector import LanguageDetector

        detector = LanguageDetector()
        project_path = os.path.join(os.path.dirname(__file__), '..', '..')

        result = detector.detect(project_path)

        tests = [
            ("Detects Python", result.language == "python"),
            ("Detects FastAPI", result.framework == "fastapi"),
            ("Detects pip", result.package_manager == "pip"),
            ("Finds requirements.txt", result.dependencies_file == "requirements.txt"),
        ]

        for name, passed in tests:
            print_test(name, passed)

        return all(t[1] for t in tests)

    except Exception as e:
        print_test(f"Language Detector: {e}", False)
        return False


def test_dockerfile_optimizer():
    """Test Dockerfile Optimizer."""
    print_header("TEST 3: Dockerfile Optimizer")

    try:
        from infrastructure.build.language_detector import LanguageDetector
        from infrastructure.build.dockerfile_optimizer import DockerfileOptimizer

        detector = LanguageDetector()
        optimizer = DockerfileOptimizer()
        project_path = os.path.join(os.path.dirname(__file__), '..', '..')

        project_info = detector.detect(project_path)
        dockerfile = optimizer.optimize(project_path, project_info)
        analysis = optimizer._analyze_project(project_path, project_info)

        tests = [
            ("Generates Dockerfile", len(dockerfile) > 100),
            ("Multi-stage build", "AS" in dockerfile),
            ("Non-root user", "USER appuser" in dockerfile),
            ("Health check", "HEALTHCHECK" in dockerfile),
            ("Detects dependencies", len(analysis.runtime_deps) > 0),
            ("Extracts env vars", len(analysis.env_vars) > 0),
            ("Detects ports", len(analysis.exposes_ports) > 0),
        ]

        for name, passed in tests:
            print_test(name, passed)

        print(f"\nDetails:")
        print(f"  - Dockerfile: {len(dockerfile)} chars, {len(dockerfile.split(chr(10)))} lines")
        print(f"  - Dependencies: {len(analysis.runtime_deps)}")
        print(f"  - Env vars: {len(analysis.env_vars)}")
        print(f"  - Ports: {analysis.exposes_ports}")

        return all(t[1] for t in tests)

    except Exception as e:
        print_test(f"Dockerfile Optimizer: {e}", False)
        return False


def test_docker_builder():
    """Test Docker Builder."""
    print_header("TEST 4: Docker Builder")

    try:
        from infrastructure.build.docker_builder import DockerBuilder

        builder = DockerBuilder()

        tests = [
            ("Docker client initialized", builder.client is not None),
        ]

        # Test list images (non-destructive)
        try:
            images = builder.list_images()
            tests.append(("List images works", isinstance(images, list)))
        except Exception as e:
            tests.append((f"List images: {e}", False))

        for name, passed in tests:
            print_test(name, passed)

        return all(t[1] for t in tests)

    except Exception as e:
        print_test(f"Docker Builder: {e}", False)
        return False


def test_build_agent():
    """Test Build Agent."""
    print_header("TEST 5: Build Agent with CrewAI")

    groq_api_key = os.getenv('GROQ_API_KEY')
    if not groq_api_key:
        print_test("GROQ_API_KEY not set", False)
        print("  Hint: Set GROQ_API_KEY environment variable")
        return False

    try:
        from agents.build.build_agent import BuildAgent

        agent = BuildAgent(groq_api_key=groq_api_key)
        project_path = os.path.join(os.path.dirname(__file__), '..', '..')

        tests = [
            ("Agent initialized", agent is not None),
            ("Has detector", agent.detector is not None),
            ("Has optimizer", agent.optimizer is not None),
            ("Has builder", agent.builder is not None),
            ("Has Groq client", agent.groq_client is not None),
            ("Has CrewAI agent", agent.agent is not None),
        ]

        # Test Dockerfile generation
        try:
            dockerfile = agent.generate_dockerfile_only(project_path)
            tests.append(("Generates Dockerfile", len(dockerfile) > 100))
        except Exception as e:
            tests.append((f"Generate Dockerfile: {e}", False))

        for name, passed in tests:
            print_test(name, passed)

        return all(t[1] for t in tests)

    except Exception as e:
        print_test(f"Build Agent: {e}", False)
        return False


def test_ai_analysis():
    """Test AI-powered analysis."""
    print_header("TEST 6: AI Analysis with Groq LLM")

    groq_api_key = os.getenv('GROQ_API_KEY')
    if not groq_api_key:
        print_test("GROQ_API_KEY not set", False)
        return False

    try:
        from agents.build.build_agent import BuildAgent

        agent = BuildAgent(groq_api_key=groq_api_key)

        test_dockerfile = """FROM python:3.11-slim
RUN pip install flask
COPY . /app
WORKDIR /app
CMD ["python", "app.py"]"""

        print("  Analyzing Dockerfile with Groq LLM...")
        analysis = agent._analyze_dockerfile_with_ai(test_dockerfile)

        tests = [
            ("AI analysis returns text", isinstance(analysis, str)),
            ("Analysis is substantial", len(analysis) > 50),
            ("No error message", "Analysis failed:" not in analysis),
        ]

        for name, passed in tests:
            print_test(name, passed)

        if all(t[1] for t in tests):
            print(f"\n  Analysis preview: {analysis[:200]}...")

        return all(t[1] for t in tests)

    except Exception as e:
        print_test(f"AI Analysis: {e}", False)
        return False


def test_integration():
    """Test complete pipeline integration."""
    print_header("TEST 7: Integration - Complete Pipeline")

    try:
        from infrastructure.build.language_detector import LanguageDetector
        from infrastructure.build.dockerfile_optimizer import DockerfileOptimizer

        project_path = os.path.join(os.path.dirname(__file__), '..', '..')

        # Step 1: Detect
        detector = LanguageDetector()
        project_info = detector.detect(project_path)
        step1 = project_info.language == "python"
        print_test("Step 1: Language detection", step1)

        # Step 2: Optimize
        optimizer = DockerfileOptimizer()
        dockerfile = optimizer.optimize(project_path, project_info)
        step2 = len(dockerfile) > 100
        print_test("Step 2: Dockerfile generation", step2)

        # Step 3: Analyze
        analysis = optimizer._analyze_project(project_path, project_info)
        step3 = len(analysis.runtime_deps) > 0
        print_test("Step 3: Project analysis", step3)

        return step1 and step2 and step3

    except Exception as e:
        print_test(f"Integration: {e}", False)
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print(" DAY 3 BUILD AGENT - COMPLETE MANUAL TEST SUITE")
    print("=" * 70)
    print("\nThis will test all Day 3 components:")
    print("  1. Language Detector")
    print("  2. Dockerfile Optimizer")
    print("  3. Docker Builder")
    print("  4. Build Agent with CrewAI")
    print("  5. AI Analysis (Groq LLM)")
    print("  6. Integration Pipeline")
    print("\nTests are non-destructive (no Docker builds)")
    print()

    # Run all tests
    results = {
        "Imports": test_imports(),
        "Language Detector": test_language_detector(),
        "Dockerfile Optimizer": test_dockerfile_optimizer(),
        "Docker Builder": test_docker_builder(),
        "Build Agent": test_build_agent(),
        "AI Analysis": test_ai_analysis(),
        "Integration": test_integration(),
    }

    # Print summary
    print_header("TEST SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status} {name}")

    print()
    print(f"Results: {passed}/{total} test suites passed")
    print()

    if passed == total:
        print("=" * 70)
        print(" SUCCESS: DAY 3 - 100% COMPLETE - ALL TESTS PASSED")
        print("=" * 70)
        print()
        print("Next: Day 4 - Deploy Agent Implementation")
        return 0
    else:
        print("=" * 70)
        print(" ERROR: SOME TESTS FAILED - Review errors above")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
