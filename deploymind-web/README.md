# DeployMind Web

Full-stack web application with FastAPI backend and Next.js frontend.

## Features

- **FastAPI Backend**: Modern Python web framework with async support
- **Next.js Frontend**: React framework with TypeScript
- **GitHub OAuth**: Real GitHub authentication flow
- **JWT Authentication**: Secure token-based auth
- **Real-time Monitoring**: Deployment status and analytics
- **Modern UI**: Shadcn/UI components with Tailwind CSS

## Quick Start

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Start database (from parent directory)
cd .. && docker-compose up -d postgres redis

# Run backend
cd backend
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

Backend runs on: http://localhost:8000
API docs: http://localhost:8000/api/docs

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local if needed

# Run development server
npm run dev
```

Frontend runs on: http://localhost:5000

## Project Structure

```
deploymind-web/
├── backend/                # FastAPI backend
│   ├── api/
│   │   ├── routes/        # API endpoints
│   │   ├── models/        # Database models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── middleware/    # Auth middleware
│   │   └── utils/         # JWT, helpers
│   └── database/          # Database connection
│
├── frontend/              # Next.js frontend
│   ├── app/              # Pages (login, dashboard, etc.)
│   ├── components/       # React components
│   └── lib/              # API client, utilities
│
└── docker-compose.yml    # Services orchestration
```

## GitHub OAuth Setup

1. Create OAuth App at: https://github.com/settings/developers
2. Set Authorization callback URL: `http://localhost:5000/auth/callback`
3. Copy Client ID and Secret to `backend/.env`

## Environment Variables

### Backend (.env)
```bash
DATABASE_URL=postgresql://admin:password@localhost:5432/deploymind
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-secret-key-here
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GITHUB_REDIRECT_URI=http://localhost:5000/auth/callback
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Testing

### Backend
```bash
cd backend
pytest tests/ -v
```

### Frontend
```bash
cd frontend
npm run build  # Check for build errors
npm run lint   # Check for linting errors
```

## Docker Deployment

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop all services
docker-compose down
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## Frontend Pages

- `/login` - GitHub OAuth login
- `/dashboard` - Main dashboard
- `/pricing` - Pricing page (placeholder)
