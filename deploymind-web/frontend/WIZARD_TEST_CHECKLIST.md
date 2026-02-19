# Deployment Wizard - Test Checklist

Use this checklist to verify all wizard functionality works correctly.

## Pre-Test Setup

- [ ] Backend server running on `http://localhost:8000`
- [ ] Frontend server running on `http://localhost:5000`
- [ ] User logged in to dashboard
- [ ] AI endpoints accessible (optional, wizard works without)

## Test Cases

### 1. Navigation & Progress

#### Navigate to Wizard
- [ ] Click "New Deployment" button from deployments page
- [ ] Wizard page loads with step 1 (Repository)
- [ ] Progress bar shows 6 steps
- [ ] Current step (Repository) is highlighted

#### Step Navigation
- [ ] Back button is hidden on first step
- [ ] Click "Continue" without filling form → Button disabled
- [ ] Fill valid data → Button enabled
- [ ] Click "Continue" → Move to step 2
- [ ] Click "Back" → Return to step 1
- [ ] Progress bar updates correctly

---

### 2. Repository Step

#### Basic Input
- [ ] Repository field accepts text input
- [ ] Branch field accepts text input
- [ ] Commit SHA field accepts text input (optional)

#### Validation
- [ ] Enter "test" → Show validation error (invalid format)
- [ ] Enter "owner/repo" → Show green checkmark
- [ ] Empty repository → Continue button disabled
- [ ] Valid repository → Continue button enabled

#### Quick Select
- [ ] Click "main" badge → Branch populated with "main"
- [ ] Click "develop" badge → Branch changed to "develop"
- [ ] Click "staging" badge → Branch changed to "staging"

#### Continue
- [ ] Click Continue with valid data → Move to Instance step

---

### 3. Instance Step

#### AI Recommendation (if available)
- [ ] Purple recommendation card appears
- [ ] Shows recommended instance type
- [ ] Shows monthly cost estimate
- [ ] Shows AI reasoning text

#### Instance Type Selection
- [ ] 5 instance type cards displayed (t2.micro → t3.medium)
- [ ] Each card shows: CPU, memory, monthly cost
- [ ] Recommended instance has purple badge
- [ ] Click instance card → Card highlights
- [ ] Click different card → Previous card unhighlights

#### Manual Instance ID
- [ ] Enter instance ID → Instance type cards deselect
- [ ] Clear instance ID → Can select instance type again

#### Region Selection
- [ ] Dropdown shows 4 regions
- [ ] Select different region → Value updates

#### Continue
- [ ] No selection → Continue disabled
- [ ] Instance type selected → Continue enabled
- [ ] Instance ID entered → Continue enabled

---

### 4. Strategy Step

#### AI Recommendation (if available)
- [ ] Purple recommendation card appears
- [ ] Shows recommended strategy (ROLLING/BLUE_GREEN/CANARY)
- [ ] Shows reasoning text
- [ ] Shows risk level

#### Strategy Selection
- [ ] 3 strategy cards displayed
- [ ] Each shows: name, description, risk level, duration
- [ ] Recommended strategy has purple badge
- [ ] Click strategy → Card highlights
- [ ] Risk level color-coded correctly:
  - [ ] Very Low = Green
  - [ ] Low = Blue
  - [ ] Medium = Yellow

#### Features Display
- [ ] Rolling shows: Zero downtime, Automatic rollback, Health checks, Safe for production
- [ ] Blue/Green shows: Instant rollback, Full testing, 2x resources, Best for critical
- [ ] Canary shows: Gradual traffic shift, Early detection, A/B testing, Complex setup

#### Continue
- [ ] No selection → Continue disabled (default: rolling)
- [ ] Strategy selected → Continue enabled

---

### 5. Environment Variables Step

#### Quick Add
- [ ] Click "NODE_ENV" badge → Variable added with key "NODE_ENV"
- [ ] Click "API_KEY" badge → Variable added as secret (yellow lock icon)
- [ ] Multiple clicks → Multiple variables added

#### Add Variable Manually
- [ ] Click "+ Add Variable" → New empty row appears
- [ ] Enter key in uppercase → Accepts input
- [ ] Enter value → Accepts input
- [ ] Click key/lock icon → Toggles secret state

