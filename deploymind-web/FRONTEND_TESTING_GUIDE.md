# 🧪 DeployMind Frontend Testing Guide

**Complete manual testing checklist to verify EVERYTHING works.**

Last Updated: 2026-02-19

---

## 📋 Pre-Testing Checklist

### Backend Status
```bash
# 1. Verify backend is running
curl http://localhost:8000/health
# Expected: {"status": "healthy"}

# 2. Verify GitHub token is saved
cd E:\devops\deploymind\deploymind-web\backend
python verify_token.py
# Expected: "[OK] GitHub Token: SET (gho_...)"

# 3. Check backend logs
# Look for: "[GITHUB] PyGithub successfully imported"
```

### Frontend Status
```bash
# Verify frontend is running
# Browser: http://localhost:5000
# Expected: Login page or Dashboard (if already logged in)
```

---

## 🔐 1. Authentication Testing

### 1.1 GitHub OAuth Login
**URL:** `http://localhost:5000`

| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Click "Login with GitHub" | Redirects to GitHub authorization | ☐ |
| 2 | Authorize DeployMind | Redirects back to dashboard | ☐ |
| 3 | Check user profile (top right) | Shows your GitHub avatar & username | ☐ |
| 4 | Verify token saved | Backend logs: "Authenticated as: PrathamModi001" | ☐ |

**Backend Logs to Check:**
```
[OAUTH] Starting GitHub OAuth
[OAUTH] Existing user: <your-email>
[OAUTH] SUCCESS! Token for: <your-email>
```

### 1.2 Session Persistence
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Refresh page (F5) | Stays logged in, no redirect | ☐ |
| 2 | Close tab, reopen `localhost:5000` | Still logged in | ☐ |
| 3 | Check `/api/auth/me` | Returns user info (use browser DevTools Network tab) | ☐ |

### 1.3 Logout
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Click user menu → Logout | Redirects to login page | ☐ |
| 2 | Try accessing `/dashboard` | Redirects to login | ☐ |
| 3 | Check localStorage | JWT token removed | ☐ |

---

## 📦 2. GitHub Integration Testing

### 2.1 Repository Dropdown
**URL:** `http://localhost:5000/dashboard/deployments/new`

| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Click "Select repository" dropdown | Shows loading spinner | ☐ |
| 2 | Wait for repos to load | Shows ALL 74 of your repositories | ☐ |
| 3 | Verify specific repo | Find "PrathamModi001/dish-manage-realtime" | ☐ |
| 4 | Verify repo data | Each repo shows: name, description, language | ☐ |
| 5 | Check sorting | Repos sorted by recently updated | ☐ |

**Backend Logs to Check:**
```
[GITHUB] search_user_repositories called for user_id=1, query=''
[GITHUB] Found user: PrathamModi001 (github_id=72181828)
[GITHUB] User token status: SET (length=40)
[GITHUB] Authenticated as: PrathamModi001
[GITHUB] Successfully fetched 74 repositories for user PrathamModi001
[GITHUB] Returning 74 repositories
[GITHUB] First 3 repos: ['PrathamModi001/repo1', 'PrathamModi001/repo2', ...]
```

### 2.2 Repository Search
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Type "dish" in search box | Filters to repos containing "dish" | ☐ |
| 2 | Type "realtime" | Shows "dish-manage-realtime" | ☐ |
| 3 | Clear search | Shows all repos again | ☐ |
| 4 | Type non-existent repo | Shows "No repository found" | ☐ |

### 2.3 Branch Selection
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Select a repository | Branch dropdown enables | ☐ |
| 2 | Click branch dropdown | Shows loading spinner | ☐ |
| 3 | Wait for branches | Shows all branches (main, develop, etc.) | ☐ |
| 4 | Check default branch | "main" or "master" is pre-selected | ☐ |
| 5 | Select different branch | Updates selected branch | ☐ |

