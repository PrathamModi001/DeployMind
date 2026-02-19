# 🚀 DeployMind - Quick Start Guide

**Get running in 5 minutes!**

---

## ✅ Prerequisites Checklist

Before starting, verify you have:

- [x] Python 3.13 installed
- [x] Node.js 18+ installed
- [x] Git installed
- [x] GitHub account
- [x] AWS account (for EC2 deployment)

---

## 🎯 Super Quick Start (2 Minutes)

### 1. Start Backend (Terminal 1)

```bash
cd E:\devops\deploymind\deploymind-web\backend
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected Output:**
```
[GITHUB] PyGithub successfully imported ✅
INFO: Uvicorn running on http://0.0.0.0:8000
```

**If you see errors:**
- `No module named 'github'` → PyGithub is not installed (we fixed this!)
- `deploymind-core not available` → This is OK (web app works independently)

### 2. Start Frontend (Terminal 2)

```bash
cd E:\devops\deploymind\deploymind-web\frontend
npm run dev
```

**Expected Output:**
```
▲ Next.js 15.1.6
- Local:        http://localhost:5000
✓ Ready in 2.3s
```

### 3. Test the App (Browser)

Open: http://localhost:5000

**You should see:**
- Login page with "Login with GitHub" button
- Click it → GitHub OAuth → Authorize → Dashboard

**If you're already logged in:**
- You'll see the dashboard immediately
- Click "New Deployment" to test the wizard

---

## 🧪 Quick Health Check

### Backend is Working
```bash
curl http://localhost:8000/health
```

**Expected:** `{"status": "healthy"}`

### GitHub Token is Saved
```bash
cd E:\devops\deploymind\deploymind-web\backend
python verify_token.py
```

**Expected:**
```
Username: PrathamModi001
Email: prathammodi001@gmail.com
[OK] GitHub Token: SET (gho_...)
```

### Repositories Loading
1. Go to: http://localhost:5000/dashboard/deployments/new
2. Click "Select repository" dropdown
3. You should see ALL 74 repositories
4. Search for "dish-manage-realtime"
5. It should appear in the list!

---

## 🎯 5-Minute Complete Test

### Test 1: GitHub Login (30 seconds)
1. Go to http://localhost:5000
2. Click "Login with GitHub"
3. Authorize DeployMind
4. You should see the dashboard

**Check backend logs:**
```
[OAUTH] Starting GitHub OAuth
[OAUTH] SUCCESS! Token for: <your-email>
```

### Test 2: Repository Browsing (1 minute)
1. Click "New Deployment"
2. Click "Select repository" dropdown
3. Verify you see all 74 repositories
4. Search for "dish" - should find dish-manage-realtime
5. Select a repository
6. Branch dropdown should populate
7. Select a branch

**Check backend logs:**
```
[GITHUB] search_user_repositories called for user_id=1
[GITHUB] Found user: PrathamModi001
[GITHUB] Successfully fetched 74 repositories
```

### Test 3: Deployment Wizard (2 minutes)
1. Continue through wizard:
   - Step 2: Select instance (t2.micro)
   - Step 3: Select strategy (Rolling)
   - Step 4: Add env vars (optional)
   - Step 5: Review configuration
2. Check that AI recommendations appear
3. Click "Deploy" (or skip if you don't want to deploy yet)

### Test 4: AI Insights (1 minute)
1. Click "AI Insights" in sidebar
2. Verify 5 cards appear:
   - Health Prediction
   - Anomaly Detection
   - Autoscaling Recommendations
   - Cost Analysis
   - Security Risk Score
3. Each should show data or "No data yet"

---

## 🔍 Troubleshooting

### Issue: "PyGithub not available"

**Solution:**
```bash
cd E:\devops\deploymind\deploymind-web\backend
notepad venv\pyvenv.cfg
```

Change:
```
include-system-site-packages = false
```
To:
```
include-system-site-packages = true
```

Then restart backend.

### Issue: "Only seeing 2 mock repositories"

**Check:**
1. Backend logs - should see "[GITHUB] PyGithub successfully imported"
2. If not, follow PyGithub fix above
3. Restart backend
4. Hard refresh browser (Ctrl+Shift+R)

### Issue: "Token not saved"

**Solution:**
1. Log out from the app
2. Log back in via GitHub
3. Run `python verify_token.py` to confirm
4. Should see "[OK] GitHub Token: SET"

### Issue: "Deployment fails"

**Check:**
1. Are you within AWS free tier limits?
2. Do you have AWS credentials configured?
3. Is the repository accessible?
4. Check backend logs for specific error

### Issue: "Frontend won't start"

**Solution:**
```bash
cd E:\devops\deploymind\deploymind-web\frontend
npm install
npm run dev
```

### Issue: "Backend won't start"

**Solution:**
```bash
cd E:\devops\deploymind\deploymind-web\backend
pip install -r requirements.txt
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📚 Full Testing Guide

