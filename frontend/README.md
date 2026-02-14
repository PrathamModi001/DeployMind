# DeployMind Frontend

Modern Next.js 15 frontend for the DeployMind deployment platform.

## Tech Stack

- **Next.js 15** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling
- **shadcn/ui** - High-quality React components
- **TanStack Query** - Server state management
- **Axios** - HTTP client for API calls
- **Lucide React** - Icon library

## Setup

### Install Dependencies

```bash
cd frontend
npm install
```

### Configure Environment

Create `.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Run Development Server

```bash
npm run dev
```

## Features

- ✅ JWT Authentication
- ✅ Protected Dashboard Routes
- ✅ Responsive Sidebar Navigation
- ✅ Real-time Analytics
- ✅ Dark Theme UI

## Default Credentials

- **Email**: admin@deploymind.io
- **Password**: admin123
