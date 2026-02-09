"""Test Day 4: Full multi-agent deployment workflow.

This script tests the complete deployment pipeline with all agents:
1. Security Agent - Trivy scanning, CVE analysis
2. Build Agent - Dockerfile optimization, Docker build
3. Deploy Agent - Rolling deployment with health checks

It deploys a real application to verify the workflow works end-to-end.
"""
import sys
sys.path.insert(0, '.')

from config.settings import Settings
from agents.enhanced_orchestrator import create_orchestrator
from datetime import datetime

def print_header(text):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(text)
    print("=" * 70)

def print_phase(phase, status, details=None):
    """Print phase status."""
    status_icon = "[OK]" if status == "success" else "[FAIL]" if status == "failed" else "[...]"
    print(f"\n{status_icon} {phase}")
    if details:
        for key, value in details.items():
            print(f"   {key}: {value}")

def main():
    print_header("DAY 4 WORKFLOW TEST - Multi-Agent Deployment Pipeline")

    # Load settings
    print("\n[*] Loading configuration...")
    settings = Settings.load()

    # Validate settings
    missing = settings.validate()
    if missing:
        print(f"\n[ERROR] Missing required environment variables: {', '.join(missing)}")
        print("Configure your .env file and try again.")
        return 1

    print("[OK] Configuration loaded")

    # Create orchestrator
    print("\n[*] Initializing Enhanced Orchestrator...")
    orchestrator = create_orchestrator(settings)
    print("[OK] Orchestrator initialized with all agents:")
    print("   - Security Agent (Trivy scanning)")
    print("   - Build Agent (Docker build)")
    print("   - Deploy Agent (Rolling deployment)")

    # Test deployment configuration
    print_header("TEST CONFIGURATION")

    # Use the existing EC2 instance
    instance_id = "i-0ee9185b15eea1604"
    repository = "PrathamModi001/DeployMind"

    print(f"Repository: {repository}")
    print(f"Instance ID: {instance_id}")
    print(f"Port: 8080")
    print(f"Health Check: /health")
    print(f"Strategy: rolling")

    # Confirm deployment
    print("\n[WARNING]  This will deploy to the EC2 instance.")
    confirm = input("Continue? (y/n): ")
    if confirm.lower() != 'y':
        print("Cancelled.")
        return 0

    # Start deployment
    print_header("STARTING DEPLOYMENT PIPELINE")
    start_time = datetime.now()

    try:
        # Deploy with orchestrator
        print("\n[*] Starting multi-agent deployment workflow...")
        print("This will execute all 3 agents in sequence:")
        print("   1. Security Agent -> Scan for vulnerabilities")
        print("   2. Build Agent -> Build Docker image")
        print("   3. Deploy Agent -> Deploy to EC2 with health checks")
        print()

        response = orchestrator.deploy_application(
            repository=repository,
            instance_id=instance_id,
            port=8080,
            strategy="rolling",
            health_check_path="/health",
            environment="staging"
        )

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # Print results
        print_header("DEPLOYMENT RESULTS")

        # Overall status
        if response.success:
            print(f"\n[SUCCESS] DEPLOYMENT SUCCESSFUL!")
            print(f"   Duration: {duration:.1f} seconds")
            print(f"   Deployment ID: {response.deployment_id}")
        else:
            print(f"\n[ERROR] DEPLOYMENT FAILED")
            print(f"   Duration: {duration:.1f} seconds")
            print(f"   Failed at: {response.error_phase} phase")
            print(f"   Error: {response.error_message}")
            if response.rollback_performed:
                print(f"   [WARNING]  Automatic rollback performed")

        # Phase 1: Security
        print_phase(
            "Phase 1: Security Scan",
            "success" if response.security_passed else "failed",
            {
                "Passed": "[OK] Yes" if response.security_passed else "[ERROR] No",
                "Vulnerabilities": response.vulnerabilities_found,
                "Scan ID": response.security_scan_id
            }
        )

        # Phase 2: Build
        if response.build_successful or response.image_tag:
            print_phase(
                "Phase 2: Docker Build",
                "success" if response.build_successful else "failed",
                {
                    "Success": "[OK] Yes" if response.build_successful else "[ERROR] No",
                    "Image Tag": response.image_tag or "N/A",
                    "Image Size": f"{response.image_size_mb:.1f} MB" if response.image_size_mb else "N/A"
                }
            )

        # Phase 3: Deploy
        if response.deployment_successful or response.container_id:
            print_phase(
                "Phase 3: Deployment",
                "success" if response.deployment_successful else "failed",
                {
                    "Success": "[OK] Yes" if response.deployment_successful else "[ERROR] No",
                    "Container ID": response.container_id[:12] if response.container_id else "N/A",
                    "Health Check": "[OK] Passed" if response.health_check_passed else "[ERROR] Failed",
                    "Application URL": response.application_url or "N/A"
                }
            )

        # Summary
        print_header("TEST SUMMARY")
        print(f"\nAgent Workflow: {'[OK] PASSED' if response.success else '[ERROR] FAILED'}")
        print(f"Total Duration: {duration:.1f} seconds")
        print(f"\nPhases Completed:")
        print(f"  1. Security Scan: {'[OK]' if response.security_passed else '[ERROR]'}")
        print(f"  2. Build Image: {'[OK]' if response.build_successful else '[ERROR]'}")
        print(f"  3. Deploy App: {'[OK]' if response.deployment_successful else '[ERROR]'}")

        if response.success:
            print(f"\n[URL] Application running at: {response.application_url}")
            print(f"\n[TIP] Test the deployment:")
            print(f"   curl {response.application_url}")
            print(f"   curl {response.application_url}/health")

        # Clean up
        orchestrator.close()

        return 0 if response.success else 1

    except Exception as e:
        print(f"\n[ERROR] EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