For comprehensive testing of ALL features:

**See:** `FRONTEND_TESTING_GUIDE.md` - 200+ test cases

---

## 🎓 What to Test First

### Priority 1: Core Flow (Must Work)
1. ✅ Login with GitHub
2. ✅ Browse repositories (see all 74)
3. ✅ Select repository and branch
4. ✅ View AI recommendations

### Priority 2: Deployment
5. ✅ Create deployment (mock or real)
6. ✅ View deployment logs
7. ✅ Check deployment status

### Priority 3: AI Features
8. ✅ Health prediction
9. ✅ Anomaly detection
10. ✅ Cost analysis

### Priority 4: Management
11. ✅ Rollback deployment
12. ✅ View analytics
13. ✅ Manage env vars

---

## 🎯 Success Indicators

### You Know It's Working When:

**Backend:**
```
[GITHUB] PyGithub successfully imported ✅
[GITHUB] Authenticated as: PrathamModi001 ✅
[GITHUB] Successfully fetched 74 repositories ✅
```

**Frontend:**
```
✓ Login page loads
✓ Dashboard shows after GitHub login
✓ Repository dropdown shows all 74 repos
✓ Wizard steps 1-6 all accessible
✓ AI Insights page renders
```

**Database:**
```bash
python verify_token.py
# Output: [OK] GitHub Token: SET (gho_...)
```

---

## 🚀 Ready to Deploy a Real App?

Once you've tested the wizard flow, you can deploy a real application:

### Requirements:
1. Repository with a Dockerfile (or package.json for auto-detection)
2. AWS account with EC2 access
3. AWS credentials configured (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)

### Steps:
1. Go to "New Deployment"
2. Select your repository
3. Choose branch
4. Select t2.micro (free tier)
5. Choose Rolling strategy
6. Add environment variables
7. Click "Deploy"
8. Watch the progress:
   - Security Scan (30s)
   - Docker Build (1-2 min)
   - EC2 Deployment (1 min)
   - Health Checks (2 min)

**Total Time:** ~5 minutes

---

## 📊 What's Next?

After testing everything:

1. **Read the completion summary:**
   - `PROJECT_COMPLETE.md` - Full project overview

2. **Run comprehensive tests:**
   - `FRONTEND_TESTING_GUIDE.md` - 200+ test cases

3. **Deploy a real app:**
   - Use one of your 74 repositories
   - Follow the wizard
   - Watch it deploy!

4. **Explore AI features:**
   - Health prediction
   - Cost analysis
   - Autoscaling recommendations

5. **Optional - Production deployment:**
   - Docker containerization
   - CI/CD setup
   - Domain & SSL

---

## 🎉 You're Done!

If you can:
- ✅ Login with GitHub
- ✅ See all 74 repositories
- ✅ Navigate through the wizard
- ✅ View AI insights

**Then everything is working perfectly!** 🎊

---

## 📞 Quick Commands

### Start Everything
```bash
# Terminal 1: Backend
cd E:\devops\deploymind\deploymind-web\backend && python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd E:\devops\deploymind\deploymind-web\frontend && npm run dev
```

### Stop Everything
- Backend: Press Ctrl+C in Terminal 1
- Frontend: Press Ctrl+C in Terminal 2

### Restart After Code Changes
- Backend: Auto-reloads (--reload flag)
- Frontend: Auto-reloads (Next.js hot reload)

---

**Need Help?**
- Check `FRONTEND_TESTING_GUIDE.md` for detailed troubleshooting
- Check backend logs for `[GITHUB]`, `[OAUTH]`, `[DEPLOYMENT]` messages
- Check browser console (F12) for frontend errors

**Last Updated:** 2026-02-19
