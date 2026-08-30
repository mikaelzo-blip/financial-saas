import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor: Attach JWT token and active tenant organization ID
apiClient.interceptors.request.use(
  (config) => {
    const sessionStr = localStorage.getItem('financial_user_session');
    if (sessionStr) {
      try {
        const session = JSON.parse(sessionStr);
        if (session.accessToken) {
          config.headers.Authorization = `Bearer ${session.accessToken}`;
        }
        if (session.organizationId) {
          config.headers['X-Organization-ID'] = session.organizationId;
        }
      } catch {
        // Ignored if session is malformed
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor: Handle 401 Unauthorized
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear token and redirect if on a protected route
      if (!window.location.pathname.startsWith('/login')) {
        localStorage.removeItem('financial_user_session');
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);
