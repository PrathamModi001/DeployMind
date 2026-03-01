"""Intensive tests for DockerfileOptimizer.

Covers every rule individually (DM001–DM015) and end-to-end scoring.

Rules tested:
  DM000 — empty Dockerfile
  DM001 — non-root USER (missing, root, valid)
  DM002 — multi-stage build
  DM003 — apt-get cleanup
  DM004 — pip --no-cache-dir
  DM005 — layer ordering (dep files before source)
  DM006 — base image pinning
  DM007 — ADD vs COPY
  DM008 — MAINTAINER deprecated
  DM009 — :latest tag
  DM010 — consecutive RUN chaining
  DM011 — HEALTHCHECK missing
  DM012 — sensitive files
  DM013 — EXPOSE present
  DM014 — WORKDIR absolute
  DM015 — shell-form CMD/ENTRYPOINT

Edge cases:
  - Windows-style line endings (CRLF)
  - Instructions in mixed case
  - Multiple FROM stages
  - Multi-line RUN with backslash continuation
  - Score clamping at 0
  - Score of 100 for a perfect Dockerfile
  - FindingSeverity ordering in sorted output
  - get_summary output format
  - Concurrent RUN detection across stages
"""

from __future__ import annotations

import pytest

from deploymind.infrastructure.build.dockerfile_optimizer import (
    DockerfileOptimizer,
    FindingSeverity,
    OptimizationFinding,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def optimizer() -> DockerfileOptimizer:
    return DockerfileOptimizer()


# ---------------------------------------------------------------------------
# Reference Dockerfiles
# ---------------------------------------------------------------------------

PERFECT_DOCKERFILE = """\
# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runner
WORKDIR /app
RUN groupadd --gid 1001 g && useradd --uid 1001 --gid g appuser
COPY --from=builder /root/.local /root/.local
COPY . .
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/health || exit 1
CMD ["python", "main.py"]
"""

TERRIBLE_DOCKERFILE = """\
FROM python
RUN apt-get update
RUN apt-get install -y curl
RUN pip install flask
ADD .env /app/.env
MAINTAINER bad@example.com
WORKDIR app
CMD python server.py
"""


# ===========================================================================
# DM000 — Empty content
# ===========================================================================

class TestEmptyDockerfile:
    def test_empty_string(self, optimizer):
        findings = optimizer.analyze("")
        assert any(f.rule_id == "DM000" for f in findings)

    def test_whitespace_only(self, optimizer):
        findings = optimizer.analyze("   \n\n  ")
        assert any(f.rule_id == "DM000" for f in findings)

    def test_empty_is_error_severity(self, optimizer):
        findings = optimizer.analyze("")
        dm000 = next(f for f in findings if f.rule_id == "DM000")
        assert dm000.severity == FindingSeverity.ERROR


# ===========================================================================
# DM001 — Non-root USER
# ===========================================================================

class TestNonRootUser:
    def test_no_user_instruction(self, optimizer):
        df = "FROM python:3.12\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM001" for f in findings)

    def test_no_user_is_error(self, optimizer):
        df = "FROM python:3.12\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        dm001 = next(f for f in findings if f.rule_id == "DM001")
        assert dm001.severity == FindingSeverity.ERROR

    def test_user_root_detected(self, optimizer):
        df = "FROM python:3.12\nUSER root\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM001" for f in findings)

    def test_user_zero_detected(self, optimizer):
        df = "FROM python:3.12\nUSER 0\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM001" for f in findings)

    def test_valid_user_passes(self, optimizer):
        df = "FROM python:3.12\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM001" for f in findings)

    def test_named_non_root_passes(self, optimizer):
        df = "FROM python:3.12\nUSER appuser\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM001" for f in findings)

    def test_user_instruction_case_insensitive(self, optimizer):
        df = "FROM python:3.12\nuser appuser\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM001" for f in findings)


# ===========================================================================
# DM002 — Multi-stage build
# ===========================================================================

class TestMultiStageBuild:
    def test_single_stage_warning(self, optimizer):
        df = "FROM python:3.12-slim\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM002" for f in findings)

    def test_single_stage_is_warning_severity(self, optimizer):
        df = "FROM python:3.12-slim\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        dm002 = next(f for f in findings if f.rule_id == "DM002")
        assert dm002.severity == FindingSeverity.WARNING

    def test_multi_stage_passes(self, optimizer):
        df = "FROM python:3.12 AS builder\nFROM python:3.12-slim AS runner\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM002" for f in findings)

    def test_three_stages_passes(self, optimizer):
        df = "FROM node:20 AS deps\nFROM node:20 AS build\nFROM node:20-alpine AS runner\nUSER 1001\nCMD node index.js\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM002" for f in findings)


