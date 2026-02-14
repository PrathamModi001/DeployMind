/**
 * API client configuration for DeployMind backend.
 */
import axios from 'axios';

// API base URL - defaults to localhost:8000 for development
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Create axios instance with default config
export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add JWT token
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear token and redirect to login on unauthorized
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// API endpoints
export const api = {
  // Authentication
  auth: {
    login: (email: string, password: string) =>
      apiClient.post('/api/auth/login', { email, password }),
    register: (data: any) =>
      apiClient.post('/api/auth/register', data),
    me: () =>
      apiClient.get('/api/auth/me'),
    logout: () =>
      apiClient.post('/api/auth/logout'),
  },

  // Deployments
  deployments: {
    list: (params?: { page?: number; page_size?: number; status?: string }) =>
      apiClient.get('/api/deployments', { params }),
    get: (id: string) =>
      apiClient.get(`/api/deployments/${id}`),
    create: (data: any) =>
      apiClient.post('/api/deployments', data),
    logs: (id: string) =>
      apiClient.get(`/api/deployments/${id}/logs`),
    rollback: (id: string) =>
      apiClient.post(`/api/deployments/${id}/rollback`),
  },

  // Analytics
  analytics: {
    overview: (days?: number) =>
      apiClient.get('/api/analytics/overview', { params: { days } }),
    timeline: (days?: number) =>
      apiClient.get('/api/analytics/timeline', { params: { days } }),
    performance: () =>
      apiClient.get('/api/analytics/performance'),
  },
};
