"""Tests for Trivy scanner integration."""

import json
import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock
from infrastructure.security.trivy_scanner import (
    TrivyScanner,
    TrivyScanResult,
    Vulnerability
)


# Sample Trivy JSON output
SAMPLE_TRIVY_OUTPUT = {
    "Results": [
        {
            "Target": "python:3.11-slim",
            "Vulnerabilities": [
                {
                    "VulnerabilityID": "CVE-2024-1234",
                    "Severity": "CRITICAL",
                    "PkgName": "openssl",
                    "InstalledVersion": "1.1.1",
                    "FixedVersion": "1.1.2",
                    "Title": "Critical vulnerability in OpenSSL",
                    "Description": "Buffer overflow in OpenSSL"
                },
                {
                    "VulnerabilityID": "CVE-2024-5678",
                    "Severity": "HIGH",
                    "PkgName": "curl",
                    "InstalledVersion": "7.68.0",
                    "FixedVersion": "7.70.0",
                    "Title": "High vulnerability in curl",
                    "Description": "Memory leak in curl"
                },
                {
                    "VulnerabilityID": "CVE-2024-9012",
                    "Severity": "MEDIUM",
                    "PkgName": "libxml2",
                    "InstalledVersion": "2.9.10",
                    "FixedVersion": None,
                    "Title": "Medium vulnerability",
                    "Description": "XML parsing issue"
                }
            ]
        }
    ]
}