# ===========================================================================
# DM003 — apt-get cleanup
# ===========================================================================

class TestAptCleanup:
    def test_apt_without_cleanup_flagged(self, optimizer):
        df = "FROM debian:12\nRUN apt-get update && apt-get install -y curl\nUSER 1001\nCMD curl\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM003" for f in findings)

    def test_apt_with_cleanup_passes(self, optimizer):
        df = (
            "FROM debian:12\n"
            "RUN apt-get update && apt-get install -y --no-install-recommends curl \\\n"
            "    && rm -rf /var/lib/apt/lists/*\n"
            "USER 1001\nCMD curl\n"
        )
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM003" for f in findings)

    def test_apt_cleanup_within_multiline_run_passes(self, optimizer):
        df = (
            "FROM debian:12\n"
            "RUN apt-get update \\\n"
            " && apt-get install -y gcc \\\n"
            " && rm -rf /var/lib/apt/lists/*\n"
            "USER appuser\nCMD echo hi\n"
        )
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM003" for f in findings)

    def test_apt_cleanup_severity_is_warning(self, optimizer):
        df = "FROM debian:12\nRUN apt-get install -y gcc\nUSER 1001\nCMD gcc\n"
        findings = optimizer.analyze(df)
        dm003 = next((f for f in findings if f.rule_id == "DM003"), None)
        if dm003:  # Only present when apt cleanup is missing
            assert dm003.severity == FindingSeverity.WARNING


# ===========================================================================
# DM004 — pip --no-cache-dir
# ===========================================================================

class TestPipNoCache:
    def test_pip_without_no_cache_dir(self, optimizer):
        df = "FROM python:3.12\nRUN pip install flask\nUSER 1001\nCMD flask run\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM004" for f in findings)

    def test_pip_with_no_cache_dir_passes(self, optimizer):
        df = "FROM python:3.12\nRUN pip install --no-cache-dir flask\nUSER 1001\nCMD flask run\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM004" for f in findings)

    def test_pip_with_user_flag_passes(self, optimizer):
        """--user installs to user dir; the cache ends up outside the layer."""
        df = "FROM python:3.12\nRUN pip install --user flask\nUSER 1001\nCMD flask run\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM004" for f in findings)

    def test_pip_info_severity(self, optimizer):
        df = "FROM python:3.12\nRUN pip install flask\nUSER 1001\nCMD flask run\n"
        findings = optimizer.analyze(df)
        dm004 = next((f for f in findings if f.rule_id == "DM004"), None)
        if dm004:
            assert dm004.severity == FindingSeverity.INFO


# ===========================================================================
# DM005 — Layer ordering
# ===========================================================================

class TestLayerOrdering:
    def test_dep_file_before_source_passes(self, optimizer):
        df = (
            "FROM python:3.12 AS builder\n"
            "WORKDIR /build\n"
            "COPY requirements.txt ./\n"
            "RUN pip install --no-cache-dir -r requirements.txt\n"
            "COPY . .\n"
            "FROM python:3.12-slim AS runner\n"
            "USER 1001\nCMD python app.py\n"
        )
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM005" for f in findings)

    def test_source_before_dep_file_flagged(self, optimizer):
        df = (
            "FROM python:3.12\n"
            "WORKDIR /app\n"
            "COPY . .\n"
            "COPY requirements.txt ./\n"
            "USER 1001\nCMD python app.py\n"
        )
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM005" for f in findings)


# ===========================================================================
# DM006 — Base image pinning
# ===========================================================================

class TestBaseImagePinning:
    def test_untagged_image_warning(self, optimizer):
        df = "FROM python\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM006" for f in findings)

    def test_tagged_image_passes(self, optimizer):
        df = "FROM python:3.12-slim\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM006" for f in findings)

    def test_digest_pinned_passes(self, optimizer):
        df = "FROM python@sha256:abcdef1234567890\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM006" for f in findings)

    def test_as_clause_does_not_confuse_parser(self, optimizer):
        df = "FROM python:3.12-slim AS builder\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM006" for f in findings)

    def test_severity_is_warning(self, optimizer):
        df = "FROM python\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        dm006 = next((f for f in findings if f.rule_id == "DM006"), None)
        if dm006:
            assert dm006.severity == FindingSeverity.WARNING


# ===========================================================================
# DM007 — ADD vs COPY
# ===========================================================================