**Backend Logs to Check:**
```
[GITHUB] Getting branches for repository: PrathamModi001/dish-manage-realtime
[GITHUB] Found 3 branches
```

### 2.4 Framework Detection
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Select Node.js repo (with package.json) | Shows "Detected: Node.js" | ☐ |
| 2 | Select Python repo (with requirements.txt) | Shows "Detected: Python" | ☐ |
| 3 | Select repo with Dockerfile | Shows "Dockerfile found ✓" | ☐ |

### 2.5 Manual Fallback
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Click "Enter manually" link | Shows manual input fields | ☐ |
| 2 | Enter "owner/repo" format | Accepts input | ☐ |
| 3 | Enter invalid format (no slash) | Shows validation error | ☐ |
| 4 | Switch back to dropdown | Dropdown works again | ☐ |

---

## 🚀 3. Deployment Wizard Testing

### 3.1 Step 1: Repository Selection
**Already tested above in GitHub Integration section.**

Click "Next" to proceed.

### 3.2 Step 2: Instance Selection
**URL:** `http://localhost:5000/dashboard/deployments/new` (Step 2)

| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | View instance cards | Shows 3 instance types: t2.micro, t2.small, t2.medium | ☐ |
| 2 | Check AI recommendation | One card marked "Recommended" with reasoning | ☐ |
| 3 | Verify pricing | Shows $/hour for each instance | ☐ |
| 4 | Verify specs | Shows vCPU, Memory, Network performance | ☐ |
| 5 | Click an instance card | Card highlights/selects | ☐ |
| 6 | Try clicking "Next" without selection | Shows validation error | ☐ |
| 7 | Select instance & click "Next" | Proceeds to Step 3 | ☐ |

**AI Recommendation Check:**
- Should show reasoning like: "Recommended for Node.js applications with moderate traffic"
- Based on detected framework and repository size

### 3.3 Step 3: Deployment Strategy
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | View strategy cards | Shows 3 strategies: Rolling, Blue/Green, Canary | ☐ |
| 2 | Check AI recommendation | One strategy marked "Recommended" | ☐ |
| 3 | Read Rolling description | Shows: "Zero-downtime updates, gradual rollout" | ☐ |
| 4 | Read Blue/Green description | Shows: "Instant rollback, full environment swap" | ☐ |
| 5 | Read Canary description | Shows: "Test with small traffic %, gradual increase" | ☐ |
| 6 | Select a strategy | Card highlights | ☐ |
| 7 | Click "Next" without selection | Shows validation error | ☐ |
| 8 | Select strategy & click "Next" | Proceeds to Step 4 | ☐ |

**AI Recommendation Check:**
- New apps → Rolling Update
- Production apps → Blue/Green
- High-risk changes → Canary

### 3.4 Step 4: Environment Variables
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Click "Add Variable" | Adds new key/value row | ☐ |
| 2 | Enter key: "PORT" | Accepts input | ☐ |
| 3 | Enter value: "3000" | Accepts input | ☐ |
| 4 | Toggle "Secret" switch | Input becomes password field (dots) | ☐ |
| 5 | Click eye icon on secret | Reveals secret value | ☐ |
| 6 | Add multiple variables | All variables saved | ☐ |
| 7 | Delete a variable (trash icon) | Variable removed | ☐ |
| 8 | Leave key empty | Shows validation error on Next | ☐ |
| 9 | Fill all required fields | "Next" button works | ☐ |
| 10 | Click "Next" | Proceeds to Step 5 | ☐ |

**Common Environment Variables to Test:**
- `PORT=3000`
- `NODE_ENV=production`
- `DATABASE_URL=postgres://...` (mark as secret)
- `API_KEY=sk_test_...` (mark as secret)

