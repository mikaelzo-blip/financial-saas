import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

apiClient.interceptors.request.use(
  (config) => {
    const sessionStr = localStorage.getItem('financial_user_session');
    if (sessionStr) {
      try {
        const session = JSON.parse(sessionStr);
        if (session.accessToken) config.headers.Authorization = `Bearer ${session.accessToken}`;
        if (session.organizationId) config.headers['X-Organization-ID'] = session.organizationId;
        if (session.userId) config.headers['X-User-ID'] = session.userId;
      } catch {
        localStorage.removeItem('financial_user_session');
      }
    }
    return config;
  },
  (error) => Promise.reject(error),
);

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && !window.location.pathname.startsWith('/login')) {
      localStorage.removeItem('financial_user_session');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);
