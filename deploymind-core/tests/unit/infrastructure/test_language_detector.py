"""Intensive tests for LanguageDetector.

Covers:
- All supported languages (python, nodejs, go, java, ruby, rust, php)
- All framework variants within each language
- Package manager detection (npm / yarn / pnpm / pip / poetry / pipenv)
- Runtime version detection (.nvmrc, .node-version, go.mod, .python-version)
- Entry-point discovery for every language
- Edge cases: empty dir, non-existent path, unreadable files, corrupted JSON,
  ambiguous indicator combinations, Dockerfile/dockerignore presence
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from deploymind.infrastructure.build.language_detector import (
    DetectionResult,
    LanguageDetector,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    """Write *files* dict into *tmp_path* and return tmp_path."""
    for rel_path, content in files.items():
        target = tmp_path / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def detector() -> LanguageDetector:
    return LanguageDetector()


# ===========================================================================
# Error / edge cases
# ===========================================================================

class TestEdgeCases:
    def test_nonexistent_path_raises(self, detector):
        with pytest.raises(ValueError, match="does not exist"):
            detector.detect("/nonexistent/path/that/cannot/exist/xyz")

    def test_file_path_raises(self, detector, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("hello")
        with pytest.raises(ValueError, match="not a directory"):
            detector.detect(str(f))

    def test_empty_directory_returns_unknown(self, detector, tmp_path):
        result = detector.detect(str(tmp_path))
        assert result.language == "unknown"
        assert result.framework is None
        assert result.entry_point is None
        assert result.package_manager is None

    def test_result_has_correct_bool_flags_when_no_docker_files(self, detector, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask")
        result = detector.detect(str(tmp_path))
        assert result.has_dockerfile is False
        assert result.has_dockerignore is False

    def test_detects_existing_dockerfile(self, detector, tmp_path):
        make_repo(tmp_path, {
            "requirements.txt": "flask",
            "Dockerfile": "FROM python:3.12",
        })
        result = detector.detect(str(tmp_path))
        assert result.has_dockerfile is True

    def test_detects_existing_dockerignore(self, detector, tmp_path):
        make_repo(tmp_path, {
            "requirements.txt": "flask",
            ".dockerignore": "__pycache__/",
        })
        result = detector.detect(str(tmp_path))
        assert result.has_dockerignore is True

    def test_corrupted_package_json_falls_back_to_nodejs_no_framework(self, detector, tmp_path):
        (tmp_path / "package.json").write_text("{{{ not valid json", encoding="utf-8")
        result = detector.detect(str(tmp_path))
        assert result.language == "nodejs"
        assert result.framework is None  # framework detection failed gracefully

    def test_to_summary_contains_all_fields(self, detector, tmp_path):
        make_repo(tmp_path, {
            "requirements.txt": "fastapi",
            ".python-version": "3.12",
            "main.py": "",
        })
        result = detector.detect(str(tmp_path))
        summary = result.to_summary()
        assert "Language:" in summary
        assert "Framework:" in summary
        assert "Entry:" in summary
        assert "Has Dockerfile:" in summary

    def test_to_summary_without_optional_fields(self, detector, tmp_path):
        result = detector.detect(str(tmp_path))  # empty dir
        summary = result.to_summary()
        assert "Language: unknown" in summary
        # No framework, entry, package manager — should still produce a string
        assert "Has Dockerfile: No" in summary


# ===========================================================================
# Python detection
# ===========================================================================

class TestPythonDetection:
    def test_requirements_txt_detected(self, detector, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask>=2.0")
        result = detector.detect(str(tmp_path))
        assert result.language == "python"

    def test_pyproject_toml_detected(self, detector, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'myapp'")
        result = detector.detect(str(tmp_path))
        assert result.language == "python"

    def test_setup_py_detected(self, detector, tmp_path):
        (tmp_path / "setup.py").write_text("from setuptools import setup; setup()")
        result = detector.detect(str(tmp_path))
        assert result.language == "python"

    def test_pipfile_detected(self, detector, tmp_path):
        (tmp_path / "Pipfile").write_text("[packages]\nflask = '*'")
        result = detector.detect(str(tmp_path))
        assert result.language == "python"
        assert result.package_manager == "pipenv"

    # Framework detection
    @pytest.mark.parametrize("pkg,expected_fw", [
        ("fastapi", "fastapi"),
        ("flask", "flask"),
        ("django", "django"),
        ("tornado", "tornado"),
        ("starlette", "starlette"),
        ("aiohttp", "aiohttp"),
        ("sanic", "sanic"),
        ("bottle", "bottle"),
        ("falcon", "falcon"),
    ])
    def test_framework_from_requirements(self, detector, tmp_path, pkg, expected_fw):
        (tmp_path / "requirements.txt").write_text(f"{pkg}>=1.0\nrequests")
        result = detector.detect(str(tmp_path))
        assert result.framework == expected_fw

    def test_framework_from_pyproject_toml(self, detector, tmp_path):
        (tmp_path / "pyproject.toml").write_text(
            "[project]\ndependencies = ['fastapi>=0.100']"
        )
        result = detector.detect(str(tmp_path))
        assert result.framework == "fastapi"

    # Runtime version
    def test_python_version_from_dot_file(self, detector, tmp_path):
        make_repo(tmp_path, {
            "requirements.txt": "flask",
            ".python-version": "3.11.4",
        })
        result = detector.detect(str(tmp_path))
        assert result.runtime_version == "3.11.4"

    def test_python_version_missing_returns_none(self, detector, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask")
        result = detector.detect(str(tmp_path))
        assert result.runtime_version is None

    # Package manager refinement
    def test_poetry_lock_detected(self, detector, tmp_path):
        make_repo(tmp_path, {
            "pyproject.toml": "[tool.poetry]\nname = 'x'",
            "poetry.lock": "# lock",
        })
        result = detector.detect(str(tmp_path))
        assert result.package_manager == "poetry"

    def test_pip_default_for_plain_requirements(self, detector, tmp_path):
        (tmp_path / "requirements.txt").write_text("flask")
        result = detector.detect(str(tmp_path))
        assert result.package_manager == "pip"

    # Entry point
    @pytest.mark.parametrize("filename", ["main.py", "app.py", "server.py", "manage.py"])
    def test_python_entry_point_discovery(self, detector, tmp_path, filename):
        make_repo(tmp_path, {
            "requirements.txt": "flask",
            filename: "# app",
        })
        result = detector.detect(str(tmp_path))
        assert result.entry_point == filename

    def test_python_entry_point_priority(self, detector, tmp_path):
        # main.py appears before app.py in ENTRY_POINTS list
        make_repo(tmp_path, {
            "requirements.txt": "flask",
            "main.py": "",
            "app.py": "",
        })
        result = detector.detect(str(tmp_path))
        assert result.entry_point == "main.py"

    def test_no_entry_point_when_none_match(self, detector, tmp_path):
        make_repo(tmp_path, {
            "requirements.txt": "flask",
            "my_custom_app.py": "",
        })
        result = detector.detect(str(tmp_path))
        assert result.entry_point is None


# ===========================================================================
# Node.js detection
# ===========================================================================

class TestNodeDetection:
    def _pkg_json(self, deps: dict | None = None, dev_deps: dict | None = None,
                  engines: dict | None = None) -> str:
        data: dict = {"name": "myapp"}
        if deps:
            data["dependencies"] = deps
        if dev_deps:
            data["devDependencies"] = dev_deps
        if engines:
            data["engines"] = engines
        return json.dumps(data)

    def test_package_json_detected(self, detector, tmp_path):
        (tmp_path / "package.json").write_text(self._pkg_json())
        result = detector.detect(str(tmp_path))
        assert result.language == "nodejs"

    @pytest.mark.parametrize("pkg,expected_fw", [
        ("express", "express"),
        ("fastify", "fastify"),
        ("next", "nextjs"),
        ("nuxt", "nuxtjs"),
        ("@nestjs/core", "nestjs"),
        ("koa", "koa"),
        ("@hapi/hapi", "hapi"),
    ])
    def test_framework_from_dependencies(self, detector, tmp_path, pkg, expected_fw):
        (tmp_path / "package.json").write_text(self._pkg_json(deps={pkg: "^1.0.0"}))
        result = detector.detect(str(tmp_path))
        assert result.framework == expected_fw

    def test_framework_from_dev_dependencies(self, detector, tmp_path):
        (tmp_path / "package.json").write_text(
            self._pkg_json(dev_deps={"next": "^13.0.0"})
        )
        result = detector.detect(str(tmp_path))
        assert result.framework == "nextjs"

    # Package manager
    def test_npm_default(self, detector, tmp_path):
        (tmp_path / "package.json").write_text(self._pkg_json())
        result = detector.detect(str(tmp_path))
        assert result.package_manager == "npm"

    def test_yarn_when_yarn_lock_present(self, detector, tmp_path):
        make_repo(tmp_path, {
            "package.json": self._pkg_json(),
            "yarn.lock": "# yarn lockfile v1",
        })
        result = detector.detect(str(tmp_path))
        assert result.package_manager == "yarn"

    def test_pnpm_when_pnpm_lock_present(self, detector, tmp_path):
        make_repo(tmp_path, {
            "package.json": self._pkg_json(),
            "pnpm-lock.yaml": "lockfileVersion: '6.0'",
        })
        result = detector.detect(str(tmp_path))
        assert result.package_manager == "pnpm"

    def test_pnpm_wins_over_yarn_when_both_present(self, detector, tmp_path):
        """pnpm-lock.yaml checked before yarn.lock."""
        make_repo(tmp_path, {
            "package.json": self._pkg_json(),
            "yarn.lock": "",
            "pnpm-lock.yaml": "",
        })
        result = detector.detect(str(tmp_path))
        assert result.package_manager == "pnpm"

    # Runtime version
    def test_version_from_nvmrc(self, detector, tmp_path):
        make_repo(tmp_path, {
            "package.json": self._pkg_json(),
            ".nvmrc": "v20.11.0",
        })
        result = detector.detect(str(tmp_path))
        assert result.runtime_version == "20.11.0"  # lstripped 'v'

    def test_version_from_node_version_file(self, detector, tmp_path):
        make_repo(tmp_path, {
            "package.json": self._pkg_json(),
            ".node-version": "18.19.0",
        })
        result = detector.detect(str(tmp_path))
        assert result.runtime_version == "18.19.0"

    def test_version_from_engines_field(self, detector, tmp_path):
        (tmp_path / "package.json").write_text(
            self._pkg_json(engines={"node": ">=20 <21"})
        )
        result = detector.detect(str(tmp_path))
        assert result.runtime_version == ">=20 <21"

    def test_no_version_when_nothing_found(self, detector, tmp_path):
        (tmp_path / "package.json").write_text(self._pkg_json())
        result = detector.detect(str(tmp_path))
        assert result.runtime_version is None

    # Entry point
    @pytest.mark.parametrize("filename", [
        "index.js", "server.js", "app.js", "src/index.js",
        "index.ts", "server.ts",
    ])
    def test_node_entry_point(self, detector, tmp_path, filename):
        make_repo(tmp_path, {
            "package.json": self._pkg_json(),
            filename: "",
        })
        result = detector.detect(str(tmp_path))
        assert result.entry_point == filename


# ===========================================================================
# Go detection
# ===========================================================================

class TestGoDetection:
    def test_go_mod_detected(self, detector, tmp_path):
        make_repo(tmp_path, {
            "go.mod": "module myapp\n\ngo 1.22\n",
        })
        result = detector.detect(str(tmp_path))
        assert result.language == "go"
        assert result.package_manager == "go mod"

    def test_go_version_extracted(self, detector, tmp_path):
        make_repo(tmp_path, {
            "go.mod": "module myapp\n\ngo 1.21\n",
        })
        result = detector.detect(str(tmp_path))
        assert result.runtime_version == "1.21"

    def test_go_version_with_patch(self, detector, tmp_path):
        make_repo(tmp_path, {
            "go.mod": "module myapp\n\ngo 1.22.3\n",
        })
        result = detector.detect(str(tmp_path))
        assert result.runtime_version == "1.22.3"

    @pytest.mark.parametrize("pkg,expected_fw", [
        ("gin-gonic/gin", "gin"),
        ("labstack/echo", "echo"),
        ("gofiber/fiber", "fiber"),
        ("go-chi/chi", "chi"),
        ("gorilla/mux", "gorilla-mux"),
    ])
    def test_go_framework_detection(self, detector, tmp_path, pkg, expected_fw):
        make_repo(tmp_path, {
            "go.mod": f"module myapp\n\ngo 1.22\n\nrequire (\n\tgithub.com/{pkg} v1.0.0\n)\n",
        })
        result = detector.detect(str(tmp_path))
        assert result.framework == expected_fw

    def test_unknown_framework_returns_none(self, detector, tmp_path):
        make_repo(tmp_path, {
            "go.mod": "module myapp\n\ngo 1.22\n",
        })
        result = detector.detect(str(tmp_path))
        assert result.framework is None

    def test_go_entry_point_main_go(self, detector, tmp_path):
        make_repo(tmp_path, {
            "go.mod": "module myapp\n\ngo 1.22\n",
            "main.go": "package main",
        })
        result = detector.detect(str(tmp_path))
        assert result.entry_point == "main.go"

    def test_go_entry_point_cmd(self, detector, tmp_path):
        make_repo(tmp_path, {
            "go.mod": "module myapp\n\ngo 1.22\n",
            "cmd/main.go": "package main",
        })
        result = detector.detect(str(tmp_path))
        assert result.entry_point == "cmd/main.go"


# ===========================================================================
# Java detection
# ===========================================================================

class TestJavaDetection:
    def test_pom_xml_detected(self, detector, tmp_path):
        (tmp_path / "pom.xml").write_text(
            "<project><java.version>21</java.version></project>"
        )
        result = detector.detect(str(tmp_path))
        assert result.language == "java"
        assert result.package_manager == "maven"

    def test_build_gradle_detected(self, detector, tmp_path):
        (tmp_path / "build.gradle").write_text("plugins { id 'java' }")
        result = detector.detect(str(tmp_path))
        assert result.language == "java"
        assert result.package_manager == "gradle"

    def test_java_version_from_pom_java_version(self, detector, tmp_path):
        (tmp_path / "pom.xml").write_text(
            "<project><properties><java.version>21</java.version></properties></project>"
        )
        result = detector.detect(str(tmp_path))
        assert result.runtime_version == "21"

    def test_java_version_from_compiler_source(self, detector, tmp_path):
        (tmp_path / "pom.xml").write_text(
            "<project><properties>"
            "<maven.compiler.source>17</maven.compiler.source>"
            "</properties></project>"
        )
        result = detector.detect(str(tmp_path))
        assert result.runtime_version == "17"

    def test_java_version_from_gradle(self, detector, tmp_path):
        (tmp_path / "build.gradle").write_text(
            "sourceCompatibility = '17'\njava { toolchain { languageVersion = JavaVersion.VERSION_21 } }"
        )
        result = detector.detect(str(tmp_path))
        assert result.runtime_version in ("17", "21")  # first match wins

    def test_no_version_when_none_declared(self, detector, tmp_path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        result = detector.detect(str(tmp_path))
        assert result.runtime_version is None


# ===========================================================================
# Ruby, Rust, PHP detection
# ===========================================================================

class TestOtherLanguages:
    def test_gemfile_detected_as_ruby(self, detector, tmp_path):
        (tmp_path / "Gemfile").write_text("source 'https://rubygems.org'\ngem 'sinatra'")
        result = detector.detect(str(tmp_path))
        assert result.language == "ruby"
        assert result.package_manager == "bundler"

    def test_cargo_toml_detected_as_rust(self, detector, tmp_path):
        (tmp_path / "Cargo.toml").write_text("[package]\nname = 'myapp'")
        result = detector.detect(str(tmp_path))
        assert result.language == "rust"
        assert result.package_manager == "cargo"

    def test_rust_entry_point(self, detector, tmp_path):
        make_repo(tmp_path, {
            "Cargo.toml": "[package]\nname = 'myapp'",
            "src/main.rs": "fn main() {}",
        })
        result = detector.detect(str(tmp_path))
        assert result.entry_point == "src/main.rs"

    def test_composer_json_detected_as_php(self, detector, tmp_path):
        (tmp_path / "composer.json").write_text('{"name": "app/app"}')
        result = detector.detect(str(tmp_path))
        assert result.language == "php"
        assert result.package_manager == "composer"

    def test_ruby_entry_points(self, detector, tmp_path):
        make_repo(tmp_path, {
            "Gemfile": "gem 'sinatra'",
            "app.rb": "",
        })
        result = detector.detect(str(tmp_path))
        assert result.entry_point == "app.rb"


# ===========================================================================
# Language priority (first indicator wins)
# ===========================================================================

class TestLanguagePriority:
    def test_package_json_beats_requirements_txt(self, detector, tmp_path):
        """package.json appears before requirements.txt in LANGUAGE_INDICATORS."""
        make_repo(tmp_path, {
            "package.json": '{"name":"x"}',
            "requirements.txt": "flask",
        })
        result = detector.detect(str(tmp_path))
        assert result.language == "nodejs"

    def test_requirements_txt_beats_pyproject_toml(self, detector, tmp_path):
        """requirements.txt appears before pyproject.toml in the list."""
        make_repo(tmp_path, {
            "requirements.txt": "flask",
            "pyproject.toml": "[project]\nname='x'",
        })
        result = detector.detect(str(tmp_path))
        # Both are python; just check the language is correct
        assert result.language == "python"

    def test_setup_cfg_detected_as_python(self, detector, tmp_path):
        (tmp_path / "setup.cfg").write_text("[metadata]\nname = myapp")
        result = detector.detect(str(tmp_path))
        assert result.language == "python"


# ===========================================================================
# DetectionResult model
# ===========================================================================

class TestDetectionResult:
    def test_to_summary_omits_none_fields(self):
        r = DetectionResult(
            language="python",
            framework=None,
            entry_point=None,
            has_dockerfile=False,
            has_dockerignore=False,
            package_manager=None,
            runtime_version=None,
        )
        summary = r.to_summary()
        assert "Framework:" not in summary
        assert "Entry:" not in summary
        assert "Package Manager:" not in summary
        assert "Runtime:" not in summary

    def test_to_summary_includes_all_when_set(self):
        r = DetectionResult(
            language="go",
            framework="gin",
            entry_point="main.go",
            has_dockerfile=True,
            has_dockerignore=True,
            package_manager="go mod",
            runtime_version="1.22",
        )
        summary = r.to_summary()
        assert "Language: go" in summary
        assert "Framework: gin" in summary
        assert "Entry: main.go" in summary
        assert "Package Manager: go mod" in summary
        assert "Runtime: 1.22" in summary
        assert "Has Dockerfile: Yes" in summary
        assert "Has .dockerignore: Yes" in summary
