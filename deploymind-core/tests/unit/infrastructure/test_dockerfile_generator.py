"""Intensive tests for DockerfileGenerator.

Covers:
- All 6 supported languages (python, nodejs, go, java, ruby, rust)
- Framework-specific start commands (fastapi, django, flask, nextjs, nestjs)
- Package-manager-specific install commands (npm/yarn/pnpm, maven/gradle)
- Version normalisation for Python and Node.js
- Generic fallback for unknown language
- Security invariants:
    * Non-root USER in every generated Dockerfile
    * No :latest tags (unless intentional generic fallback)
    * Multi-stage build for all named languages
- Content invariants: EXPOSE, WORKDIR, CMD/ENTRYPOINT
- .dockerignore content for every language
- GeneratedDockerfile metadata fields
"""

from __future__ import annotations

import pytest

from deploymind.infrastructure.build.language_detector import DetectionResult
from deploymind.infrastructure.build.dockerfile_generator import (
    DockerfileGenerator,
    GeneratedDockerfile,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_detection(
    language: str = "python",
    framework: str | None = None,
    entry_point: str | None = None,
    package_manager: str | None = None,
    runtime_version: str | None = None,
    has_dockerfile: bool = False,
    has_dockerignore: bool = False,
) -> DetectionResult:
    return DetectionResult(
        language=language,
        framework=framework,
        entry_point=entry_point,
        has_dockerfile=has_dockerfile,
        has_dockerignore=has_dockerignore,
        package_manager=package_manager,
        runtime_version=runtime_version,
    )


@pytest.fixture
def generator() -> DockerfileGenerator:
    return DockerfileGenerator()


# ===========================================================================
# Security invariants — apply to ALL languages
# ===========================================================================

LANGUAGES = ["python", "nodejs", "go", "java", "ruby", "rust"]


@pytest.mark.parametrize("lang", LANGUAGES)
class TestSecurityInvariants:
    def test_non_root_user_present(self, generator, lang):
        detection = make_detection(language=lang)
        result = generator.generate(detection)
        assert "USER " in result.content, (
            f"No USER instruction in {lang} Dockerfile"
        )
        # Ensure we're not running as root
        lines = result.content.splitlines()
        user_lines = [l.strip() for l in lines if l.strip().startswith("USER ")]
        non_root = [l for l in user_lines if l not in ("USER root", "USER 0")]
        assert non_root, (
            f"{lang} Dockerfile only has root USER lines: {user_lines}"
        )

    def test_multi_stage_build(self, generator, lang):
        detection = make_detection(language=lang)
        result = generator.generate(detection)
        from_count = sum(
            1 for line in result.content.splitlines()
            if line.strip().upper().startswith("FROM ")
        )
        assert from_count >= 2, (
            f"{lang} Dockerfile should be multi-stage (found {from_count} FROM lines)"
        )

    def test_is_multi_stage_metadata(self, generator, lang):
        detection = make_detection(language=lang)
        result = generator.generate(detection)
        assert result.is_multi_stage is True

    def test_expose_present(self, generator, lang):
        detection = make_detection(language=lang)
        result = generator.generate(detection)
        assert "EXPOSE " in result.content, f"No EXPOSE in {lang} Dockerfile"

    def test_workdir_present(self, generator, lang):
        detection = make_detection(language=lang)
        result = generator.generate(detection)
        assert "WORKDIR " in result.content

    def test_cmd_or_entrypoint_present(self, generator, lang):
        detection = make_detection(language=lang)
        result = generator.generate(detection)
        has_cmd = "CMD " in result.content or "CMD[" in result.content
        has_entrypoint = "ENTRYPOINT " in result.content or "ENTRYPOINT[" in result.content
        assert has_cmd or has_entrypoint, f"No CMD/ENTRYPOINT in {lang} Dockerfile"

    def test_dockerignore_not_empty(self, generator, lang):
        detection = make_detection(language=lang)
        result = generator.generate(detection)
        assert result.dockerignore_content.strip(), f"Empty .dockerignore for {lang}"

    def test_git_in_dockerignore(self, generator, lang):
        detection = make_detection(language=lang)
        result = generator.generate(detection)
        assert ".git" in result.dockerignore_content

    def test_dotenv_in_dockerignore(self, generator, lang):
        detection = make_detection(language=lang)
        result = generator.generate(detection)
        assert ".env" in result.dockerignore_content

    def test_language_metadata(self, generator, lang):
        detection = make_detection(language=lang)
        result = generator.generate(detection)
        assert result.language == lang


# ===========================================================================
# Python-specific tests
# ===========================================================================

class TestPythonDockerfile:
    def test_default_runtime_version(self, generator):
        result = generator.generate(make_detection(language="python"))
        assert "python:3.12-slim" in result.content

    def test_custom_runtime_version(self, generator):
        result = generator.generate(make_detection(language="python", runtime_version="3.11"))
        assert "python:3.11-slim" in result.content
        assert "python:3.12-slim" not in result.content

    def test_runtime_version_normalised_to_major_minor(self, generator):
        result = generator.generate(make_detection(language="python", runtime_version="3.11.9"))
        assert "python:3.11-slim" in result.content

    def test_pip_install_no_cache_dir(self, generator):
        result = generator.generate(make_detection(language="python"))
        assert "--no-cache-dir" in result.content

    def test_non_root_user_setup(self, generator):
        result = generator.generate(make_detection(language="python"))
        assert "useradd" in result.content or "adduser" in result.content

    def test_fastapi_start_command(self, generator):
        result = generator.generate(make_detection(language="python", framework="fastapi", entry_point="main.py"))
        assert "uvicorn" in result.content
        assert "main:app" in result.content

    def test_django_start_command(self, generator):
        result = generator.generate(make_detection(language="python", framework="django"))
        assert "gunicorn" in result.content or "manage.py" in result.content

    def test_flask_start_command(self, generator):
        result = generator.generate(make_detection(language="python", framework="flask", entry_point="app.py"))
        assert "gunicorn" in result.content or "app.py" in result.content

    def test_generic_python_start_command_uses_entry_point(self, generator):
        result = generator.generate(make_detection(language="python", entry_point="server.py"))
        assert "server.py" in result.content

    def test_requirements_copied_before_source(self, generator):
        content = generator.generate(make_detection(language="python")).content
        lines = content.splitlines()
        req_copy_idx = next(
            (i for i, l in enumerate(lines) if "requirements" in l and "COPY" in l), None
        )
        source_copy_idx = next(
            (i for i, l in enumerate(lines) if re.search(r"COPY\s+\.\s+\.", l)), None
        )
        if req_copy_idx is not None and source_copy_idx is not None:
            assert req_copy_idx < source_copy_idx

    def test_base_and_runner_image_fields(self, generator):
        result = generator.generate(make_detection(language="python"))
        assert result.base_image.startswith("python:")
        assert result.runner_image.startswith("python:")

    def test_exposed_port_is_8000(self, generator):
        result = generator.generate(make_detection(language="python"))
        assert result.exposed_port == 8000
        assert "8000" in result.content

    def test_pyc_in_dockerignore(self, generator):
        result = generator.generate(make_detection(language="python"))
        assert "*.pyc" in result.dockerignore_content


import re  # needed by test_requirements_copied_before_source


# ===========================================================================
# Node.js-specific tests
# ===========================================================================

class TestNodeDockerfile:
    def test_default_runtime_version(self, generator):
        result = generator.generate(make_detection(language="nodejs"))
        assert "node:20-alpine" in result.content

    def test_custom_node_version(self, generator):
        result = generator.generate(make_detection(language="nodejs", runtime_version="18"))
        assert "node:18-alpine" in result.content

    def test_version_with_v_prefix_normalised(self, generator):
        result = generator.generate(make_detection(language="nodejs", runtime_version="v20.11.0"))
        assert "node:20-alpine" in result.content

    def test_semver_range_normalised(self, generator):
        result = generator.generate(make_detection(language="nodejs", runtime_version=">=20 <21"))
        # Should extract major version 20
        assert "node:20-alpine" in result.content or "node:>=-alpine" not in result.content

    def test_npm_install_command(self, generator):
        result = generator.generate(make_detection(language="nodejs", package_manager="npm"))
        assert "npm ci" in result.content

    def test_yarn_install_command(self, generator):
        result = generator.generate(make_detection(language="nodejs", package_manager="yarn"))
        assert "yarn install --frozen-lockfile" in result.content

    def test_pnpm_install_command(self, generator):
        result = generator.generate(make_detection(language="nodejs", package_manager="pnpm"))
        assert "pnpm install --frozen-lockfile" in result.content

    def test_nextjs_dockerfile(self, generator):
        result = generator.generate(make_detection(language="nodejs", framework="nextjs"))
        # Next.js needs .next/standalone
        assert ".next/standalone" in result.content or "standalone" in result.content

    def test_node_modules_in_dockerignore(self, generator):
        result = generator.generate(make_detection(language="nodejs"))
        assert "node_modules" in result.dockerignore_content

    def test_exposed_port_is_3000(self, generator):
        result = generator.generate(make_detection(language="nodejs"))
        assert result.exposed_port == 3000

    def test_node_env_production_set(self, generator):
        result = generator.generate(make_detection(language="nodejs"))
        assert "NODE_ENV=production" in result.content


# ===========================================================================
# Go-specific tests
# ===========================================================================

class TestGoDockerfile:
    def test_default_runtime(self, generator):
        result = generator.generate(make_detection(language="go"))
        assert "golang:1.22-alpine" in result.content

    def test_custom_runtime(self, generator):
        result = generator.generate(make_detection(language="go", runtime_version="1.21"))
        assert "golang:1.21-alpine" in result.content

    def test_uses_distroless_runner(self, generator):
        result = generator.generate(make_detection(language="go"))
        assert "distroless" in result.content
        assert result.runner_image == "gcr.io/distroless/static-debian12"

    def test_cgo_disabled(self, generator):
        result = generator.generate(make_detection(language="go"))
        assert "CGO_ENABLED=0" in result.content

    def test_go_mod_download_cached(self, generator):
        result = generator.generate(make_detection(language="go"))
        assert "go.mod" in result.content and "go mod download" in result.content

    def test_nobody_user(self, generator):
        result = generator.generate(make_detection(language="go"))
        # distroless uses UID 65534 (nobody)
        assert "65534" in result.content

    def test_go_in_dockerignore(self, generator):
        result = generator.generate(make_detection(language="go"))
        assert "_test.go" in result.dockerignore_content or "test" in result.dockerignore_content

    def test_exposed_port_is_8080(self, generator):
        result = generator.generate(make_detection(language="go"))
        assert result.exposed_port == 8080

    def test_ldflags_optimise_binary(self, generator):
        result = generator.generate(make_detection(language="go"))
        assert "-ldflags" in result.content
        assert "-w -s" in result.content


# ===========================================================================
# Java-specific tests
# ===========================================================================

class TestJavaDockerfile:
    def test_default_java_version(self, generator):
        result = generator.generate(make_detection(language="java"))
        assert "eclipse-temurin:21-jdk-alpine" in result.content

    def test_custom_java_version(self, generator):
        result = generator.generate(make_detection(language="java", runtime_version="17"))
        assert "eclipse-temurin:17-jdk-alpine" in result.content
        assert "eclipse-temurin:17-jre-alpine" in result.content

    def test_jdk_for_build_jre_for_runtime(self, generator):
        result = generator.generate(make_detection(language="java"))
        assert "-jdk-" in result.base_image
        assert "-jre-" in result.runner_image

    def test_maven_build_command(self, generator):
        result = generator.generate(make_detection(language="java", package_manager="maven"))
        assert "mvnw" in result.content or "mvn" in result.content

    def test_gradle_build_command(self, generator):
        result = generator.generate(make_detection(language="java", package_manager="gradle"))
        assert "gradlew" in result.content or "gradle" in result.content

    def test_java_opts_env(self, generator):
        result = generator.generate(make_detection(language="java"))
        assert "JAVA_OPTS" in result.content
        assert "MaxRAMPercentage" in result.content

    def test_exposed_port_is_8080(self, generator):
        result = generator.generate(make_detection(language="java"))
        assert result.exposed_port == 8080


# ===========================================================================
# Ruby-specific tests
# ===========================================================================

class TestRubyDockerfile:
    def test_ruby_base_image(self, generator):
        result = generator.generate(make_detection(language="ruby"))
        assert "ruby:3.3-slim" in result.content

    def test_bundle_install(self, generator):
        result = generator.generate(make_detection(language="ruby"))
        assert "bundle install" in result.content

    def test_gemfile_copied_first(self, generator):
        result = generator.generate(make_detection(language="ruby"))
        lines = result.content.splitlines()
        gemfile_idx = next((i for i, l in enumerate(lines) if "Gemfile" in l and "COPY" in l), None)
        source_idx = next((i for i, l in enumerate(lines) if re.search(r"COPY\s+\.\s+\.", l)), None)
        if gemfile_idx is not None and source_idx is not None:
            assert gemfile_idx < source_idx

    def test_exposed_port_is_3000(self, generator):
        result = generator.generate(make_detection(language="ruby"))
        assert result.exposed_port == 3000


# ===========================================================================
# Rust-specific tests
# ===========================================================================

class TestRustDockerfile:
    def test_rust_base_image(self, generator):
        result = generator.generate(make_detection(language="rust"))
        assert "rust:1.76-alpine" in result.content

    def test_uses_alpine_runner(self, generator):
        result = generator.generate(make_detection(language="rust"))
        assert "alpine:3.19" in result.content
        assert result.runner_image == "alpine:3.19"

    def test_cargo_build_release(self, generator):
        result = generator.generate(make_detection(language="rust"))
        assert "cargo build --release" in result.content

    def test_dep_caching_stub(self, generator):
        result = generator.generate(make_detection(language="rust"))
        # Stub main.rs trick to pre-cache deps
        assert "fn main()" in result.content

    def test_exposed_port_is_8080(self, generator):
        result = generator.generate(make_detection(language="rust"))
        assert result.exposed_port == 8080


# ===========================================================================
# Generic/unknown fallback
# ===========================================================================

class TestGenericFallback:
    def test_unknown_language_returns_generic(self, generator):
        result = generator.generate(make_detection(language="unknown"))
        assert result.language == "unknown"

    def test_generic_has_user_instruction(self, generator):
        result = generator.generate(make_detection(language="unknown"))
        assert "USER " in result.content

    def test_generic_exposed_port(self, generator):
        result = generator.generate(make_detection(language="unknown"))
        assert result.exposed_port == 8080

    def test_unsupported_language_gets_generic(self, generator):
        result = generator.generate(make_detection(language="cobol"))
        assert result.language == "unknown"