### 3.5 Step 5: Review & Deploy
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | View configuration summary | Shows all selections from previous steps | ☐ |
| 2 | Verify repository | Shows correct owner/repo/branch | ☐ |
| 3 | Verify instance | Shows selected instance type | ☐ |
| 4 | Verify strategy | Shows selected deployment strategy | ☐ |
| 5 | Verify environment vars | Shows count (e.g., "4 variables") | ☐ |
| 6 | Check security settings | Shows checkboxes for scanning/monitoring | ☐ |
| 7 | Enable all security features | All checkboxes checked | ☐ |
| 8 | Click "Deploy Application" | Proceeds to Step 6 (deployment progress) | ☐ |

**Security Settings:**
- ✅ Run security scan before deployment
- ✅ Enable health monitoring
- ✅ Auto-rollback on failure

### 3.6 Step 6: Deployment Progress
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Deployment starts | Shows progress bar at 0% | ☐ |
| 2 | Phase 1: Security Scanning | Progress updates, shows "Scanning..." | ☐ |
| 3 | Security scan completes | Shows ✓ or vulnerabilities found | ☐ |
| 4 | Phase 2: Building | Shows "Building Docker image..." | ☐ |
| 5 | Build completes | Shows image size and ✓ | ☐ |
| 6 | Phase 3: Deploying | Shows "Deploying to EC2..." | ☐ |
| 7 | Deployment completes | Shows instance ID and IP | ☐ |
| 8 | Phase 4: Health Checks | Shows "Running health checks..." | ☐ |
| 9 | Health checks pass | Shows ✓ and "Application is healthy" | ☐ |
| 10 | View logs in real-time | Logs stream in deployment log panel | ☐ |
| 11 | Deployment finishes | Shows "Deployment Successful!" | ☐ |
| 12 | Click "View Deployment" | Redirects to deployment details page | ☐ |

**Progress Phases:**
1. 🔍 Security Scanning (0-25%)
2. 🔨 Building Image (25-50%)
3. 🚀 Deploying (50-75%)
4. ❤️ Health Checks (75-100%)

**Backend Logs to Check:**
```
[DEPLOYMENT] Creating deployment for user 1
[SECURITY] Starting security scan
[BUILD] Building Docker image
[DEPLOY] Deploying to EC2
[HEALTH] Running health checks
[DEPLOYMENT] Deployment completed successfully
```

### 3.7 Error Handling
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Deployment fails (simulate) | Shows error message | ☐ |
| 2 | Check error details | Shows specific error (e.g., "Security scan failed: 5 CRITICAL vulnerabilities") | ☐ |
| 3 | Click "View Details" | Shows full error log | ☐ |
| 4 | Click "Retry" button | Restarts deployment from beginning | ☐ |
| 5 | Click "Cancel" | Returns to wizard step 1 | ☐ |

---

## 🤖 4. AI Insights Testing

### 4.1 Health Prediction
**URL:** `http://localhost:5000/dashboard/ai-insights`

| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | View "Health Prediction" card | Shows failure probability (0-100%) | ☐ |
| 2 | Check risk level | Shows: Low (<30%), Medium (30-70%), High (>70%) | ☐ |
| 3 | View confidence score | Shows AI confidence (0-100%) | ☐ |
| 4 | Read contributing factors | Lists specific issues (e.g., "High error rate", "Memory leaks") | ☐ |
| 5 | View predictions chart | Shows trend over time (if data available) | ☐ |

**API Call to Check:**
```
GET /api/ai/health-prediction/{deployment_id}
```

**Backend Logs:**
```
[AI] Health prediction requested for deployment_id=1
[AI] Analyzing 150 health check records
[AI] Failure probability: 65% (Medium risk)
```

### 4.2 Anomaly Detection
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | View "Anomaly Detection" card | Shows anomaly status | ☐ |
| 2 | Check CPU anomalies | Shows spikes or unusual patterns | ☐ |
| 3 | Check Memory anomalies | Shows memory leaks or sudden increases | ☐ |
| 4 | Check Network anomalies | Shows unusual traffic patterns | ☐ |
| 5 | View anomaly timeline | Shows when anomalies occurred | ☐ |
| 6 | Click on anomaly | Shows detailed metrics | ☐ |

