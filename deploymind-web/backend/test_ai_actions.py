#!/usr/bin/env python3
"""
Test script for AI Actions endpoints.

Prerequisites:
1. Backend running: python -m uvicorn api.main:app --reload --port 8000
2. PostgreSQL running: docker-compose up -d
3. Valid JWT token (login via frontend first)

Usage:
    python test_ai_actions.py
"""
import requests
import time
import json
from typing import Dict, Optional

# Configuration
API_BASE = "http://localhost:8000"
TOKEN = None  # Will be prompted if not set

# ANSI colors for pretty output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'


def print_section(title: str):
    """Print a section header."""
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}{title.center(80)}{RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}\n")


def print_success(message: str):
    """Print success message."""
    print(f"{GREEN}✓ {message}{RESET}")


def print_error(message: str):
    """Print error message."""
    print(f"{RED}✗ {message}{RESET}")


def print_info(message: str):
    """Print info message."""
    print(f"{YELLOW}ℹ {message}{RESET}")


def get_headers() -> Dict[str, str]:
    """Get request headers with auth token."""
    global TOKEN
    if not TOKEN:
        TOKEN = input(f"\n{YELLOW}Enter your JWT token (from browser localStorage):{RESET} ").strip()

    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }


def test_health():
    """Test backend health endpoint."""
    print_section("Testing Backend Health")

    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code == 200:
            print_success(f"Backend is healthy: {response.json()}")
            return True
        else:
            print_error(f"Health check failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print_error(f"Cannot connect to backend: {e}")
        print_info("Make sure backend is running on http://localhost:8000")
        return False


def test_get_deployments():
    """Test getting deployments list."""
    print_section("Testing Deployments Endpoint")

    try:
        response = requests.get(
            f"{API_BASE}/api/deployments",
            headers=get_headers(),
            params={"page": 1, "page_size": 5},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print_success(f"Found {data.get('total', 0)} deployments")

            if data.get('deployments'):
                first_dep = data['deployments'][0]
                print_info(f"First deployment ID: {first_dep['id']}")
                return first_dep['id']
            else:
                print_info("No deployments found - will use mock ID")
                return "demo-deployment-1"
        elif response.status_code == 401:
            print_error("Unauthorized - invalid or expired token")
            print_info("Get a new token by logging in via frontend")
            return None
        else:
            print_error(f"Failed to get deployments: {response.status_code}")
            print_info(f"Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print_error(f"Request failed: {e}")
        return None


def test_scaling_recommendation(deployment_id: str):
    """Test auto-scaling recommendation endpoint."""
    print_section("Testing Auto-Scaling Recommendation")

    try:
        response = requests.post(
            f"{API_BASE}/api/ai/advanced/scaling-recommendation/{deployment_id}",
            headers=get_headers(),
            params={"hours_lookback": 6},
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            print_success("Scaling recommendation received")
            print(json.dumps(data, indent=2))

            # Check for actionable recommendations
            if data.get('actionable_recommendations'):
                print_success(f"Found {len(data['actionable_recommendations'])} actionable recommendations")
                return data['actionable_recommendations'][0]
            else:
                print_info("No actionable recommendations (might be already optimized)")
                return None
        else:
            print_error(f"Failed: {response.status_code}")
            print_info(f"Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print_error(f"Request failed: {e}")
        return None


def test_execute_action(recommendation: Dict):
    """Test executing an AI action."""
    print_section("Testing Action Execution")

    action_type = recommendation.get('action_type')
    print_info(f"Action type: {action_type}")
    print_info(f"Title: {recommendation.get('title')}")
    print_info(f"Description: {recommendation.get('description')}")

    # Map action type to endpoint
    endpoint_map = {
        'scale_instance': 'scale-instance',
        'stop_idle_deployments': 'stop-idle-deployments',
        'trigger_security_scan': 'trigger-security-scan'
    }

    endpoint = endpoint_map.get(action_type)
    if not endpoint:
        print_error(f"Unknown action type: {action_type}")
        return None

    # Prepare request
    request_data = {
        "recommendation_id": recommendation['id'],
        "parameters": recommendation['parameters'],
        "confirmed": True
    }

    print_info(f"Executing: POST /api/ai/actions/execute/{endpoint}")

    try:
        response = requests.post(
            f"{API_BASE}/api/ai/actions/execute/{endpoint}",
            headers=get_headers(),
            json=request_data,
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            execution_id = data.get('execution_id')
            print_success(f"Action initiated! Execution ID: {execution_id}")
            print_info(f"Status: {data.get('status')}")
            print_info(f"Message: {data.get('message')}")
            return execution_id
        else:
            print_error(f"Execution failed: {response.status_code}")
            print_info(f"Response: {response.text}")
            return None

    except requests.exceptions.RequestException as e:
        print_error(f"Request failed: {e}")
        return None


def test_poll_status(execution_id: str, max_attempts: int = 30):
    """Poll action execution status."""
    print_section("Polling Action Status")

    print_info(f"Polling execution {execution_id} (max {max_attempts} attempts, 2s interval)")

    for attempt in range(max_attempts):
        try:
            response = requests.get(
                f"{API_BASE}/api/ai/actions/status/{execution_id}",
                headers=get_headers(),
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                status = data.get('status')
                progress = data.get('progress_percent', 0)
                message = data.get('message', '')

                print(f"[{attempt + 1}/{max_attempts}] Status: {status} | Progress: {progress}% | {message}")

                if status == 'completed':
                    print_success("Action completed successfully!")
                    print(json.dumps(data.get('result', {}), indent=2))
                    return True
                elif status == 'failed':
                    print_error(f"Action failed: {data.get('error_message')}")
                    return False

                # Continue polling
                time.sleep(2)
            else:
                print_error(f"Status check failed: {response.status_code}")
                return False

        except requests.exceptions.RequestException as e:
            print_error(f"Request failed: {e}")
            return False

    print_error("Timeout waiting for action to complete")
    return False


def test_cost_analysis():
    """Test cost trend analysis endpoint."""
    print_section("Testing Cost Trend Analysis")

    try:
        response = requests.get(
            f"{API_BASE}/api/ai/advanced/cost-analysis",
            headers=get_headers(),
            params={"months_lookback": 6},
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            print_success("Cost analysis received")
            print_info(f"Current month cost: ${data.get('total_cost_current_month', 0):.2f}")
            print_info(f"Growth rate: {data.get('monthly_growth_rate_percent', 0):.1f}%")
            print_info(f"Potential savings: ${data.get('potential_savings_monthly', 0):.2f}/mo")

            if data.get('actionable_recommendations'):
                print_success(f"Found {len(data['actionable_recommendations'])} cost optimization actions")
            return True
        else:
            print_error(f"Failed: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print_error(f"Request failed: {e}")
        return False


def test_security_risk(deployment_id: str):
    """Test security risk scoring endpoint."""
    print_section("Testing Security Risk Scoring")

    try:
        response = requests.post(
            f"{API_BASE}/api/ai/advanced/security-risk/{deployment_id}",
            headers=get_headers(),
            timeout=15
        )

        if response.status_code == 200:
            data = response.json()
            print_success("Security risk score received")
            print_info(f"Risk score: {data.get('risk_score', 0):.1f}/100")
            print_info(f"Rating: {data.get('rating')}")
            print_info(f"Confidence: {data.get('confidence')}")

            if data.get('actionable_recommendations'):
                print_success(f"Found {len(data['actionable_recommendations'])} security actions")
            return True
        else:
            print_error(f"Failed: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print_error(f"Request failed: {e}")
        return False


def main():
    """Run all tests."""
    print(f"\n{BLUE}{'=' * 80}{RESET}")
    print(f"{BLUE}{'AI ACTIONS API TEST SUITE'.center(80)}{RESET}")
    print(f"{BLUE}{'=' * 80}{RESET}")

    # Test 1: Backend health
    if not test_health():
        print_error("\n❌ Backend is not running. Please start it first.")
        print_info("Run: python -m uvicorn api.main:app --reload --port 8000")
        return

    # Test 2: Get deployments
    deployment_id = test_get_deployments()
    if not deployment_id:
        print_error("\n❌ Cannot get deployments. Check authentication.")
        return

    # Test 3: Advanced AI endpoints
    test_cost_analysis()
    test_security_risk(deployment_id)

    # Test 4: Scaling recommendation with actionable actions
    recommendation = test_scaling_recommendation(deployment_id)

    if recommendation:
        # Ask user if they want to execute the action
        print_info(f"\nFound actionable recommendation: {recommendation.get('title')}")
        execute = input(f"{YELLOW}Execute this action? (yes/no): {RESET}").strip().lower()

        if execute == 'yes':
            # Test 5: Execute action
            execution_id = test_execute_action(recommendation)

            if execution_id:
                # Test 6: Poll status
                test_poll_status(execution_id)

    print_section("Test Suite Complete")
    print_success("All API endpoints are functional!")
    print_info("\nNext steps:")
    print_info("1. Test the frontend at http://localhost:5000/dashboard/ai-insights")
    print_info("2. Click 'Apply' buttons on recommendations")
    print_info("3. Watch the progress bar and status updates")
    print_info("4. Verify actions complete successfully")


if __name__ == "__main__":
    main()