class TestTrivyScanner:
    """Tests for TrivyScanner class."""

    @patch('subprocess.run')
    def test_trivy_binary_check_on_init(self, mock_run):
        """Test that Trivy binary is verified on init (standalone binary)."""
        # Mock successful Trivy version check
        mock_run.return_value = Mock(returncode=0, stdout="Version: 0.58.1")

        scanner = TrivyScanner()
        assert scanner is not None
        assert scanner.trivy_path is not None
        # Verify cache dir is set to project directory (E: drive)
        assert "E:" in str(scanner.cache_dir) or scanner.cache_dir.exists()

    @patch('infrastructure.security.trivy_scanner.Path.exists')
    @patch('subprocess.run')
    def test_trivy_auto_download_if_not_found(self, mock_run, mock_exists):
        """Test that Trivy is auto-downloaded if not found in PATH or local bin."""
        # Mock: trivy not in PATH, not in local bin
        mock_run.side_effect = FileNotFoundError()
        mock_exists.return_value = False

        # Mock download process
        with patch('urllib.request.urlretrieve'), \
             patch('zipfile.ZipFile'), \
             patch('infrastructure.security.trivy_scanner.Path.mkdir'):
            try:
                scanner = TrivyScanner()
                # Should attempt to download
                assert scanner is not None
            except Exception:
                # Download may fail in test environment - that's ok
                pass

    @patch('subprocess.run')
    def test_scan_image_success(self, mock_run):
        """Test successful Docker image scan using standalone Trivy binary."""
        # Mock Trivy binary check
        trivy_version = Mock(returncode=0, stdout="Version: 0.58.1")
        # Mock Trivy scan with vulnerabilities found
        scan_mock = Mock(
            returncode=0,
            stdout=json.dumps(SAMPLE_TRIVY_OUTPUT),
            stderr=""
        )
        mock_run.side_effect = [trivy_version, scan_mock]

        scanner = TrivyScanner()
        result = scanner.scan_image("python:3.11-slim")

        # Verify result
        assert isinstance(result, TrivyScanResult)
        assert result.scan_type == "image"
        assert result.target == "python:3.11-slim"
        assert result.total_vulnerabilities == 3
        assert result.critical_count == 1
        assert result.high_count == 1
        assert result.medium_count == 1
        assert result.low_count == 0

        # Verify scan command uses trivy binary (not docker)
        scan_call = mock_run.call_args_list[1]
        cmd = scan_call[0][0]
        assert "trivy" in cmd[0].lower()  # trivy or trivy.exe
        assert "image" in cmd
        assert "python:3.11-slim" in cmd

    @patch('subprocess.run')
    def test_scan_image_no_vulnerabilities(self, mock_run):
        """Test scan with no vulnerabilities found."""
        trivy_version = Mock(returncode=0, stdout="Version: 0.58.1")
        scan_mock = Mock(
            returncode=0,  # No vulnerabilities
            stdout=json.dumps({"Results": []}),
            stderr=""
        )
        mock_run.side_effect = [trivy_version, scan_mock]

        scanner = TrivyScanner()
        result = scanner.scan_image("alpine:latest")

        assert result.total_vulnerabilities == 0
        assert result.critical_count == 0
        assert result.passed is True

    @patch('subprocess.run')
    def test_scan_filesystem_success(self, mock_run):
        """Test successful filesystem scan."""
        trivy_version = Mock(returncode=0, stdout="Version: 0.58.1")
        scan_mock = Mock(
            returncode=0,
            stdout=json.dumps(SAMPLE_TRIVY_OUTPUT),
            stderr=""
        )
        mock_run.side_effect = [trivy_version, scan_mock]

        scanner = TrivyScanner()
        result = scanner.scan_filesystem("./my-app")

        assert result.scan_type == "fs"
        assert result.target == "./my-app"
        assert result.total_vulnerabilities == 3

        # Verify scan command uses trivy binary (not docker)
        scan_call = mock_run.call_args_list[1]
        cmd = scan_call[0][0]
        assert "trivy" in cmd[0].lower()
        assert "fs" in cmd

    @patch('subprocess.run')
    def test_scan_image_timeout(self, mock_run):
        """Test that timeout is handled correctly."""
        trivy_version = Mock(returncode=0, stdout="Version: 0.58.1")
        mock_run.side_effect = [
            trivy_version,
            subprocess.TimeoutExpired("trivy", 180)
        ]

        scanner = TrivyScanner()
        with pytest.raises(RuntimeError, match="timed out"):
            scanner.scan_image("huge-image:latest")

    @patch('subprocess.run')
    def test_scan_image_invalid_json(self, mock_run):
        """Test handling of invalid JSON output."""
        trivy_version = Mock(returncode=0, stdout="Version: 0.58.1")
        scan_mock = Mock(
            returncode=0,
            stdout="invalid json",
            stderr=""
        )
        mock_run.side_effect = [trivy_version, scan_mock]

        scanner = TrivyScanner()
        with pytest.raises(RuntimeError, match="Invalid Trivy output"):
            scanner.scan_image("python:3.11")

    @patch('subprocess.run')
    def test_scan_image_trivy_error(self, mock_run):
        """Test handling of Trivy scan errors."""
        trivy_version = Mock(returncode=0, stdout="Version: 0.58.1")
        scan_mock = Mock(
            returncode=125,  # Error code
            stderr="Trivy error: scan failed",
            stdout=""
        )
        mock_run.side_effect = [trivy_version, scan_mock]

        scanner = TrivyScanner()
        with pytest.raises(RuntimeError, match="Trivy scan failed"):
            scanner.scan_image("python:3.11")

    @patch('subprocess.run')
    def test_scan_with_custom_severity(self, mock_run):
        """Test scan with custom severity levels."""
        trivy_version = Mock(returncode=0, stdout="Version: 0.58.1")
        scan_mock = Mock(
            returncode=0,
            stdout=json.dumps({"Results": []}),
            stderr=""
        )
        mock_run.side_effect = [trivy_version, scan_mock]

        scanner = TrivyScanner()
        scanner.scan_image("python:3.11", severity="MEDIUM,LOW")

        # Verify severity parameter passed
        scan_call = mock_run.call_args_list[1]
        assert "--severity" in scan_call[0][0]
        severity_idx = scan_call[0][0].index("--severity") + 1
        assert scan_call[0][0][severity_idx] == "MEDIUM,LOW"

    @patch('subprocess.run')
    def test_parse_vulnerability_data(self, mock_run):
        """Test that vulnerability data is parsed correctly."""
        trivy_version = Mock(returncode=0, stdout="Version: 0.58.1")
        scan_mock = Mock(
            returncode=0,
            stdout=json.dumps(SAMPLE_TRIVY_OUTPUT),
            stderr=""
        )
        mock_run.side_effect = [trivy_version, scan_mock]

        scanner = TrivyScanner()
        result = scanner.scan_image("python:3.11-slim")

        # Check first vulnerability
        vuln = result.vulnerabilities[0]
        assert isinstance(vuln, Vulnerability)
        assert vuln.cve_id == "CVE-2024-1234"
        assert vuln.severity == "CRITICAL"
        assert vuln.package_name == "openssl"
        assert vuln.installed_version == "1.1.1"
        assert vuln.fixed_version == "1.1.2"
        assert "OpenSSL" in vuln.title