**API Call to Check:**
```
GET /api/ai/anomaly-detection/{deployment_id}
```

**Expected Response:**
```json
{
  "anomalies_detected": true,
  "anomaly_count": 3,
  "anomalies": [
    {
      "type": "cpu_spike",
      "severity": "medium",
      "timestamp": "2026-02-19T10:30:00Z",
      "description": "CPU usage spiked to 95%"
    }
  ]
}
```

### 4.3 Autoscaling Recommendations
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | View "Autoscaling" card | Shows scaling recommendation | ☐ |
| 2 | Check recommendation type | Shows: Horizontal (add instances) or Vertical (larger instance) | ☐ |
| 3 | View current state | Shows current instance type and count | ☐ |
| 4 | View recommended state | Shows suggested instance type/count | ☐ |
| 5 | Check cost impact | Shows estimated cost change ($/month) | ☐ |
| 6 | Read reasoning | Shows why scaling is recommended | ☐ |
| 7 | Click "Apply Recommendation" | Shows confirmation dialog | ☐ |

**API Call:**
```
GET /api/ai/autoscaling-recommendation/{deployment_id}
```

**Expected Response:**
```json
{
  "recommendation_type": "horizontal",
  "current_instances": 1,
  "recommended_instances": 3,
  "reasoning": "CPU consistently above 80% during peak hours",
  "estimated_cost_change": 45.50,
  "confidence": 0.85
}
```

### 4.4 Cost Analysis
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | View "Cost Analysis" card | Shows current spending | ☐ |
| 2 | Check monthly spend | Shows current month cost | ☐ |
| 3 | View spending trend | Shows graph (last 3 months) | ☐ |
| 4 | Check forecast | Shows predicted next month cost | ☐ |
| 5 | View optimization suggestions | Lists ways to reduce costs | ☐ |
| 6 | Check savings potential | Shows estimated savings ($/month) | ☐ |
| 7 | Click suggestion | Shows detailed optimization steps | ☐ |

**API Call:**
```
GET /api/ai/cost-analysis?user_id=1
```

**Expected Response:**
```json
{
  "current_month_spend": 127.50,
  "forecast_next_month": 145.00,
  "trend": "increasing",
  "optimization_suggestions": [
    {
      "action": "Downgrade 2 t2.medium instances to t2.small",
      "impact": "Reduce performance by 10%",
      "savings_usd": 30.50
    }
  ]
}
```

### 4.5 Security Risk Scoring
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | View "Security Risk" card | Shows risk score (0-100) | ☐ |
| 2 | Check risk level | Shows color: Green (<30), Yellow (30-70), Red (>70) | ☐ |
| 3 | View vulnerability breakdown | Shows CRITICAL, HIGH, MEDIUM, LOW counts | ☐ |
| 4 | Check CVE list | Shows specific CVE IDs | ☐ |
| 5 | Click CVE | Opens CVE details page | ☐ |
| 6 | View remediation steps | Shows how to fix vulnerabilities | ☐ |

**API Call:**
```
GET /api/ai/security-risk/{deployment_id}
```

**Expected Response:**
```json
{
  "risk_score": 65,
  "risk_level": "medium",
  "vulnerability_counts": {
    "CRITICAL": 2,
    "HIGH": 5,
    "MEDIUM": 12,
    "LOW": 8
  },
  "top_vulnerabilities": [
    {
      "cve_id": "CVE-2024-1234",
      "severity": "CRITICAL",
      "package": "openssl",
      "fixed_version": "3.0.10"
    }
  ]
}
```

---

## 📊 5. Dashboard Testing

### 5.1 Dashboard Overview
**URL:** `http://localhost:5000/dashboard`

| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | View dashboard | Shows overview cards | ☐ |
| 2 | Check total deployments | Shows count | ☐ |
| 3 | Check active deployments | Shows running deployment count | ☐ |
| 4 | Check failed deployments | Shows failure count | ☐ |
| 5 | View recent deployments list | Shows last 5 deployments | ☐ |
| 6 | View deployment status | Shows status badges (Running, Failed, Success) | ☐ |

### 5.2 Deployments List
**URL:** `http://localhost:5000/dashboard/deployments`

| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | View all deployments | Shows table/grid of deployments | ☐ |
| 2 | Check columns | Shows: Repository, Status, Strategy, Instance, Created | ☐ |
| 3 | Sort by status | Sorts deployments | ☐ |
| 4 | Sort by date | Sorts by created_at | ☐ |
| 5 | Filter by status | Shows only selected status | ☐ |
| 6 | Search by repository | Filters by repo name | ☐ |
| 7 | Click deployment row | Opens deployment details | ☐ |

### 5.3 Deployment Details
**URL:** `http://localhost:5000/dashboard/deployments/{id}`

| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | View deployment details | Shows complete deployment info | ☐ |
| 2 | Check repository info | Shows owner/repo/branch/commit SHA | ☐ |
| 3 | Check instance info | Shows instance ID, type, IP address | ☐ |
| 4 | Check status timeline | Shows deployment phases with timestamps | ☐ |
| 5 | View environment variables | Shows configured env vars (secrets hidden) | ☐ |
| 6 | View security scan results | Shows vulnerability counts | ☐ |
| 7 | View build logs | Shows Docker build output | ☐ |
| 8 | View deployment logs | Shows deployment process logs | ☐ |
| 9 | View health check results | Shows health check history | ☐ |

### 5.4 Deployment Actions
| Step | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| 1 | Click "Restart" button | Shows confirmation dialog | ☐ |
| 2 | Confirm restart | Deployment restarts | ☐ |
| 3 | Click "Rollback" button | Shows rollback confirmation | ☐ |
| 4 | Confirm rollback | Rolls back to previous version | ☐ |
| 5 | Click "Stop" button | Stops deployment | ☐ |
| 6 | Click "Delete" button | Shows deletion warning | ☐ |
| 7 | Confirm delete | Deployment deleted, redirects to list | ☐ |

---

## 🔍 6. Edge Cases & Error Handling

### 6.1 Network Errors
| Scenario | Action | Expected Result | ✅ |
|----------|--------|----------------|---|
| Backend offline | Refresh page | Shows "Unable to connect" error | ☐ |
| Slow network | Load any page | Shows loading spinner | ☐ |
| Timeout | Wait >30s on API call | Shows timeout error | ☐ |
| Retry after error | Click "Retry" | Reloads data | ☐ |

### 6.2 Authentication Errors
| Scenario | Action | Expected Result | ✅ |
|----------|--------|----------------|---|
| Expired JWT | Wait 30 min, refresh | Redirects to login | ☐ |
| Invalid token | Manually edit localStorage token | Redirects to login | ☐ |
| GitHub OAuth fails | Cancel GitHub auth | Shows error message | ☐ |

### 6.3 Validation Errors
| Scenario | Action | Expected Result | ✅ |
|----------|--------|----------------|---|
| Empty repository | Try to proceed without selecting repo | Shows "Repository is required" | ☐ |
| Invalid env var key | Enter key with spaces | Shows "Invalid key format" | ☐ |
| Duplicate env var | Add same key twice | Shows "Duplicate key" error | ☐ |

### 6.4 GitHub API Errors
| Scenario | Action | Expected Result | ✅ |
|----------|--------|----------------|---|
| Rate limit exceeded | Make many API calls | Shows rate limit error | ☐ |
| Repository not found | Enter non-existent repo manually | Shows 404 error | ☐ |
| No permission | Select private repo (if no access) | Shows permission error | ☐ |