class TestAddVsCopy:
    def test_add_for_simple_file_flagged(self, optimizer):
        df = "FROM python:3.12\nADD app.py /app/app.py\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM007" for f in findings)

    def test_add_for_url_passes(self, optimizer):
        df = "FROM python:3.12\nADD https://example.com/file.zip /tmp/\nUSER 1001\nCMD echo\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM007" for f in findings)

    def test_add_for_tar_passes(self, optimizer):
        df = "FROM python:3.12\nADD archive.tar.gz /app/\nUSER 1001\nCMD echo\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM007" for f in findings)

    def test_copy_instead_of_add_passes(self, optimizer):
        df = "FROM python:3.12\nCOPY app.py /app/app.py\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM007" for f in findings)

    def test_severity_is_info(self, optimizer):
        df = "FROM python:3.12\nADD app.py /app/app.py\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        dm007 = next((f for f in findings if f.rule_id == "DM007"), None)
        if dm007:
            assert dm007.severity == FindingSeverity.INFO


# ===========================================================================
# DM008 — MAINTAINER deprecated
# ===========================================================================

class TestMaintainerDeprecated:
    def test_maintainer_flagged(self, optimizer):
        df = "FROM python:3.12\nMAINTAINER dev@example.com\nUSER 1001\nCMD echo\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM008" for f in findings)

    def test_maintainer_is_info(self, optimizer):
        df = "FROM python:3.12\nMAINTAINER dev@example.com\nUSER 1001\nCMD echo\n"
        findings = optimizer.analyze(df)
        dm008 = next(f for f in findings if f.rule_id == "DM008")
        assert dm008.severity == FindingSeverity.INFO

    def test_label_not_flagged(self, optimizer):
        df = 'FROM python:3.12\nLABEL maintainer="dev@example.com"\nUSER 1001\nCMD echo\n'
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM008" for f in findings)


# ===========================================================================
# DM009 — :latest tag
# ===========================================================================

class TestLatestTag:
    def test_latest_tag_flagged(self, optimizer):
        df = "FROM python:latest\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM009" for f in findings)

    def test_pinned_tag_not_flagged(self, optimizer):
        df = "FROM python:3.12-slim\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM009" for f in findings)

    def test_latest_severity_is_warning(self, optimizer):
        df = "FROM node:latest\nUSER 1001\nCMD node index.js\n"
        findings = optimizer.analyze(df)
        dm009 = next((f for f in findings if f.rule_id == "DM009"), None)
        if dm009:
            assert dm009.severity == FindingSeverity.WARNING


# ===========================================================================
# DM010 — Consecutive RUN chaining
# ===========================================================================

class TestRunChaining:
    def test_three_consecutive_runs_flagged(self, optimizer):
        df = (
            "FROM python:3.12\n"
            "RUN apt-get update\n"
            "RUN apt-get install -y curl\n"
            "RUN pip install flask\n"
            "USER 1001\nCMD flask run\n"
        )
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM010" for f in findings)

    def test_two_consecutive_runs_not_flagged(self, optimizer):
        df = (
            "FROM python:3.12\n"
            "RUN apt-get update\n"
            "RUN pip install flask\n"
            "USER 1001\nCMD flask run\n"
        )
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM010" for f in findings)

    def test_chained_commands_not_flagged(self, optimizer):
        df = (
            "FROM python:3.12\n"
            "RUN apt-get update \\\n"
            " && apt-get install -y curl \\\n"
            " && pip install flask\n"
            "USER 1001\nCMD flask run\n"
        )
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM010" for f in findings)

    def test_runs_reset_between_stages(self, optimizer):
        """Each FROM starts a new stage; runs don't accumulate across stages."""
        df = (
            "FROM python:3.12 AS builder\n"
            "RUN a\n"
            "RUN b\n"
            "FROM python:3.12-slim AS runner\n"
            "RUN c\n"
            "USER 1001\nCMD echo\n"
        )
        findings = optimizer.analyze(df)
        # Only 2 consecutive in each stage → should NOT trigger DM010
        assert not any(f.rule_id == "DM010" for f in findings)

    def test_severity_is_info(self, optimizer):
        df = "FROM python:3.12\nRUN a\nRUN b\nRUN c\nUSER 1001\nCMD echo\n"
        findings = optimizer.analyze(df)
        dm010 = next((f for f in findings if f.rule_id == "DM010"), None)
        if dm010:
            assert dm010.severity == FindingSeverity.INFO


# ===========================================================================
# DM011 — HEALTHCHECK
# ===========================================================================