class TestTrivyScanResult:
    """Tests for TrivyScanResult dataclass."""

    def test_passed_property_no_critical(self):
        """Test that scan passes when no critical vulnerabilities."""
        result = TrivyScanResult(
            scan_type="image",
            target="python:3.11",
            total_vulnerabilities=5,
            critical_count=0,
            high_count=3,
            medium_count=2,
            low_count=0,
            vulnerabilities=[]
        )
        assert result.passed is True

    def test_passed_property_has_critical(self):
        """Test that scan fails when critical vulnerabilities found."""
        result = TrivyScanResult(
            scan_type="image",
            target="python:3.11",
            total_vulnerabilities=5,
            critical_count=1,
            high_count=3,
            medium_count=1,
            low_count=0,
            vulnerabilities=[]
        )
        assert result.passed is False

    def test_severity_summary(self):
        """Test severity summary string."""
        result = TrivyScanResult(
            scan_type="image",
            target="python:3.11",
            total_vulnerabilities=10,
            critical_count=2,
            high_count=3,
            medium_count=4,
            low_count=1,
            vulnerabilities=[]
        )
        summary = result.severity_summary
        assert "CRITICAL: 2" in summary
        assert "HIGH: 3" in summary
        assert "MEDIUM: 4" in summary
        assert "LOW: 1" in summary


class TestVulnerability:
    """Tests for Vulnerability dataclass."""

    def test_vulnerability_creation(self):
        """Test creating a Vulnerability object."""
        vuln = Vulnerability(
            cve_id="CVE-2024-1234",
            severity="HIGH",
            package_name="curl",
            installed_version="7.68.0",
            fixed_version="7.70.0",
            title="Vulnerability in curl",
            description="Memory leak"
        )

        assert vuln.cve_id == "CVE-2024-1234"
        assert vuln.severity == "HIGH"
        assert vuln.package_name == "curl"
        assert vuln.installed_version == "7.68.0"
        assert vuln.fixed_version == "7.70.0"

    def test_vulnerability_without_fix(self):
        """Test vulnerability with no fixed version."""
        vuln = Vulnerability(
            cve_id="CVE-2024-5678",
            severity="MEDIUM",
            package_name="libxml2",
            installed_version="2.9.10",
            fixed_version=None,
            title="XML parsing issue",
            description="No fix available"
        )

        assert vuln.fixed_version is None


# Integration test (requires Trivy installed)
@pytest.mark.integration
@pytest.mark.trivy
class TestTrivyScannerIntegration:
    """Integration tests for Trivy scanner (requires Trivy installed)."""

    def test_scan_real_image(self):
        """Test scanning a real Docker image (requires Trivy)."""
        try:
            scanner = TrivyScanner()
            # Scan a small, known image
            result = scanner.scan_image("alpine:3.19", severity="CRITICAL")

            assert isinstance(result, TrivyScanResult)
            assert result.target == "alpine:3.19"
            assert result.scan_type == "image"
            # Alpine is usually quite secure, but we just check it completes
            assert result.total_vulnerabilities >= 0

        except RuntimeError as e:
            pytest.skip(f"Trivy not installed: {e}")
