# 🎯 AI Actions Usage & Testing Guide

**Complete guide for using and testing the AI-powered actionable recommendations feature.**

Last Updated: 2026-02-20

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Feature Overview](#feature-overview)
3. [Backend Testing](#backend-testing)
4. [Frontend Testing](#frontend-testing)
5. [Database Verification](#database-verification)
6. [Troubleshooting](#troubleshooting)
7. [API Reference](#api-reference)

---

## 🚀 Quick Start

### Prerequisites

✅ **Required:**
- PostgreSQL running (port 5432)
- Node.js 18+ (for frontend)
- Python 3.10+ (for backend)

✅ **Optional (for full functionality):**
- AWS credentials (for EC2 operations)
- GitHub token (for repository access)
- Groq API key (for LLM features)

### Step 1: Start PostgreSQL

```bash
# Using Docker Compose
cd E:\devops\deploymind
docker-compose up -d

# Verify PostgreSQL is running
docker ps | findstr postgres
```

### Step 2: Initialize Database

```bash
cd E:\devops\deploymind\deploymind-web\backend

# Initialize web-specific tables (action_executions, etc.)
python -c "from api.services.database import init_web_db; init_web_db()"

# Expected output:
# ✓ Web database tables initialized
```

### Step 3: Start Backend

```bash
cd E:\devops\deploymind\deploymind-web\backend

# Activate venv (if using)
venv\Scripts\Activate.ps1

# Start server
python -m uvicorn api.main:app --reload --port 8000

# Expected output:
# INFO: Uvicorn running on http://127.0.0.1:8000
# INFO: Application startup complete.
```

**Verify backend is running:**
```bash
curl http://localhost:8000/health
# Expected: {"status":"healthy","service":"deploymind-api","version":"1.0.0"}
```

### Step 4: Start Frontend

```bash
# In a NEW terminal
cd E:\devops\deploymind\deploymind-web\frontend

npm run dev

# Expected output:
# ▲ Next.js 14.x.x
# - Local:        http://localhost:5000
```

### Step 5: Login & Test

1. Navigate to `http://localhost:5000`
2. Login with GitHub OAuth
3. Go to **AI Insights** page: `http://localhost:5000/dashboard/ai-insights`
4. Look for "Quick Actions" sections with **Apply** buttons
5. Click **Apply** → Review confirmation → Click **Confirm**
6. Watch the magic! ✨

---

## 🎯 Feature Overview

### What Are AI Actions?

AI Actions transform **read-only AI recommendations** into **one-click executable operations** with real-time progress tracking.

### Implemented Actions (3 Types)

#### 1️⃣ **Scale Instance** (Vertical Scaling)
- **What it does:** Changes EC2 instance type (e.g., t2.micro → t2.small)
- **Process:** Stop instance → Modify type → Start instance
- **Shows:** Cost impact, downtime estimate, performance improvement
- **Confirmation:** ✅ Required (destructive)
- **Duration:** ~3 minutes

**Example:**
```
Title: "Upgrade to t2.small"
Impact: +$8.46/mo, ~2 min downtime, +50% performance
```

#### 2️⃣ **Stop Idle Deployments** (Cost Optimization)
- **What it does:** Stops multiple EC2 instances that are idle
- **Shows:** Monthly savings, number of deployments affected
- **Confirmation:** ✅ Required (destructive)
- **Duration:** ~2 minutes

**Example:**
```
Title: "Stop 2 idle deployments"
Impact: Save $16.94/month, affects 2 deployments
```

#### 3️⃣ **Trigger Security Scan** (Security)
- **What it does:** Runs Trivy security scan on container image
- **Shows:** Scan age, risk reduction estimate
- **Confirmation:** ❌ Not required (safe, read-only)
- **Duration:** ~5 minutes

**Example:**
```
Title: "Run fresh security scan"
Impact: Scan is 8 days old, high risk reduction
```

---

## 🧪 Backend Testing

### Automated Test Script

We've created a comprehensive Python test script that tests all API endpoints:

```bash
cd E:\devops\deploymind\deploymind-web\backend
python test_ai_actions.py
```

**What it tests:**
1. ✅ Backend health check
2. ✅ Authentication & deployments list
3. ✅ Cost trend analysis endpoint
4. ✅ Security risk scoring endpoint
5. ✅ Auto-scaling recommendation endpoint
6. ✅ Action execution endpoints (3 types)
7. ✅ Status polling endpoint
8. ✅ Real-time progress tracking

**Expected Output:**
```
================================================================================
                        AI ACTIONS API TEST SUITE
================================================================================

================================================================================
                        Testing Backend Health
================================================================================

✓ Backend is healthy: {'status': 'healthy', ...}

================================================================================
                     Testing Deployments Endpoint
================================================================================

✓ Found 5 deployments
ℹ First deployment ID: dep-abc123

... (continues with all tests)

Found actionable recommendation: Upgrade to t2.small
Execute this action? (yes/no):
```

### Manual API Testing (cURL)

#### Test 1: Health Check
```bash
curl http://localhost:8000/health
```

#### Test 2: Get Deployments (requires auth token)
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/deployments?page=1&page_size=5
```

#### Test 3: Get Scaling Recommendation
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  http://localhost:8000/api/ai/advanced/scaling-recommendation/DEPLOYMENT_ID?hours_lookback=6
```

#### Test 4: Execute Action
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "recommendation_id": "scale-dep-abc123-xyz",
    "parameters": {
      "deployment_id": "dep-abc123",
      "current_instance_type": "t2.micro",
      "target_instance_type": "t2.small",
      "instance_id": "i-0123456789abcdef"
    },
    "confirmed": true
  }' \
  http://localhost:8000/api/ai/actions/execute/scale-instance
```

#### Test 5: Poll Status
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/ai/actions/status/EXECUTION_ID
```

---

## 🖥️ Frontend Testing

### AI Insights Page Testing

**URL:** `http://localhost:5000/dashboard/ai-insights`

#### Test Scenario 1: View Recommendations

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Navigate to AI Insights | Page loads with 3 sections |
| 2 | Check Auto-Scaling section | Shows CPU/Memory utilization metrics |
| 3 | Check Cost Trends section | Shows monthly cost & growth rate |
| 4 | Check Security Risk section | Shows risk score /100 |
| 5 | Scroll to "Quick Actions" | Each section has actionable recommendations |

#### Test Scenario 2: Execute Scaling Action

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Locate "Upgrade to t2.small" recommendation | Shows cost impact, downtime |
| 2 | Click **Apply** button | Confirmation dialog appears |
| 3 | Review dialog | Shows: Impact summary, Warning, Cancel/Confirm buttons |
| 4 | Click **Confirm** | Dialog closes, button shows "Applying... 0%" |
| 5 | Watch progress | Button updates: 20% → 50% → 90% → 100% |
| 6 | Wait 2-3 minutes | Button shows "Applied ✓" with green checkmark |
| 7 | Wait 3 seconds | Button resets to "Apply", recommendation may disappear |
| 8 | Check page refresh | Metrics update automatically |

#### Test Scenario 3: Execute Security Scan

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Locate "Run fresh security scan" | Shows scan age (e.g., "8 days old") |
| 2 | Click **Apply** (no confirmation) | Action starts immediately |
| 3 | Watch progress | 0% → 30% → 80% → 100% |
| 4 | Wait ~5 minutes | Button shows "Applied ✓" |
| 5 | Check security risk score | Updates with fresh data |
| 6 | Check scan age | Now shows "0 days ago" |

#### Test Scenario 4: Execute Cost Optimization

| Step | Action | Expected Result |
|------|--------|----------------|
| 1 | Locate "Stop 2 idle deployments" | Shows savings: $16.94/mo |
| 2 | Click **Apply** | Confirmation dialog with warning |
| 3 | Review impact | Shows: Savings, Deployments affected, Warning message |
| 4 | Click **Confirm** | Action executes |
| 5 | Watch progress | 20% → 70% → 100% |
| 6 | Verify instances stopped | Check deployments list - instances stopped |

### Edge Cases Testing

| Test Case | Action | Expected Result |
|-----------|--------|----------------|
| **Cancel confirmation** | Click Apply → Cancel | Dialog closes, no action executed |
| **Network error** | Disconnect wifi → Click Apply | Shows error message |
| **Concurrent actions** | Click Apply twice rapidly | Second click disabled |
| **Page refresh mid-action** | Refresh during execution | Action continues in background |
| **Unauthorized access** | Logout → Try to poll status | Returns 401 error |

---

## 💾 Database Verification

### Check Action Executions Table

```sql
-- Connect to database
psql -U admin -d deploymind

-- View recent executions
SELECT
  id,
  action_type,
  status,
  progress_percent,
  created_at,
  started_at,
  completed_at
FROM action_executions
ORDER BY created_at DESC
LIMIT 10;
```

**Expected Output:**
```
     id      |       action_type        |  status   | progress_percent |      created_at
-------------+--------------------------+-----------+------------------+---------------------
 exec-abc123 | scale_instance           | completed |              100 | 2026-02-20 10:30:00
 exec-def456 | trigger_security_scan    | completed |              100 | 2026-02-20 10:25:00
 exec-ghi789 | stop_idle_deployments    | in_progress |             50 | 2026-02-20 10:20:00
```

### Verify Cascade Deletion

```sql
-- Before deletion - Note deployment ID
SET deployment_id = 'dep-abc123';

-- Delete deployment (via frontend or API)

-- After deletion - Verify cascade
SELECT COUNT(*) FROM deployments WHERE id = 'dep-abc123';
-- Expected: 0

SELECT COUNT(*) FROM security_scans WHERE deployment_id = 'dep-abc123';
-- Expected: 0

SELECT COUNT(*) FROM action_executions WHERE deployment_id = 'dep-abc123';
-- Expected: 0 (cascaded)
```

### Action Execution Details

```sql
-- View full execution details
SELECT
  id,
  action_type,
  status,
  parameters,
  result,
  error_message,
  progress_percent,
  current_step,
  created_at,
  started_at,
  completed_at,
  (completed_at - started_at) AS duration
FROM action_executions
WHERE id = 'exec-abc123';
```

---

## 🔧 Troubleshooting

### Issue 1: Backend won't start

**Error:** `ModuleNotFoundError: No module named 'deploymind'`

**Solution:**
```bash
# Install missing dependencies
cd E:\devops\deploymind\deploymind-web\backend
pip install PyGithub boto3 python-dotenv sqlalchemy psycopg2-binary
```

---

### Issue 2: Database connection error

**Error:** `connection to server at "localhost" (::1), port 5432 failed`

**Solution:**
```bash
# Check if PostgreSQL is running
docker ps | findstr postgres

# If not running, start it
cd E:\devops\deploymind
docker-compose up -d

# Verify connection
psql -U admin -d deploymind -c "SELECT 1;"
```

---

### Issue 3: Action executions not saving

**Error:** Actions execute but aren't saved to database

**Solution:**
```bash
# Initialize action_executions table
cd E:\devops\deploymind\deploymind-web\backend
python -c "from api.services.database import init_web_db; init_web_db()"
```

---

### Issue 4: "Apply" button shows error

**Error:** "Failed to execute scaling: ..."

**Possible causes:**
1. **Missing AWS credentials** (for scale/stop actions)
   - Solution: Add AWS credentials to `.env` file
   ```
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   AWS_REGION=us-east-1
   ```

2. **Invalid deployment ID**
   - Solution: Use a valid deployment ID from `/api/deployments`

3. **Action already in progress**
   - Solution: Wait for previous action to complete

4. **Unauthorized**
   - Solution: Login again to refresh JWT token

---

### Issue 5: Progress stuck at 0%

**Symptoms:** Button shows "Applying... 0%" indefinitely

**Solution:**
```bash
# Check backend logs for errors
# Look for "[ERROR]" messages

# Check action_executions table
psql -U admin -d deploymind -c "
SELECT id, status, error_message
FROM action_executions
WHERE status = 'failed'
ORDER BY created_at DESC
LIMIT 5;"
```

---

## 📚 API Reference

### Endpoints

#### 1. Execute Scale Instance
```http
POST /api/ai/actions/execute/scale-instance
Authorization: Bearer {token}
Content-Type: application/json

{
  "recommendation_id": "scale-dep-123-abc",
  "parameters": {
    "deployment_id": "dep-123",
    "current_instance_type": "t2.micro",
    "target_instance_type": "t2.small",
    "instance_id": "i-abc123"
  },
  "confirmed": true
}
```

**Response:**
```json
{
  "execution_id": "exec-xyz789",
  "status": "in_progress",
  "message": "Scaling instance from t2.micro to t2.small...",
  "estimated_completion_time": "2026-02-20T10:15:00Z"
}
```

#### 2. Execute Stop Idle Deployments
```http
POST /api/ai/actions/execute/stop-idle-deployments
Authorization: Bearer {token}

{
  "recommendation_id": "stop-idle-abc",
  "parameters": {
    "deployment_ids": ["dep-1", "dep-2"],
    "reason": "Cost optimization"
  },
  "confirmed": true
}
```

#### 3. Execute Trigger Security Scan
```http
POST /api/ai/actions/execute/trigger-security-scan
Authorization: Bearer {token}

{
  "recommendation_id": "scan-dep-123-xyz",
  "parameters": {
    "deployment_id": "dep-123",
    "scan_type": "full"
  },
  "confirmed": false
}
```

#### 4. Get Execution Status
```http
GET /api/ai/actions/status/{execution_id}
Authorization: Bearer {token}
```

**Response:**
```json
{
  "execution_id": "exec-xyz789",
  "status": "completed",
  "action_type": "scale_instance",
  "progress_percent": 100,
  "message": "Instance successfully scaled to t2.small",
  "result": {
    "old_instance_type": "t2.micro",
    "new_instance_type": "t2.small",
    "downtime_seconds": 87
  },
  "created_at": "2026-02-20T10:10:00Z",
  "completed_at": "2026-02-20T10:12:27Z",
  "duration_seconds": 147.3
}
```

### Status Values

- `queued` - Action is queued, not started yet
- `in_progress` - Action is currently executing
- `completed` - Action finished successfully
- `failed` - Action failed with error

### Action Types

- `scale_instance` - Vertical scaling (change EC2 instance type)
- `stop_idle_deployments` - Stop multiple idle instances
- `trigger_security_scan` - Run Trivy security scan

---

## 🎓 Best Practices

### For Users

✅ **DO:**
- Review confirmation dialogs carefully before confirming
- Wait for actions to complete before executing another
- Check the impact (cost, downtime) before applying
- Monitor the progress bar during execution
- Verify results after completion

❌ **DON'T:**
- Click "Apply" multiple times rapidly
- Close browser during execution (action continues in background)
- Execute destructive actions without reviewing impact
- Ignore error messages

### For Developers

✅ **DO:**
- Always validate user input on backend
- Check authorization (user owns deployment)
- Log all actions to action_executions table
- Handle errors gracefully with user-friendly messages
- Test with real AWS credentials before production

❌ **DON'T:**
- Skip confirmation dialogs for destructive actions
- Execute actions synchronously (use async)
- Expose internal error messages to users
- Allow concurrent execution of same action

---

## 📊 Performance Benchmarks

| Metric | Target | Typical |
|--------|--------|---------|
| Action initiation | < 500ms | ~300ms |
| Status polling response | < 200ms | ~100ms |
| Scale instance (total) | 2-3 min | ~2.5 min |
| Stop idle deployments | 1-2 min | ~1.5 min |
| Trigger security scan | 4-6 min | ~5 min |
| Status polling frequency | 2 seconds | 2 seconds |
| Timeout | 10 minutes | 10 minutes |

---

## 🎉 Success Criteria

Your implementation is working correctly if:

✅ All 3 action types show "Apply" buttons
✅ Confirmation dialogs display for destructive actions
✅ Progress updates in real-time (0% → 100%)
✅ Actions complete successfully with "Applied ✓"
✅ Page auto-refreshes after completion
✅ Errors show user-friendly messages
✅ Database records all executions
✅ Cascade deletion works properly

---

**Need Help?**

1. Check backend logs: Look for `[ERROR]` messages
2. Check browser console: Press F12 → Console tab
3. Verify database: Run SQL queries above
4. Review this guide: Most issues covered in Troubleshooting

**Last Updated:** 2026-02-20
**Author:** Claude AI
**Version:** 1.0.0