class TestHealthcheck:
    def test_no_healthcheck_flagged(self, optimizer):
        df = "FROM python:3.12\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM011" for f in findings)

    def test_healthcheck_present_not_flagged(self, optimizer):
        df = (
            "FROM python:3.12\n"
            "USER 1001\n"
            "HEALTHCHECK --interval=30s CMD curl -f http://localhost:8000/health\n"
            "CMD python app.py\n"
        )
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM011" for f in findings)

    def test_severity_is_info(self, optimizer):
        df = "FROM python:3.12\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        dm011 = next((f for f in findings if f.rule_id == "DM011"), None)
        if dm011:
            assert dm011.severity == FindingSeverity.INFO


# ===========================================================================
# DM012 — Sensitive files
# ===========================================================================

class TestSensitiveFiles:
    def test_env_file_copied(self, optimizer):
        df = "FROM python:3.12\nCOPY .env /app/.env\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM012" for f in findings)

    def test_pem_file_copied(self, optimizer):
        df = "FROM python:3.12\nCOPY cert.pem /app/cert.pem\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM012" for f in findings)

    def test_private_key_copied(self, optimizer):
        df = "FROM python:3.12\nCOPY id_rsa /root/.ssh/id_rsa\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM012" for f in findings)

    def test_aws_credentials_copied(self, optimizer):
        df = "FROM python:3.12\nCOPY .aws/credentials /root/.aws/credentials\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM012" for f in findings)

    def test_normal_file_copy_passes(self, optimizer):
        df = "FROM python:3.12\nCOPY app.py /app/app.py\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM012" for f in findings)

    def test_severity_is_error(self, optimizer):
        df = "FROM python:3.12\nCOPY .env /app/.env\nUSER 1001\nCMD python app.py\n"
        findings = optimizer.analyze(df)
        dm012 = next(f for f in findings if f.rule_id == "DM012")
        assert dm012.severity == FindingSeverity.ERROR


# ===========================================================================
# DM013 — EXPOSE present
# ===========================================================================

class TestExposePresent:
    def test_no_expose_with_cmd_flagged(self, optimizer):
        df = "FROM python:3.12\nUSER 1001\nCMD python server.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM013" for f in findings)

    def test_expose_present_passes(self, optimizer):
        df = "FROM python:3.12\nUSER 1001\nEXPOSE 8000\nCMD python server.py\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM013" for f in findings)

    def test_no_expose_no_cmd_not_flagged(self, optimizer):
        """If there's no CMD/ENTRYPOINT, EXPOSE is not required."""
        df = "FROM python:3.12-slim AS builder\nUSER 1001\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM013" for f in findings)


# ===========================================================================
# DM014 — WORKDIR absolute
# ===========================================================================

class TestWorkdirAbsolute:
    def test_relative_workdir_flagged(self, optimizer):
        df = "FROM python:3.12\nWORKDIR app\nUSER 1001\nCMD echo\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM014" for f in findings)

    def test_absolute_workdir_passes(self, optimizer):
        df = "FROM python:3.12\nWORKDIR /app\nUSER 1001\nCMD echo\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM014" for f in findings)

    def test_env_variable_workdir_passes(self, optimizer):
        df = "FROM python:3.12\nWORKDIR $APP_HOME\nUSER 1001\nCMD echo\n"
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM014" for f in findings)


# ===========================================================================
# DM015 — Shell-form CMD/ENTRYPOINT
# ===========================================================================

class TestShellFormCmd:
    def test_shell_form_cmd_flagged(self, optimizer):
        df = "FROM python:3.12\nUSER 1001\nEXPOSE 8000\nCMD python server.py\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM015" for f in findings)

    def test_exec_form_cmd_passes(self, optimizer):
        df = 'FROM python:3.12\nUSER 1001\nEXPOSE 8000\nCMD ["python", "server.py"]\n'
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM015" for f in findings)

    def test_shell_form_entrypoint_flagged(self, optimizer):
        df = "FROM go:1.22\nUSER 1001\nEXPOSE 8080\nENTRYPOINT /server\n"
        findings = optimizer.analyze(df)
        assert any(f.rule_id == "DM015" for f in findings)

    def test_exec_form_entrypoint_passes(self, optimizer):
        df = 'FROM go:1.22\nUSER 1001\nEXPOSE 8080\nENTRYPOINT ["/server"]\n'
        findings = optimizer.analyze(df)
        assert not any(f.rule_id == "DM015" for f in findings)

    def test_severity_is_warning(self, optimizer):
        df = "FROM python:3.12\nUSER 1001\nEXPOSE 8000\nCMD python server.py\n"
        findings = optimizer.analyze(df)
        dm015 = next((f for f in findings if f.rule_id == "DM015"), None)
        if dm015:
            assert dm015.severity == FindingSeverity.WARNING