### 6.5 Deployment Errors
| Scenario | Action | Expected Result | ✅ |
|----------|--------|----------------|---|
| Security scan fails | Deploy repo with critical CVEs | Shows failure, suggests fixes | ☐ |
| Build fails | Deploy repo with Dockerfile errors | Shows build logs with error | ☐ |
| Health check fails | Deploy app that crashes | Auto-rollback triggered | ☐ |
| EC2 quota exceeded | Deploy with no available instances | Shows quota error | ☐ |

---

## 🎨 7. UI/UX Testing

### 7.1 Responsive Design
| Screen Size | Action | Expected Result | ✅ |
|-------------|--------|----------------|---|
| Desktop (1920x1080) | View all pages | Layout looks good | ☐ |
| Laptop (1366x768) | View all pages | Layout adapts | ☐ |
| Tablet (768x1024) | View all pages | Mobile nav appears | ☐ |
| Mobile (375x667) | View all pages | All features accessible | ☐ |

### 7.2 Animations & Transitions
| Element | Action | Expected Result | ✅ |
|---------|--------|----------------|---|
| Wizard steps | Click Next | Smooth slide transition | ☐ |
| Dropdowns | Open/close | Smooth fade in/out | ☐ |
| Progress bar | Deployment | Smooth progress animation | ☐ |
| Toast notifications | Success/error | Slide in from top-right | ☐ |
| Loading spinners | Any loading state | Smooth rotation | ☐ |

### 7.3 Accessibility
| Test | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| Keyboard navigation | Tab through wizard | All elements focusable | ☐ |
| Enter key | Press Enter on buttons | Triggers action | ☐ |
| Escape key | Press Esc on modal | Closes modal | ☐ |
| Focus indicators | Tab to element | Shows focus ring | ☐ |
| ARIA labels | Screen reader test | Elements properly labeled | ☐ |

### 7.4 Dark Mode (if implemented)
| Test | Action | Expected Result | ✅ |
|------|--------|----------------|---|
| Toggle dark mode | Click theme toggle | Switches to dark theme | ☐ |
| Persistence | Refresh page | Theme persists | ☐ |
| All pages | Navigate all pages | Consistent dark theme | ☐ |

---

## 📝 8. Data Persistence Testing

### 8.1 Wizard State
| Scenario | Action | Expected Result | ✅ |
|----------|--------|----------------|---|
| Fill Step 1 & 2 | Refresh page | Progress lost (expected) | ☐ |
| Browser back button | Click back in wizard | Returns to previous step | ☐ |
| Browser forward | Click forward | Goes to next step | ☐ |

### 8.2 Form Data
| Scenario | Action | Expected Result | ✅ |
|----------|--------|----------------|---|
| Enter env vars | Go back to Step 3, then forward | Env vars still filled | ☐ |
| Select instance | Change strategy, go back | Instance still selected | ☐ |

---

## 🚨 9. Critical User Flows

### 9.1 Complete Deployment Flow (Happy Path)
**Time to Complete: ~5 minutes**

| Step | Action | Duration | ✅ |
|------|--------|----------|---|
| 1 | Login with GitHub | 10s | ☐ |
| 2 | Navigate to New Deployment | 5s | ☐ |
| 3 | Select repository (dish-manage-realtime) | 15s | ☐ |
| 4 | Select branch (main) | 5s | ☐ |
| 5 | Click Next | 1s | ☐ |
| 6 | Select instance (t2.micro) | 5s | ☐ |
| 7 | Click Next | 1s | ☐ |
| 8 | Select strategy (Rolling) | 5s | ☐ |
| 9 | Click Next | 1s | ☐ |
| 10 | Add env vars (PORT=3000, NODE_ENV=production) | 30s | ☐ |
| 11 | Click Next | 1s | ☐ |
| 12 | Review configuration | 15s | ☐ |
| 13 | Enable all security features | 5s | ☐ |
| 14 | Click Deploy | 1s | ☐ |
| 15 | Watch deployment progress | 2-3 min | ☐ |
| 16 | Verify success message | 5s | ☐ |
| 17 | Click "View Deployment" | 5s | ☐ |
| 18 | Verify deployment is running | 10s | ☐ |