#### Secret Variables
- [ ] Secret variable shows password dots
- [ ] Click eye icon → Shows plain text
- [ ] Click eye-off icon → Hides text again
- [ ] Secret badge shows "This variable will be stored securely"

#### Remove Variable
- [ ] Click trash icon → Variable removed
- [ ] Last variable removed → "No variables" empty state shown

#### Continue
- [ ] Empty variables list → Continue enabled (variables optional)
- [ ] Variables added → Continue enabled

---

### 6. Review Step

#### Configuration Summary
- [ ] Repository card shows: owner/repo, branch, commit SHA (if provided)
- [ ] Instance card shows: instance type OR instance ID, region
- [ ] Strategy card shows: selected strategy (uppercase, underscores → spaces)
- [ ] Environment card shows: variable count, secret count

#### Security Options
- [ ] Security scan toggle ON by default
- [ ] Auto-rollback toggle ON by default
- [ ] Health check toggle ON by default
- [ ] Toggles work (click changes state)

#### Pre-deployment Checklist
- [ ] Shows 4 checkmarks (all green)
- [ ] If security scan enabled: Shows "Security scan will run" item

#### Warnings
- [ ] Turn OFF auto-rollback → Yellow warning appears
- [ ] Warning text: "Auto-rollback is disabled"
- [ ] Turn ON auto-rollback → Warning disappears

#### Deploy
- [ ] Click "Deploy Now 🚀" → Button shows loading spinner
- [ ] Button text changes to "Deploying..."
- [ ] Button disabled during deployment

---

### 7. Deployment Progress Step

#### Initial State
- [ ] Automatically advances to this step after clicking Deploy
- [ ] Shows deployment ID (format: deploy-YYYYMMDD-XXXXXX)
- [ ] Shows initial status badge

#### Phase Progress
- [ ] 4 phases displayed:
  - [ ] Security Scan (Shield icon)
  - [ ] Building (Hammer icon)
  - [ ] Deploying (Rocket icon)
  - [ ] Health Check (Activity icon)

#### Status Updates (polling every 2s)
- [ ] Pending phase: Grey circle icon, muted background
- [ ] In Progress phase: Blue spinner, pulsing background
- [ ] Completed phase: Green checkmark, green background
- [ ] Failed phase (if error): Red X, red background

#### Progress Bar
- [ ] Shows 0% initially
- [ ] Updates as phases complete (25%, 50%, 75%, 100%)
- [ ] Hides when deployment complete/failed

#### Success State
- [ ] Title shows "🎉 Deployment Successful!"
- [ ] Status badge green: "DEPLOYED"
- [ ] Green success card appears
- [ ] "View Details" button shown
- [ ] "Back to Deployments" button shown

#### Failure State
- [ ] Title shows "❌ Deployment Failed"
- [ ] Status badge red: "FAILED" / "BUILD_FAILED" / "SECURITY_FAILED"
- [ ] Red error card appears with reason
- [ ] "View Details" button shown
- [ ] "Back to Deployments" button shown

#### Actions
- [ ] Click "View Details" → Navigate to `/dashboard/deployments/{id}`
- [ ] Click "Back to Deployments" → Navigate to `/dashboard/deployments`

---

### 8. Edge Cases & Error Handling

#### Network Errors
- [ ] Disconnect network → Show error message (not crash)
- [ ] Reconnect → Wizard still functional

#### API Failures
- [ ] AI endpoint down → Wizard works without recommendations
- [ ] Deployment endpoint down → Show error, allow retry

#### Invalid Data
- [ ] Special characters in repo → Validation catches
- [ ] SQL injection in fields → Sanitized
- [ ] Very long input → Truncated or validated

#### Browser Compatibility
- [ ] Chrome/Edge → All features work
- [ ] Firefox → All features work
- [ ] Safari → All features work

#### Responsive Design
- [ ] Desktop (1920x1080) → Full layout
- [ ] Tablet (768x1024) → Adapted layout
- [ ] Mobile (375x667) → Mobile-friendly layout

---

## Results Summary

### Passed: ____ / 100+
### Failed: ____
### Blocked: ____

## Issues Found

| Issue | Step | Severity | Notes |
|-------|------|----------|-------|
|       |      |          |       |

## Sign-off

- [ ] All critical functionality works
- [ ] No blocking bugs
- [ ] Ready for production
- [ ] Documentation updated

**Tested By**: _________________
**Date**: _________________
**Version**: _________________
