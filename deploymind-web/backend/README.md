# DeployMind Backend API

REST API for the DeployMind deployment platform.

## Tech Stack

- **FastAPI** - Modern Python web framework
- **Pydantic** - Data validation and settings
- **JWT** - Authentication
- **SQLAlchemy** - ORM (database integration)
- **PostgreSQL** - Database
- **Redis** - Caching

## Project Structure

```
backend/
├── api/
│   ├── routes/           # API endpoints
│   │   ├── auth.py       # Authentication
│   │   ├── deployments.py # Deployment management
│   │   └── analytics.py   # Analytics & metrics
│   ├── middleware/        # Custom middleware
│   │   └── auth.py        # JWT authentication
│   ├── models/            # Database models
│   │   └── user.py        # User model
│   ├── schemas/           # Pydantic schemas
│   │   ├── auth.py        # Auth schemas
│   │   └── deployment.py  # Deployment schemas
│   ├── utils/             # Utilities
│   │   └── jwt.py         # JWT utilities
│   ├── config.py          # Configuration
│   └── main.py            # FastAPI app
├── tests/                 # API tests
│   └── test_api.py
├── requirements.txt       # Dependencies
├── .env.example           # Environment variables template
└── README.md              # This file
```

## Setup

### 1. Create Virtual Environment

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Run API Server

```bash
# Development mode with auto-reload
python -m api.main

# Or use uvicorn directly
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- http://localhost:8000
- API Docs (Swagger): http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login and get JWT token
- `GET /api/auth/me` - Get current user info
- `POST /api/auth/logout` - Logout

### Deployments
- `GET /api/deployments` - List deployments (paginated)
- `GET /api/deployments/{id}` - Get deployment details
- `POST /api/deployments` - Create new deployment
- `GET /api/deployments/{id}/logs` - Get deployment logs
- `POST /api/deployments/{id}/rollback` - Rollback deployment

### Analytics
- `GET /api/analytics/overview` - Get analytics overview
- `GET /api/analytics/timeline` - Get deployment timeline
- `GET /api/analytics/performance` - Get performance metrics

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=api --cov-report=html

# Run specific test file
pytest tests/test_api.py -v
```

## Default Credentials

For testing, use the default admin account:
- **Email**: admin@deploymind.io
- **Password**: admin123

## Authentication

All protected endpoints require a JWT token:

```bash
# 1. Login to get token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@deploymind.io", "password": "admin123"}'

# 2. Use token in subsequent requests
curl http://localhost:8000/api/deployments \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

## Development Notes

- Mock data is currently used for users and deployments
- Database integration is planned for production
- WebSocket support for real-time updates coming soon
- CORS is configured for `http://localhost:3000` (frontend)

## Next Steps

- [ ] Integrate with existing deployment workflow
- [ ] Add WebSocket support for real-time updates
- [ ] Connect to PostgreSQL database
- [ ] Add Redis caching
- [ ] Implement rate limiting
- [ ] Add request/response logging
- [ ] Deploy to production
