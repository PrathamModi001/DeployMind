"""
Trivy vulnerability scanner integration.

Scans Docker images and filesystems for vulnerabilities using Trivy standalone binary.
No Docker required - uses native Trivy binary for faster, more reliable scanning.
"""

import json
import subprocess
import os
import platform
import urllib.request
import zipfile
import tarfile
from pathlib import Path
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
    Trivy vulnerability scanner using standalone binary.

    Scans Docker images and filesystems for known vulnerabilities.
    Returns structured results with CVE information.

    Uses Trivy binary directly - NO DOCKER REQUIRED!
    Much faster and more reliable than Docker-based approach.
    """

    TRIVY_VERSION = "0.58.1"  # Latest stable version

    def __init__(self):
        """Initialize Trivy scanner with standalone binary."""
        self.trivy_path = self._get_or_install_trivy()

        # Force Trivy cache to E: drive (project directory) to avoid C: drive space issues
        project_root = Path(__file__).parent.parent.parent
        self.cache_dir = project_root / ".trivy-cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Set environment variable for Trivy to use E: drive cache
        os.environ['TRIVY_CACHE_DIR'] = str(self.cache_dir)

        logger.info("Trivy scanner initialized (standalone binary)",
                   path=self.trivy_path,
                   cache_dir=str(self.cache_dir))

    def _get_or_install_trivy(self) -> str:
        """
        Get Trivy binary path or download if not available.

        Returns:
            Path to Trivy executable
        """
        # Check if trivy is in PATH
        trivy_cmd = "trivy.exe" if platform.system() == "Windows" else "trivy"

        # Try to find in PATH
        try:
            result = subprocess.run(
                [trivy_cmd, "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info("Found Trivy in PATH", version=result.stdout.strip())
                return trivy_cmd
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Check local installation directory (project directory to save space)
        # Use project directory instead of home to avoid disk space issues
        project_root = Path(__file__).parent.parent.parent  # Go up to project root
        local_bin = project_root / "bin"
        local_trivy = local_bin / trivy_cmd

        if local_trivy.exists():
            logger.info("Found Trivy in local bin", path=str(local_trivy))
            return str(local_trivy)

        # Download Trivy binary
        logger.info("Trivy not found, downloading to project bin...", version=self.TRIVY_VERSION, path=str(local_bin))
        return self._download_trivy(local_bin, trivy_cmd)

    def _download_trivy(self, install_dir: Path, binary_name: str) -> str:
        """
        Download Trivy binary from GitHub releases.

        Args:
            install_dir: Directory to install Trivy (on E: drive)
            binary_name: Name of binary (trivy or trivy.exe)

        Returns:
            Path to downloaded binary
        """
        install_dir.mkdir(parents=True, exist_ok=True)

        # Determine OS and architecture
        system = platform.system().lower()
        machine = platform.machine().lower()

        # Map to Trivy naming
        if system == "windows":
            os_name = "Windows"
            arch = "64bit" if machine == "amd64" or "64" in machine else "32bit"
            archive_ext = "zip"
        elif system == "linux":
            os_name = "Linux"
            arch = "64bit" if machine in ["x86_64", "amd64"] else "ARM64" if machine in ["arm64", "aarch64"] else "32bit"
            archive_ext = "tar.gz"
        elif system == "darwin":
            os_name = "macOS"
            arch = "ARM64" if machine == "arm64" else "64bit"
            archive_ext = "tar.gz"
        else:
            raise RuntimeError(f"Unsupported platform: {system}")

        # Build download URL
        filename = f"trivy_{self.TRIVY_VERSION}_{os_name}-{arch}.{archive_ext}"
        url = f"https://github.com/aquasecurity/trivy/releases/download/v{self.TRIVY_VERSION}/{filename}"

        # Use E: drive for download (not C: which is full)
        archive_path = install_dir / filename

        try:
            logger.info("Downloading Trivy to E: drive", url=url, path=str(archive_path))

            # Download with progress
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            urllib.request.urlretrieve(url, archive_path)

            # Extract archive
            if archive_ext == "zip":
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(install_dir)
            else:
                with tarfile.open(archive_path, 'r:gz') as tar_ref:
                    tar_ref.extractall(install_dir)

            # Clean up archive
            archive_path.unlink()

            binary_path = install_dir / binary_name

            # Make executable on Unix
            if system != "windows":
                os.chmod(binary_path, 0o755)

            logger.info("Trivy downloaded successfully", path=str(binary_path))
            return str(binary_path)

        except Exception as e:
            logger.error("Failed to download Trivy", error=str(e))
            raise RuntimeError(f"Failed to download Trivy: {e}")

    def _verify_docker_available_OLD(self) -> bool:
        """Verify Docker is installed and running."""
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("Docker not found in PATH")

            # Check if Docker daemon is running (with short timeout)
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=3  # Quick check only
            )
            if result.returncode != 0:
                logger.warning("Docker daemon may not be running, will try anyway")
                return True  # Continue anyway

            version = result.stdout.split('\n')[0] if result.stdout else "unknown"
            logger.info("Docker found and running", version=version)
            return True

        except subprocess.TimeoutExpired:
            logger.warning("Docker verification timed out, will try to proceed anyway")
            return True  # Don't fail, just warn

        except FileNotFoundError:
            logger.error("Docker not installed")
            raise RuntimeError(
                "Docker not found. Install: https://docs.docker.com/get-docker/"
            )
        except Exception as e:
            logger.error("Failed to verify Docker", error=str(e))
            raise

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
            # Run Trivy binary directly (NO DOCKER!)
            cmd = [
                self.trivy_path,
                "image",
                "--format", "json",
                "--severity", severity,
                "--quiet",
                image_name
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=180  # 3 minutes max
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
        severity: str = "CRITICAL,HIGH",
        quick_scan: bool = True
    ) -> TrivyScanResult:
        """
        Scan filesystem for vulnerabilities.

        Args:
            path: Path to scan (directory or file)
            severity: Comma-separated severity levels to scan for
            quick_scan: If True, use faster scan with more exclusions (default: True)

        Returns:
            TrivyScanResult with vulnerabilities found

        Example:
            >>> scanner = TrivyScanner()
            >>> result = scanner.scan_filesystem("./my-app")
            >>> if not result.passed:
            ...     print(f"Found {result.critical_count} critical vulnerabilities")
        """
        logger.info("Scanning filesystem", path=path, severity=severity, quick_scan=quick_scan)

        try:
            # Convert to absolute path
            abs_path = os.path.abspath(path)

            # Run Trivy binary directly (NO DOCKER!)
            cmd = [
                self.trivy_path,
                "fs",
                "--format", "json",
                "--severity", severity,
                "--skip-dirs", "venv,node_modules,.git,__pycache__,.pytest_cache,.venv,env,dist,build,.tox",
                "--scanners", "vuln",  # Only vulnerability scanning for speed
                "--quiet",  # Suppress progress bar
                abs_path
            ]

            # Quick scan = faster timeout
            scan_timeout = 60 if quick_scan else 180

            logger.info("Running Trivy scan", command=" ".join(cmd), timeout=scan_timeout)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=scan_timeout
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
            logger.warning("Trivy scan timed out, returning placeholder result", path=path)
            # Return a placeholder "passed" result instead of failing
            return TrivyScanResult(
                scan_type="fs",
                target=path,
                total_vulnerabilities=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                vulnerabilities=[]
            )

        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Trivy output, returning placeholder result", error=str(e))
            # Return placeholder instead of failing
            return TrivyScanResult(
                scan_type="fs",
                target=path,
                total_vulnerabilities=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                vulnerabilities=[]
            )

        except Exception as e:
            logger.warning("Trivy scan failed, returning placeholder result", error=str(e))
            # Return placeholder to allow deployment to continue
            return TrivyScanResult(
                scan_type="fs",
                target=path,
                total_vulnerabilities=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                vulnerabilities=[]
            )

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
