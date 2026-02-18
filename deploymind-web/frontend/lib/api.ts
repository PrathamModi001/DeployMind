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
    // Environment variables
    listEnvVars: (id: string) =>
      apiClient.get(`/api/deployments/${id}/env`),
    createEnvVar: (id: string, data: { key: string; value: string; is_secret: boolean }) =>
      apiClient.post(`/api/deployments/${id}/env`, data),
    updateEnvVar: (deploymentId: string, envId: number, data: { key: string; value: string; is_secret: boolean }) =>
      apiClient.put(`/api/deployments/${deploymentId}/env/${envId}`, data),
    deleteEnvVar: (deploymentId: string, envId: number) =>
      apiClient.delete(`/api/deployments/${deploymentId}/env/${envId}`),
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

  // AI Features
  ai: {
    recommendInstance: (data: { repository: string; language?: string; traffic_estimate?: string }) =>
      apiClient.post('/api/ai/recommend/instance', data),
    recommendStrategy: (params: { current_status: string; deployment_count: number; success_rate: number }) =>
      apiClient.post('/api/ai/recommend/strategy', null, { params }),
    analyzeCosts: (data: { deployment_count: number; avg_duration_seconds: number; instance_types: any }) =>
      apiClient.post('/api/ai/optimize/costs', data),
    estimateCost: (params: { instance_type: string; duration_hours: number; environment?: string }) =>
      apiClient.get('/api/ai/optimize/estimate', { params }),
    analyzeRollback: (data: {
      deployment_id: string;
      failed_checks: number;
      total_checks: number;
      error_messages: string[];
      deployment_age_minutes: number;
    }) =>
      apiClient.post('/api/ai/rollback/analyze', data),
    explainVulnerability: (data: { cve_id: string; package: string; severity: string; description?: string }) =>
      apiClient.post('/api/ai/security/explain', data),
  },

  // Monitoring
  monitoring: {
    getMetrics: (deploymentId: string) =>
      apiClient.get(`/api/monitoring/deployments/${deploymentId}/metrics`),
    getMetricsHistory: (deploymentId: string, hours: number = 1) =>
      apiClient.get(`/api/monitoring/deployments/${deploymentId}/metrics/history`, { params: { hours } }),
    getHealth: (deploymentId: string) =>
      apiClient.get(`/api/monitoring/deployments/${deploymentId}/health`),
  },

  // Webhooks
  webhooks: {
    getSetupInfo: () =>
      apiClient.get('/api/webhooks/github/setup'),
  },
};