**Total Time: ~5 minutes**

### 9.2 View AI Insights Flow
| Step | Action | Duration | ✅ |
|------|--------|----------|---|
| 1 | Navigate to AI Insights | 5s | ☐ |
| 2 | View health prediction | 10s | ☐ |
| 3 | View anomaly detection | 10s | ☐ |
| 4 | View autoscaling recommendations | 15s | ☐ |
| 5 | View cost analysis | 15s | ☐ |
| 6 | View security risk score | 10s | ☐ |

**Total Time: ~1 minute**

### 9.3 Rollback Flow
| Step | Action | Duration | ✅ |
|------|--------|----------|---|
| 1 | Go to deployment details | 5s | ☐ |
| 2 | Click "Rollback" button | 2s | ☐ |
| 3 | Confirm rollback | 2s | ☐ |
| 4 | Watch rollback progress | 1-2 min | ☐ |
| 5 | Verify previous version running | 10s | ☐ |

**Total Time: ~2 minutes**

---

## 📊 10. Performance Testing

### 10.1 Page Load Times
| Page | Expected Load Time | Actual | ✅ |
|------|-------------------|--------|---|
| Login | < 1s | __ | ☐ |
| Dashboard | < 2s | __ | ☐ |
| Deployments List | < 2s | __ | ☐ |
| Deployment Details | < 2s | __ | ☐ |
| AI Insights | < 3s | __ | ☐ |
| New Deployment (Step 1) | < 2s | __ | ☐ |

### 10.2 API Response Times
| Endpoint | Expected Time | Actual | ✅ |
|----------|--------------|--------|---|
| GET /api/auth/me | < 100ms | __ | ☐ |
| GET /api/github/repositories | < 2s | __ | ☐ |
| POST /api/deployments | < 500ms | __ | ☐ |
| GET /api/deployments | < 300ms | __ | ☐ |
| GET /api/ai/health-prediction/{id} | < 1s | __ | ☐ |

**How to Measure:**
- Open DevTools → Network tab
- Check request timing

---

## ✅ Testing Summary

### Overall Status
- [ ] Authentication: __ / __ tests passed
- [ ] GitHub Integration: __ / __ tests passed
- [ ] Deployment Wizard: __ / __ tests passed
- [ ] AI Insights: __ / __ tests passed
- [ ] Dashboard: __ / __ tests passed
- [ ] Edge Cases: __ / __ tests passed
- [ ] UI/UX: __ / __ tests passed
- [ ] Critical Flows: __ / __ tests passed

### Blocker Issues
List any critical issues that prevent core functionality:

1.
2.
3.

### Minor Issues
List non-critical issues:

1.
2.
3.

### Suggestions
List UX improvements or features:

1.
2.
3.

---

## 🐛 Bug Report Template

If you find a bug, report it with this format:

```markdown
### Bug: [Short description]

**Severity:** Critical / Major / Minor

**Steps to Reproduce:**
1.
2.
3.

**Expected Result:**


**Actual Result:**


**Screenshots:**
[Attach if applicable]

**Console Errors:**
[Paste console errors]

**Backend Logs:**
[Paste relevant logs]

**Environment:**
- Browser:
- OS:
- Backend version:
- Frontend version:
```

---

## 📞 Support

If you encounter issues:

1. **Check backend logs** for `[GITHUB]`, `[OAUTH]`, `[DEPLOYMENT]` messages
2. **Check browser console** (F12 → Console tab) for errors
3. **Verify backend is running** on `http://localhost:8000`
4. **Verify frontend is running** on `http://localhost:5000`
5. **Check GitHub token is saved** with `python verify_token.py`

---

**Last Updated:** 2026-02-19
**Tested By:** ___________
**Test Date:** ___________
**Overall Status:** ☐ PASS  ☐ FAIL  ☐ PARTIAL