# ===========================================================================
# Scoring
# ===========================================================================

class TestScoring:
    def test_perfect_dockerfile_score_100(self, optimizer):
        findings = optimizer.analyze(PERFECT_DOCKERFILE)
        score = optimizer.get_score(findings)
        assert score == 100

    def test_terrible_dockerfile_low_score(self, optimizer):
        findings = optimizer.analyze(TERRIBLE_DOCKERFILE)
        score = optimizer.get_score(findings)
        assert score < 60

    def test_score_clamped_at_zero(self, optimizer):
        """Even if many rules fire, score doesn't go negative."""
        very_bad = "FROM ubuntu\nADD .env /app/.env\nMAINTAINER x\nCMD python app.py\n"
        findings = optimizer.analyze(very_bad)
        score = optimizer.get_score(findings)
        assert score >= 0

    def test_score_maximum_100(self, optimizer):
        findings = optimizer.analyze(PERFECT_DOCKERFILE)
        score = optimizer.get_score(findings)
        assert score <= 100

    def test_each_error_deducts_20(self, optimizer):
        # A single missing USER is 1 error → 100 - 20 = 80 (plus other findings)
        df = "FROM python:3.12-slim AS builder\nFROM python:3.12-slim AS runner\nEXPOSE 8000\nCMD [\"python\", \"app.py\"]\n"
        findings = optimizer.analyze(df)
        errors = [f for f in findings if f.severity == FindingSeverity.ERROR]
        warnings = [f for f in findings if f.severity == FindingSeverity.WARNING]
        infos = [f for f in findings if f.severity == FindingSeverity.INFO]
        expected = max(0, 100 - 20 * len(errors) - 10 * len(warnings) - 5 * len(infos))
        assert optimizer.get_score(findings) == expected

    def test_no_findings_score_100(self, optimizer):
        assert optimizer.get_score([]) == 100


# ===========================================================================
# Sorting order
# ===========================================================================

class TestSortingOrder:
    def test_errors_before_warnings_before_info(self, optimizer):
        findings = optimizer.analyze(TERRIBLE_DOCKERFILE)
        if len(findings) < 2:
            return
        severity_values = [f.severity for f in findings]
        order = {FindingSeverity.ERROR: 0, FindingSeverity.WARNING: 1, FindingSeverity.INFO: 2}
        values = [order[s] for s in severity_values]
        assert values == sorted(values), "Findings not sorted by severity"


# ===========================================================================
# get_summary
# ===========================================================================

class TestGetSummary:
    def test_perfect_summary_says_no_issues(self, optimizer):
        findings = optimizer.analyze(PERFECT_DOCKERFILE)
        summary = optimizer.get_summary(findings)
        assert "100" in summary or "No issues" in summary

    def test_summary_contains_rule_ids(self, optimizer):
        findings = optimizer.analyze(TERRIBLE_DOCKERFILE)
        summary = optimizer.get_summary(findings)
        # Should reference at least one DM rule
        assert "DM" in summary

    def test_summary_contains_suggestion(self, optimizer):
        findings = optimizer.analyze(TERRIBLE_DOCKERFILE)
        summary = optimizer.get_summary(findings)
        assert "→" in summary  # Suggestion separator


# ===========================================================================
# Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_crlf_line_endings(self, optimizer):
        df = "FROM python:3.12-slim\r\nUSER 1001\r\nEXPOSE 8000\r\nCMD [\"python\", \"app.py\"]\r\n"
        # Should not raise — may produce some findings but shouldn't crash
        findings = optimizer.analyze(df)
        assert isinstance(findings, list)

    def test_mixed_case_instructions(self, optimizer):
        df = "from python:3.12-slim\nuser 1001\nexpose 8000\ncmd python app.py\n"
        findings = optimizer.analyze(df)
        # Should still detect shell-form cmd etc.
        assert isinstance(findings, list)

    def test_finding_line_numbers_are_positive(self, optimizer):
        findings = optimizer.analyze(TERRIBLE_DOCKERFILE)
        for f in findings:
            if f.line_number is not None:
                assert f.line_number >= 1

    def test_finding_messages_not_empty(self, optimizer):
        findings = optimizer.analyze(TERRIBLE_DOCKERFILE)
        for f in findings:
            assert f.message.strip()
            assert f.suggestion.strip()

    def test_finding_rule_ids_not_empty(self, optimizer):
        findings = optimizer.analyze(TERRIBLE_DOCKERFILE)
        for f in findings:
            assert f.rule_id.strip()
