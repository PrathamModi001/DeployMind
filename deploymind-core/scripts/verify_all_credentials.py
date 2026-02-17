"""Comprehensive credential verification for DeployMind.

Tests all three required services:
1. Groq API (LLM provider)
2. GitHub API (source code)
3. AWS EC2 (deployment target)

Run this AFTER you've added all credentials to .env file.
"""

import os
import sys
from dotenv import load_dotenv

def test_groq():
    """Test Groq API credentials."""
    print("\n" + "="*60)
    print("1. TESTING GROQ API")
    print("="*60)

    groq_key = os.getenv("GROQ_API_KEY")

    if not groq_key:
        print("❌ GROQ_API_KEY not found in .env")
        print("   Get free key: https://console.groq.com/keys")
        return False

    print(f"✅ GROQ_API_KEY found: {groq_key[:10]}...{groq_key[-4:]}")

    try:
        from groq import Groq
        print("✅ Groq SDK installed")
    except ImportError:
        print("❌ Groq SDK not installed")
        print("   Fix: pip install groq>=0.4.0")
        return False

    try:
        client = Groq(api_key=groq_key)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": "Reply with: Groq working!"}],
            max_tokens=50
        )
        result = response.choices[0].message.content
        print(f"✅ API Connection: {result}")
        print("✅ Groq API: ALL TESTS PASSED")
        return True
    except Exception as e:
        print(f"❌ API Connection Failed: {e}")
        return False


def test_github():
    """Test GitHub API credentials."""
    print("\n" + "="*60)
    print("2. TESTING GITHUB API")
    print("="*60)

    github_token = os.getenv("GITHUB_TOKEN")

    if not github_token:
        print("❌ GITHUB_TOKEN not found in .env")
        print("   Get token: https://github.com/settings/tokens")
        return False

    print(f"✅ GITHUB_TOKEN found: {github_token[:7]}...{github_token[-4:]}")

    try:
        import requests
        print("✅ requests library available")
    except ImportError:
        print("❌ requests not installed")
        print("   Fix: pip install requests")
        return False

    try:
        import requests
        headers = {"Authorization": f"token {github_token}"}
        response = requests.get("https://api.github.com/user", headers=headers)

        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Authenticated as: {user_data.get('login', 'Unknown')}")

            # Check rate limit
            rate_response = requests.get("https://api.github.com/rate_limit", headers=headers)
            if rate_response.status_code == 200:
                rate_data = rate_response.json()
                remaining = rate_data['rate']['remaining']
                limit = rate_data['rate']['limit']
                print(f"✅ Rate Limit: {remaining}/{limit} requests remaining")

            # Check token scopes
            scopes = response.headers.get('X-OAuth-Scopes', '')
            print(f"✅ Token Scopes: {scopes}")

            if 'repo' in scopes:
                print("✅ Has 'repo' scope (required)")
            else:
                print("⚠️  Missing 'repo' scope - may have limited access")

            print("✅ GitHub API: ALL TESTS PASSED")
            return True
        elif response.status_code == 401:
            print("❌ Invalid GitHub token (401 Unauthorized)")
            print("   Regenerate token at: https://github.com/settings/tokens")
            return False
        else:
            print(f"❌ Unexpected response: {response.status_code}")
            print(f"   {response.text}")
            return False

    except Exception as e:
        print(f"❌ GitHub API test failed: {e}")
        return False


