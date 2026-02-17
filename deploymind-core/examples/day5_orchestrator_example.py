"""Example usage of the Day 5 Enhanced Orchestrator.

This script demonstrates how to use the complete deployment pipeline
with real-time progress tracking.
"""

from config.settings import Settings
from agents.enhanced_orchestrator import create_orchestrator


def example_basic_deployment():
    """Example 1: Basic deployment."""
    print("=" * 70)
    print("EXAMPLE 1: Basic Deployment")
    print("=" * 70)

    # Load settings from .env
    settings = Settings.load()

    # Create orchestrator
    orchestrator = create_orchestrator(settings)

    # Deploy application
    print("\nDeploying application...")
    response = orchestrator.deploy_application(
        repository="owner/myapp",
        instance_id="i-1234567890abcdef0",
        port=8080,
        strategy="rolling",
        health_check_path="/health",
        environment="production"
    )

    # Check result
    if response.success:
        print("\n✅ DEPLOYMENT SUCCESSFUL!")
        print(f"   Application URL: {response.application_url}")
        print(f"   Image Tag: {response.image_tag}")
        print(f"   Duration: {response.duration_seconds:.1f}s")
        print(f"   Security: {response.vulnerabilities_found} vulnerabilities found")
        print(f"   Image Size: {response.image_size_mb:.1f} MB")
    else:
        print("\n❌ DEPLOYMENT FAILED!")
        print(f"   Failed at: {response.error_phase} phase")
        print(f"   Error: {response.error_message}")
        if response.rollback_performed:
            print(f"   ⚠️  Rolled back to previous version")

    # Clean up
    orchestrator.close()


def example_with_monitoring():
    """Example 2: Deployment with real-time monitoring."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Deployment with Real-Time Monitoring")
    print("=" * 70)

    # Load settings
    settings = Settings.load()
    orchestrator = create_orchestrator(settings)

    # Define event handler
    def on_deployment_event(event):
        """Handle real-time deployment events."""
        event_type = event.get("event_type")
        deployment_id = event.get("deployment_id")

        print(f"\n📡 Event: {event_type} (deployment: {deployment_id})")

        if event_type == "deployment_started":
            print(f"   Repository: {event.get('repository')}")
            print(f"   Instance: {event.get('instance_id')}")

        elif event_type == "security_scan_completed":
            passed = event.get("passed")
            status = "✅ PASSED" if passed else "❌ FAILED"
            print(f"   Status: {status}")
            print(f"   Vulnerabilities: {event.get('vulnerabilities', 0)}")

        elif event_type == "build_completed":
            success = event.get("success")
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"   Status: {status}")
            if success:
                print(f"   Image: {event.get('image_tag')}")
                print(f"   Size: {event.get('image_size_mb', 0):.1f} MB")

        elif event_type == "deployment_completed":
            success = event.get("success")
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"   Status: {status}")
            if success:
                print(f"   Container: {event.get('container_id')}")
                print(f"   Health Check: {'✅ PASSED' if event.get('health_check_passed') else '❌ FAILED'}")

        elif event_type == "deployment_failed":
            print(f"   Phase: {event.get('phase')}")
            print(f"   Reason: {event.get('reason')}")
            if event.get("rollback_performed"):
                print(f"   ⚠️  Rollback performed")

    # Subscribe to events
    print("\nSubscribing to deployment events...")
    orchestrator.subscribe_to_events(on_deployment_event)

    # Deploy
    print("\nStarting deployment...")
    response = orchestrator.deploy_application(
        repository="owner/myapp",
        instance_id="i-1234567890abcdef0"
    )

    # Final status
    print("\n" + "=" * 70)
    print("FINAL STATUS")
    print("=" * 70)
    print(f"Success: {response.success}")
    print(f"Deployment ID: {response.deployment_id}")

    # Clean up
    orchestrator.close()


def example_check_status():
    """Example 3: Check deployment status."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Check Deployment Status")
    print("=" * 70)

    # Load settings
    settings = Settings.load()
    orchestrator = create_orchestrator(settings)

    # Check status of a previous deployment
    deployment_id = "abc12345"  # Replace with actual deployment ID

    print(f"\nChecking status of deployment: {deployment_id}")
    status = orchestrator.get_deployment_status(deployment_id)

    if status:
        print("\n📊 Deployment Status:")
        print(f"   Status: {status.get('status')}")
        print(f"   Image Tag: {status.get('image_tag')}")
        print(f"   Commit SHA: {status.get('commit_sha')}")
    else:
        print("\n⚠️  Deployment not found or expired (cache TTL: 24 hours)")

    # Clean up
    orchestrator.close()


def example_error_handling():
    """Example 4: Demonstrate error handling."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Error Handling")
    print("=" * 70)

    # Load settings
    settings = Settings.load()
    orchestrator = create_orchestrator(settings)

    # Test cases for different error scenarios
    test_cases = [
        {
            "name": "Invalid repository format",
            "repository": "invalid-repo-name",  # Missing owner/
            "instance_id": "i-1234567890abcdef0"
        },
        {
            "name": "Invalid instance ID",
            "repository": "owner/repo",
            "instance_id": "invalid-instance-id"  # Wrong format
        },
        {
            "name": "Invalid port",
            "repository": "owner/repo",
            "instance_id": "i-1234567890abcdef0",
            "port": 99999  # Out of range
        }
    ]

    for test in test_cases:
        print(f"\n📝 Testing: {test['name']}")

        response = orchestrator.deploy_application(
            repository=test["repository"],
            instance_id=test["instance_id"],
            port=test.get("port", 8080)
        )

        if response.success:
            print("   ✅ Unexpected success")
        else:
            print(f"   ❌ Expected failure: {response.error_phase}")
            print(f"   Error: {response.error_message}")

    # Clean up
    orchestrator.close()


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════════════════════╗
║              DeployMind Day 5 - Orchestrator Examples                    ║
╚══════════════════════════════════════════════════════════════════════════╝

This script demonstrates the complete deployment pipeline with:
- Basic deployment
- Real-time monitoring
- Status checking
- Error handling

Prerequisites:
1. Redis running (docker-compose up -d)
2. .env file configured with API keys
3. Docker daemon running
4. AWS credentials configured

Note: These are examples - they will not actually deploy without valid
      GitHub repositories and EC2 instances.
""")

    # Run examples (comment out as needed)
    # example_basic_deployment()
    # example_with_monitoring()
    # example_check_status()
    # example_error_handling()

    print("\n💡 Uncomment the example functions in __main__ to run them.")
    print("   Make sure your .env file is configured with valid credentials.")
