"""
Download and setup Trivy scanner.

Trivy is too large (200+ MB) to commit to GitHub.
This script downloads the latest Trivy release.
"""

import os
import sys
import urllib.request
import zipfile
import platform


def get_trivy_url():
    """Get Trivy download URL based on platform."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Trivy version
    version = "0.48.3"

    if system == "windows":
        return f"https://github.com/aquasecurity/trivy/releases/download/v{version}/trivy_{version}_windows-64bit.zip"
    elif system == "darwin":  # macOS
        if "arm" in machine or "aarch64" in machine:
            return f"https://github.com/aquasecurity/trivy/releases/download/v{version}/trivy_{version}_macOS-ARM64.tar.gz"
        else:
            return f"https://github.com/aquasecurity/trivy/releases/download/v{version}/trivy_{version}_macOS-64bit.tar.gz"
    else:  # Linux
        if "arm" in machine or "aarch64" in machine:
            return f"https://github.com/aquasecurity/trivy/releases/download/v{version}/trivy_{version}_Linux-ARM64.tar.gz"
        else:
            return f"https://github.com/aquasecurity/trivy/releases/download/v{version}/trivy_{version}_Linux-64bit.tar.gz"


def download_trivy():
    """Download and extract Trivy."""
    # Create tools directory
    tools_dir = os.path.join(os.path.dirname(__file__), "..", "tools")
    os.makedirs(tools_dir, exist_ok=True)

    # Check if already downloaded
    trivy_path = os.path.join(tools_dir, "trivy.exe" if platform.system() == "Windows" else "trivy")
    if os.path.exists(trivy_path):
        print(f"✓ Trivy already exists at: {trivy_path}")
        return trivy_path

    print("Downloading Trivy scanner...")
    print("This may take a few minutes (200+ MB download)")

    url = get_trivy_url()
    filename = url.split("/")[-1]
    download_path = os.path.join(tools_dir, filename)

    # Download
    try:
        print(f"Downloading from: {url}")
        urllib.request.urlretrieve(url, download_path)
        print(f"✓ Downloaded to: {download_path}")
    except Exception as e:
        print(f"✗ Download failed: {e}")
        sys.exit(1)

    # Extract
    try:
        print("Extracting...")
        if filename.endswith(".zip"):
            with zipfile.ZipFile(download_path, "r") as zip_ref:
                zip_ref.extractall(tools_dir)
        else:  # tar.gz
            import tarfile
            with tarfile.open(download_path, "r:gz") as tar_ref:
                tar_ref.extractall(tools_dir)

        print(f"✓ Extracted to: {tools_dir}")

        # Make executable on Unix
        if platform.system() != "Windows":
            os.chmod(trivy_path, 0o755)

        # Remove archive
        os.remove(download_path)
        print(f"✓ Cleaned up archive")

    except Exception as e:
        print(f"✗ Extraction failed: {e}")
        sys.exit(1)

    print(f"\n✓ Trivy setup complete: {trivy_path}")
    return trivy_path


def main():
    """Main function."""
    print("=" * 60)
    print(" Trivy Scanner Setup")
    print("=" * 60)
    print()

    trivy_path = download_trivy()

    print()
    print("=" * 60)
    print(" Setup Complete")
    print("=" * 60)
    print()
    print("Trivy is now available at:")
    print(f"  {trivy_path}")
    print()
    print("You can now run security scans!")
    print()


if __name__ == "__main__":
    main()
