"""
Trivy vulnerability scanner integration.

Scans Docker images and filesystems for vulnerabilities using Trivy.
"""

import json
import subprocess
from dataclasses import dataclass
from typing import Optional
from shared.secure_logging import get_logger

logger = get_logger(__name__)


@dataclass
class Vulnerability:
    """Single vulnerability from Trivy scan."""

    cve_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN
    package_name: str
    installed_version: str
    fixed_version: Optional[str]
    title: str
    description: str


@dataclass
class TrivyScanResult:
    """Complete Trivy scan result."""

    scan_type: str  # "image" or "fs"
    target: str  # Image name or file path
    total_vulnerabilities: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    vulnerabilities: list[Vulnerability]

    @property
    def passed(self) -> bool:
        """Scan passes if no CRITICAL vulnerabilities."""
        return self.critical_count == 0

    @property
    def severity_summary(self) -> str:
        """Human-readable severity summary."""
        return (
            f"CRITICAL: {self.critical_count}, "
            f"HIGH: {self.high_count}, "
            f"MEDIUM: {self.medium_count}, "
            f"LOW: {self.low_count}"
        )


class TrivyScanner:
    """
    Trivy vulnerability scanner.

    Scans Docker images and filesystems for known vulnerabilities.
    Returns structured results with CVE information.
    """

    def __init__(self, trivy_path: str = "trivy"):
        """
        Initialize Trivy scanner.

        Args:
            trivy_path: Path to Trivy binary (default: "trivy" in PATH)
        """
        self.trivy_path = trivy_path
        self._verify_trivy_installed()

    def _verify_trivy_installed(self) -> bool:
        """Verify Trivy is installed and accessible."""
        try:
            result = subprocess.run(
                [self.trivy_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info("Trivy found", version=version)
                return True
            else:
                logger.warning("Trivy not found in PATH")
                return False
        except FileNotFoundError:
            logger.error("Trivy not installed")
            raise RuntimeError(
                "Trivy not found. Install: https://aquasecurity.github.io/trivy/"
            )
        except Exception as e:
            logger.error("Failed to verify Trivy", error=str(e))
            return False

    def scan_image(
        self,
        image_name: str,
        severity: str = "CRITICAL,HIGH"
    ) -> TrivyScanResult:
        """
        Scan Docker image for vulnerabilities.

        Args:
            image_name: Docker image name (e.g., "python:3.11-slim")
            severity: Comma-separated severity levels to scan for

        Returns:
            TrivyScanResult with vulnerabilities found

        Example:
            >>> scanner = TrivyScanner()
            >>> result = scanner.scan_image("python:3.11-slim")
            >>> print(result.severity_summary)
        """
        logger.info("Scanning Docker image", image=image_name, severity=severity)

        try:
            # Run Trivy scan with JSON output
            cmd = [
                self.trivy_path,
                "image",
                "--format", "json",
                "--severity", severity,
                "--no-progress",
                image_name
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes max
            )

            if result.returncode != 0 and result.returncode != 1:
                # returncode 1 means vulnerabilities found (expected)
                # anything else is an error
                logger.error(
                    "Trivy scan failed",
                    returncode=result.returncode,
                    stderr=result.stderr
                )
                raise RuntimeError(f"Trivy scan failed: {result.stderr}")

            # Parse JSON output
            scan_data = json.loads(result.stdout)
            return self._parse_scan_result(scan_data, "image", image_name)

        except subprocess.TimeoutExpired:
            logger.error("Trivy scan timed out", image=image_name)
            raise RuntimeError(f"Trivy scan timed out after 5 minutes")

        except json.JSONDecodeError as e:
            logger.error("Failed to parse Trivy output", error=str(e))
            raise RuntimeError(f"Invalid Trivy output: {e}")

        except Exception as e:
            logger.exception("Unexpected error during image scan", error=str(e))
            raise

    def scan_filesystem(
        self,
        path: str,
        severity: str = "CRITICAL,HIGH"
    ) -> TrivyScanResult:
        """
        Scan filesystem for vulnerabilities.

        Args:
            path: Path to scan (directory or file)
            severity: Comma-separated severity levels to scan for

        Returns:
            TrivyScanResult with vulnerabilities found

        Example:
            >>> scanner = TrivyScanner()
            >>> result = scanner.scan_filesystem("./my-app")
            >>> if not result.passed:
            ...     print(f"Found {result.critical_count} critical vulnerabilities")
        """
        logger.info("Scanning filesystem", path=path, severity=severity)

        try:
            cmd = [
                self.trivy_path,
                "fs",
                "--format", "json",
                "--severity", severity,
                "--no-progress",
                path
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300
            )

            if result.returncode != 0 and result.returncode != 1:
                logger.error(
                    "Trivy scan failed",
                    returncode=result.returncode,
                    stderr=result.stderr
                )
                raise RuntimeError(f"Trivy scan failed: {result.stderr}")

            scan_data = json.loads(result.stdout)
            return self._parse_scan_result(scan_data, "fs", path)

        except subprocess.TimeoutExpired:
            logger.error("Trivy scan timed out", path=path)
            raise RuntimeError(f"Trivy scan timed out after 5 minutes")

        except json.JSONDecodeError as e:
            logger.error("Failed to parse Trivy output", error=str(e))
            raise RuntimeError(f"Invalid Trivy output: {e}")

        except Exception as e:
            logger.exception("Unexpected error during filesystem scan", error=str(e))
            raise

    def _parse_scan_result(
        self,
        scan_data: dict,
        scan_type: str,
        target: str
    ) -> TrivyScanResult:
        """
        Parse Trivy JSON output into structured result.

        Args:
            scan_data: Raw JSON from Trivy
            scan_type: "image" or "fs"
            target: Image name or file path

        Returns:
            Structured TrivyScanResult
        """
        vulnerabilities = []
        critical_count = 0
        high_count = 0
        medium_count = 0
        low_count = 0

        # Trivy output structure: {"Results": [...]}
        results = scan_data.get("Results", [])

        for result in results:
            vulns = result.get("Vulnerabilities", [])

            for vuln in vulns:
                severity = vuln.get("Severity", "UNKNOWN")

                # Count by severity
                if severity == "CRITICAL":
                    critical_count += 1
                elif severity == "HIGH":
                    high_count += 1
                elif severity == "MEDIUM":
                    medium_count += 1
                elif severity == "LOW":
                    low_count += 1

                # Create Vulnerability object
                vulnerability = Vulnerability(
                    cve_id=vuln.get("VulnerabilityID", "UNKNOWN"),
                    severity=severity,
                    package_name=vuln.get("PkgName", "unknown"),
                    installed_version=vuln.get("InstalledVersion", "unknown"),
                    fixed_version=vuln.get("FixedVersion"),
                    title=vuln.get("Title", "No title"),
                    description=vuln.get("Description", "No description")
                )
                vulnerabilities.append(vulnerability)

        total = critical_count + high_count + medium_count + low_count

        logger.info(
            "Scan complete",
            target=target,
            total=total,
            critical=critical_count,
            high=high_count
        )

        return TrivyScanResult(
            scan_type=scan_type,
            target=target,
            total_vulnerabilities=total,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            vulnerabilities=vulnerabilities
        )
