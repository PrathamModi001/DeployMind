# 🚀 DeployMind - Quick Start Guide

> **AI-Powered Deployment Platform** - Ship faster with automated security, intelligent builds, and zero-downtime deployments.

---

## 📋 Prerequisites

- **Node.js** v20+ (for frontend)
- **Python** 3.11+ (for backend)
- **PostgreSQL** (Docker recommended)
- **Redis** (Docker recommended)

---

## ⚡ Quick Start (Copy-Paste Commands)

### **Option 1: Run Full Stack with Docker** (Recommended)

```bash
# Start PostgreSQL + Redis
docker-compose up -d postgres redis

# Wait 5 seconds for services to start
sleep 5

# Backend (FastAPI) - Terminal 1
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Frontend (Next.js) - Terminal 2
cd frontend
npm install
npm run dev
```

**Access**:
- 🎨 **Frontend**: http://localhost:3000
- 🔧 **Backend API**: http://localhost:8000
- 📚 **API Docs**: http://localhost:8000/docs

---

### **Option 2: Quick Commands (No Docker)**

**Backend**:
```bash
cd backend && python -m venv venv && venv\Scripts\activate && pip install -r requirements.txt && uvicorn api.main:app --reload --port 8000
```

**Frontend** (separate terminal):
```bash
cd frontend && npm install && npm run dev
```

---

## 🔑 GitHub OAuth Setup

The app uses **GitHub OAuth** for authentication. Credentials are already configured in `backend/.env`:

```env
GITHUB_CLIENT_ID=Ov23liKPJfe4x8vw6AKN
GITHUB_CLIENT_SECRET=9b7674533b4a18fb495f8ed51441a6aa2b73ab9b
GITHUB_REDIRECT_URI=http://localhost:3000/auth/callback
```

**Device Flow**: Enabled ✅

---

## 🎯 First Login

1. Go to **http://localhost:3000**
2. Click **"Continue with GitHub"**
3. Enjoy the **confetti celebration!** 🎉
4. Explore your dashboard

---

## 📦 Project Structure

```
deploymind/
├── backend/          # FastAPI backend
│   ├── api/          # REST API routes
│   ├── .env          # Environment variables (GitHub OAuth)
│   └── main.py       # FastAPI app
│
├── frontend/         # Next.js 15 frontend
│   ├── app/          # App Router pages
│   ├── components/   # UI components
│   └── lib/          # API client
│
├── docker-compose.yml  # PostgreSQL + Redis
└── QUICKSTART.md      # This file
```

---

## 🛠️ Development Workflow

### **Backend Development**

```bash
# Activate venv
cd backend
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Run with auto-reload
uvicorn api.main:app --reload --port 8000

# View API docs
open http://localhost:8000/docs
```

### **Frontend Development**

```bash
cd frontend

# Development server (hot reload)
npm run dev

# Build for production
npm run build

# Run production build
npm start

# Type checking
npm run type-check
```

---

## 🎨 UI Features

- ✅ **Railway-style** gradient deployment cards
- ✅ **Arc Browser-style** color-coded sidebar
- ✅ **Stripe-style** minimal login page
- ✅ **Linear-style** smooth animations
- ✅ **Vercel-style** deployment logs
- ✅ **Confetti** on successful login 🎊
- ✅ **Toast notifications** (Sonner)
- ✅ **Pricing page** with 3 tiers

---

## 🔧 Troubleshooting

### Backend won't start?
```bash
# Check if PostgreSQL is running
docker ps

# Restart services
docker-compose restart

# Check logs
docker-compose logs postgres redis
```

### Frontend build errors?
```bash
# Clear cache
rm -rf frontend/.next
rm -rf frontend/node_modules

# Reinstall dependencies
cd frontend
npm install
npm run build
```

### Port already in use?
```bash
# Kill process on port 8000
netstat -ano | findstr :8000  # Windows
# lsof -ti:8000 | xargs kill  # Linux/Mac

# Kill process on port 3000
netstat -ano | findstr :3000  # Windows
# lsof -ti:3000 | xargs kill  # Linux/Mac
```

---

## 📚 Useful Commands

### Docker
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Rebuild services
docker-compose up -d --build
```

### Database
```bash
# Connect to PostgreSQL
docker exec -it deploymind-postgres psql -U admin -d deploymind

# View tables
\dt

# Exit
\q
```

### API Testing
```bash
# Test backend health
curl http://localhost:8000/health

# Get GitHub OAuth URL
curl http://localhost:8000/api/auth/github

# View API docs
curl http://localhost:8000/openapi.json
```

---

## 🚀 Production Deployment

### Build Frontend
```bash
cd frontend
npm run build
npm start  # Runs on port 3000
```

### Run Backend
```bash
cd backend
source venv/bin/activate
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### Environment Variables (Production)
```env
# Backend .env
DATABASE_URL=postgresql://user:pass@prod-db:5432/deploymind
REDIS_URL=redis://prod-redis:6379
JWT_SECRET=change-this-to-secure-random-string
GITHUB_CLIENT_ID=prod_github_client_id
GITHUB_CLIENT_SECRET=prod_github_client_secret
GITHUB_REDIRECT_URI=https://yourdomain.com/auth/callback
```

---

## 🎯 Next Steps

1. **Explore the Dashboard** - View mock deployment data
2. **Check out the Pricing Page** - `/pricing`
3. **Test GitHub OAuth** - Login flow with confetti
4. **View API Docs** - http://localhost:8000/docs
5. **Connect Real AWS** - Replace mock data with real deployments

---

## 📖 Documentation

- **Architecture**: `docs/architecture/clean-architecture.md`
- **Development Guide**: `CLAUDE.md`
- **Completion Roadmap**: `COMPLETION_ROADMAP.md`
- **UI Overhaul**: `UI_OVERHAUL_ROADMAP.md`

---

## ❤️ Stack

**Frontend**:
- Next.js 15 (App Router)
- TypeScript
- Tailwind CSS v4
- shadcn/ui
- Framer Motion
- TanStack Query
- Sonner (toasts)
- canvas-confetti

**Backend**:
- FastAPI
- PostgreSQL
- Redis
- JWT Auth
- GitHub OAuth

---

**Happy Deploying! 🚀**
