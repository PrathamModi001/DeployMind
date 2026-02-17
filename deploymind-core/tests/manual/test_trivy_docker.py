"""
Test Trivy Scanner (Docker-based).

This test verifies that TrivyScanner works correctly using Docker.
"""

import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, project_root)

from deploymind.infrastructure.security.trivy_scanner import TrivyScanner


def test_trivy_scanner():
    """Test Docker-based Trivy scanner."""
    print("\n" + "="*60)
    print("TEST: Trivy Scanner (Docker-based)")
    print("="*60)

    try:
        # Initialize scanner
        print("\n[1/4] Initializing Trivy scanner...")
        scanner = TrivyScanner()
        print("[PASS] Scanner initialized")

        # Scan a small image
        print("\n[2/4] Scanning alpine:3.19 (small image)...")
        print("NOTE: First run will pull aquasec/trivy image (~200MB)")
        result = scanner.scan_image("alpine:3.19", severity="CRITICAL,HIGH")

        print(f"[PASS] Scan complete: {result.total_vulnerabilities} vulnerabilities found")
        print(f"       {result.severity_summary}")

        # Verify result structure
        print("\n[3/4] Verifying result structure...")
        assert result.scan_type == "image"
        assert result.target == "alpine:3.19"
        assert result.total_vulnerabilities >= 0
        assert hasattr(result, 'passed')
        print("[PASS] Result structure valid")

        # Test filesystem scan
        print("\n[4/4] Testing filesystem scan...")
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a simple test file
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "w") as f:
                f.write("test")

            result_fs = scanner.scan_filesystem(tmpdir, severity="CRITICAL,HIGH")
            print(f"[PASS] Filesystem scan complete: {result_fs.total_vulnerabilities} vulnerabilities")

        print("\n" + "="*60)
        print("SUCCESS: All tests passed!")
        print("="*60)
        return True

    except RuntimeError as e:
        print(f"\n[FAIL] {e}")
        print("\nTroubleshooting:")
        print("1. Ensure Docker is installed:")
        print("   docker --version")
        print("\n2. Ensure Docker daemon is running:")
        print("   docker info")
        print("\n3. Test Trivy manually:")
        print("   docker run --rm aquasec/trivy --version")
        return False

    except Exception as e:
        print(f"\n[FAIL] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "="*60)
    print(" Trivy Scanner Test")
    print("="*60)

    result = test_trivy_scanner()

    print("\n" + "="*60)
    print(" Test Result")
    print("="*60)
    print(f"  Status: {'[PASS]' if result else '[FAIL]'}")
    print("="*60)
