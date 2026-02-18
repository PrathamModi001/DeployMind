#!/bin/bash
# DeployMind Web Backend - Full Test Suite
# Tests all features: Auth, Deployments, Analytics, WebSocket, AI

set -e  # Exit on error

echo "=================================="
echo "DeployMind Web Backend Test Suite"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Change to backend directory
cd "$(dirname "$0")"

echo -e "${BLUE}Running all tests...${NC}"
echo ""

# Run all tests with verbose output
python -m pytest api/tests/ -v --tb=short

# Check exit code
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}=================================="
    echo -e "ALL TESTS PASSED!"
    echo -e "==================================${NC}"
    echo ""
    echo "Test Summary:"
    echo "  - Authentication (GitHub OAuth, JWT)"
    echo "  - Deployments (CRUD, logs, rollback)"
    echo "  - Analytics (overview, timeline, performance)"
    echo "  - AI Features (6 endpoints with mock fallbacks)"
    echo ""
    exit 0
else
    echo ""
    echo -e "${RED}=================================="
    echo -e "TESTS FAILED"
    echo -e "==================================${NC}"
    exit 1
fi