def test_aws():
    """Test AWS credentials."""
    print("\n" + "="*60)
    print("3. TESTING AWS CREDENTIALS")
    print("="*60)

    aws_key_id = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    if not aws_key_id:
        print("❌ AWS_ACCESS_KEY_ID not found in .env")
        print("   Get from: AWS Console → IAM → Users → Security Credentials")
        return False

    if not aws_secret:
        print("❌ AWS_SECRET_ACCESS_KEY not found in .env")
        return False

    print(f"✅ AWS_ACCESS_KEY_ID: {aws_key_id[:8]}...{aws_key_id[-4:]}")
    print(f"✅ AWS_REGION: {aws_region}")

    try:
        import boto3
        print("✅ boto3 installed")
    except ImportError:
        print("❌ boto3 not installed")
        print("   Fix: pip install boto3>=1.34.0")
        return False

    try:
        # Test STS (get caller identity)
        sts = boto3.client(
            'sts',
            aws_access_key_id=aws_key_id,
            aws_secret_access_key=aws_secret,
            region_name=aws_region
        )

        identity = sts.get_caller_identity()
        print(f"✅ Authenticated as: {identity['Arn']}")
        print(f"   Account ID: {identity['Account']}")
        print(f"   User ID: {identity['UserId']}")

        # Test EC2 access
        ec2 = boto3.client(
            'ec2',
            aws_access_key_id=aws_key_id,
            aws_secret_access_key=aws_secret,
            region_name=aws_region
        )

        # Try to describe instances
        response = ec2.describe_instances()
        instance_count = sum(len(r['Instances']) for r in response['Reservations'])
        print(f"✅ EC2 Access: Found {instance_count} instances in {aws_region}")

        # Check if any instances are free tier eligible
        for reservation in response['Reservations']:
            for instance in reservation['Instances']:
                instance_type = instance['InstanceType']
                state = instance['State']['Name']
                instance_id = instance['InstanceId']

                if instance_type == 't2.micro':
                    print(f"✅ Free Tier Instance: {instance_id} ({state})")
                elif instance_type.startswith('t2.'):
                    print(f"⚠️  Instance {instance_id}: {instance_type} (free tier only for t2.micro)")
                else:
                    print(f"⚠️  Instance {instance_id}: {instance_type} (NOT free tier eligible!)")

        # Verify permissions by trying to describe regions
        regions = ec2.describe_regions()
        print(f"✅ Can access {len(regions['Regions'])} AWS regions")

        print("✅ AWS Credentials: ALL TESTS PASSED")
        return True

    except Exception as e:
        error_str = str(e)

        if "InvalidClientTokenId" in error_str:
            print("❌ Invalid AWS Access Key ID")
            print("   Check AWS_ACCESS_KEY_ID in .env")
        elif "SignatureDoesNotMatch" in error_str:
            print("❌ Invalid AWS Secret Access Key")
            print("   Check AWS_SECRET_ACCESS_KEY in .env")
        elif "UnauthorizedOperation" in error_str or "AccessDenied" in error_str:
            print("❌ Insufficient permissions")
            print("   Add 'AmazonEC2FullAccess' policy to your IAM user")
        else:
            print(f"❌ AWS test failed: {e}")

        return False


def main():
    """Run all credential tests."""
    print("\n" + "🔍 DEPLOYMIND CREDENTIAL VERIFICATION" + "\n")

    # Load environment variables
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("\n📋 To fix:")
        print("1. Copy example: cp .env.example .env")
        print("2. Edit .env and add your credentials")
        print("3. Run this script again")
        sys.exit(1)

    load_dotenv()
    print("✅ .env file loaded\n")

    # Run all tests
    results = {
        "Groq API": test_groq(),
        "GitHub API": test_github(),
        "AWS Credentials": test_aws()
    }

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)

    all_passed = True
    for service, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{service:20} {status}")
        if not passed:
            all_passed = False

    print("="*60)

    if all_passed:
        print("\n🎉 ALL CREDENTIALS VERIFIED!")
        print("\nNext steps:")
        print("1. Start local services: docker-compose up -d")
        print("2. Run tests: pytest tests/ -v")
        print("3. Continue with Day 1 tasks in DEPLOYMENT_AGENT_2WEEK_PLAN.md")
        print("\n✨ You're ready to start building DeployMind!")
        return 0
    else:
        print("\n⚠️  SOME CREDENTIALS FAILED")
        print("\nFix the issues above, then run this script again:")
        print("  python verify_all_credentials.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
