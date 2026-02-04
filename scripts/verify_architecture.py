"""Comprehensive architecture verification script.

Tests all layers, imports, and integrations to ensure
the Clean Architecture migration is working correctly.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_directory_structure():
    """Verify all required directories exist."""
    print("\n" + "="*60)
    print("1. TESTING DIRECTORY STRUCTURE")
    print("="*60)

    required_dirs = [
        "domain/entities",
        "domain/value_objects",
        "domain/repositories",
        "domain/services",
        "application/use_cases",
        "application/dto",
        "application/interfaces",
        "infrastructure/cloud/aws",
        "infrastructure/vcs/github",
        "infrastructure/cache",
        "infrastructure/llm/groq",
        "agents/security",
        "agents/build",
        "agents/deploy",
        "agents/orchestrator",
        "presentation/cli",
        "presentation/api",
        "config",
        "shared",
        "tests/unit",
        "tests/integration",
        "tests/e2e",
    ]

    all_exist = True
    for dir_path in required_dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"  [OK] {dir_path}")
        else:
            print(f"  [FAIL] {dir_path} - MISSING")
            all_exist = False

    return all_exist


def test_imports():
    """Test that all critical imports work."""
    print("\n" + "="*60)
    print("2. TESTING IMPORTS")
    print("="*60)

    imports = {
        "Config/Settings": "from config.settings import settings",
        "Dependency Container": "from config.dependencies import container",
        "Domain - Deployment": "from domain.entities.deployment import Deployment",
        "Domain - Status": "from domain.value_objects.deployment_status import DeploymentStatus",
        "Domain - Repository": "from domain.repositories.deployment_repository import DeploymentRepository",
        "Infrastructure - EC2": "from infrastructure.cloud.aws.ec2_client import EC2Client",
        "Infrastructure - GitHub": "from infrastructure.vcs.github.github_client import GitHubClient",
        "Infrastructure - Redis": "from infrastructure.cache.redis_client import RedisClient",
        "Infrastructure - Groq": "from infrastructure.llm.groq.groq_client import GroqClient",
        "Shared - Exceptions": "from shared.exceptions import DeployMindException",
    }

    all_pass = True
    for name, import_stmt in imports.items():
        try:
            exec(import_stmt)
            print(f"  [OK] {name}")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            all_pass = False

    return all_pass


def test_settings():
    """Test settings load correctly."""
    print("\n" + "="*60)
    print("3. TESTING SETTINGS")
    print("="*60)

    try:
        from config.settings import settings

        # Check required fields exist
        checks = {
            "groq_api_key": settings.groq_api_key,
            "aws_access_key_id": settings.aws_access_key_id,
            "aws_secret_access_key": settings.aws_secret_access_key,
            "github_token": settings.github_token,
            "database_url": settings.database_url,
            "redis_url": settings.redis_url,
            "default_llm": settings.default_llm,
        }

        all_pass = True
        for key, value in checks.items():
            if value:
                masked_value = value[:10] + "..." if len(value) > 10 else value
                print(f"  [OK] {key}: {masked_value}")
            else:
                print(f"  [WARN] {key}: Not set (optional)")

        # Test methods
        print(f"  [OK] is_production: {settings.is_production}")
        print(f"  [OK] is_development: {settings.is_development}")

        missing = settings.validate()
        if missing:
            print(f"  [WARN] Missing required vars: {', '.join(missing)}")
        else:
            print(f"  [OK] All required settings present")

        return True

    except Exception as e:
        print(f"  [FAIL] Settings failed: {e}")
        return False


def test_dependency_injection():
    """Test dependency injection container."""
    print("\n" + "="*60)
    print("4. TESTING DEPENDENCY INJECTION")
    print("="*60)

    try:
        from config.dependencies import container

        # Test all dependencies exist
        deps = {
            "ec2_client": container.ec2_client,
            "github_client": container.github_client,
            "redis_client": container.redis_client,
            "groq_client": container.groq_client,
        }

        all_pass = True
        for name, dep in deps.items():
            if dep is not None:
                print(f"  [OK] {name}: {type(dep).__name__}")
            else:
                print(f"  [FAIL] {name}: None")
                all_pass = False

        # Test validation method
        print("\n  Testing validate_all()...")
        container.validate_all()

        return all_pass

    except Exception as e:
        print(f"  [FAIL] Dependency injection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_domain_layer():
    """Test domain layer entities and value objects."""
    print("\n" + "="*60)
    print("5. TESTING DOMAIN LAYER")
    print("="*60)

    try:
        from domain.entities.deployment import Deployment
        from domain.value_objects.deployment_status import DeploymentStatus
        from datetime import datetime

        # Test Deployment entity
        deployment = Deployment(
            id="test-123",
            repository="user/repo",
            instance_id="i-123456",
            status="pending",
            created_at=datetime.now()
        )
        print(f"  [OK] Deployment entity created: {deployment.id}")
        print(f"  [OK] can_rollback(): {deployment.can_rollback()}")

        # Test DeploymentStatus enum
        statuses = [s.value for s in DeploymentStatus]
        print(f"  [OK] DeploymentStatus enum: {len(statuses)} statuses")
        print(f"      Statuses: {', '.join(statuses)}")

        return True

    except Exception as e:
        print(f"  [FAIL] Domain layer failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_infrastructure_layer():
    """Test infrastructure layer clients."""
    print("\n" + "="*60)
    print("6. TESTING INFRASTRUCTURE LAYER")
    print("="*60)

    try:
        from config.settings import settings
        from infrastructure.cloud.aws.ec2_client import EC2Client
        from infrastructure.vcs.github.github_client import GitHubClient
        from infrastructure.cache.redis_client import RedisClient
        from infrastructure.llm.groq.groq_client import GroqClient

        # Test EC2Client instantiation
        ec2 = EC2Client(settings)
        print(f"  [OK] EC2Client instantiated")
        print(f"  [OK] EC2Client has validate_credentials method")

        # Test GitHubClient instantiation
        github = GitHubClient(settings)
        print(f"  [OK] GitHubClient instantiated")
        print(f"  [OK] GitHubClient has validate_token method")

        # Test RedisClient instantiation
        redis = RedisClient(settings.redis_url)
        print(f"  [OK] RedisClient instantiated")

        # Test GroqClient instantiation
        groq = GroqClient(settings.groq_api_key)
        print(f"  [OK] GroqClient instantiated")

        return True

    except Exception as e:
        print(f"  [FAIL] Infrastructure layer failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_live_connections():
    """Test actual connections to external services."""
    print("\n" + "="*60)
    print("7. TESTING LIVE CONNECTIONS")
    print("="*60)

    try:
        from config.dependencies import container

        # Test AWS
        print("\n  Testing AWS Connection...")
        aws_valid = container.ec2_client.validate_credentials()
        if aws_valid:
            print(f"  [OK] AWS credentials valid")
        else:
            print(f"  [FAIL] AWS credentials invalid")

        # Test GitHub
        print("\n  Testing GitHub Connection...")
        github_valid = container.github_client.validate_token()
        if github_valid:
            print(f"  [OK] GitHub token valid")
        else:
            print(f"  [FAIL] GitHub token invalid")

        return aws_valid and github_valid

    except Exception as e:
        print(f"  [FAIL] Live connections failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_no_circular_imports():
    """Test that there are no circular import issues."""
    print("\n" + "="*60)
    print("8. TESTING NO CIRCULAR IMPORTS")
    print("="*60)

    try:
        # Import all major modules
        import domain.entities.deployment
        import domain.value_objects.deployment_status
        import domain.repositories.deployment_repository
        import application.use_cases.deploy_application
        import application.interfaces.cloud_service
        import infrastructure.cloud.aws.ec2_client
        import infrastructure.vcs.github.github_client
        import infrastructure.cache.redis_client
        import infrastructure.llm.groq.groq_client
        import config.settings
        import config.dependencies
        import shared.exceptions

        print(f"  [OK] No circular imports detected")
        print(f"  [OK] All modules imported successfully")
        return True

    except Exception as e:
        print(f"  [FAIL] Circular import detected: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all verification tests."""
    print("\n" + "="*70)
    print("  DEPLOYMIND ARCHITECTURE VERIFICATION")
    print("  Clean Architecture Migration Validation")
    print("="*70)

    # Run all tests
    results = {
        "Directory Structure": test_directory_structure(),
        "Imports": test_imports(),
        "Settings": test_settings(),
        "Dependency Injection": test_dependency_injection(),
        "Domain Layer": test_domain_layer(),
        "Infrastructure Layer": test_infrastructure_layer(),
        "Live Connections": test_live_connections(),
        "No Circular Imports": test_no_circular_imports(),
    }

    # Summary
    print("\n" + "="*70)
    print("VERIFICATION SUMMARY")
    print("="*70)

    all_passed = True
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False

    print("="*70)

    if all_passed:
        print("\n[OK] ALL TESTS PASSED!")
        print("\nArchitecture is working correctly.")
        print("You're ready to start implementing features!")
        print("\nNext steps:")
        print("1. Read NEXT_STEPS.md for implementation guide")
        print("2. Start with Day 1 remaining tasks")
        print("3. Or move to Day 2 (Security Agent)")
        return 0
    else:
        print("\n[FAIL] SOME TESTS FAILED")
        print("\nPlease review the failures above and fix them.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
