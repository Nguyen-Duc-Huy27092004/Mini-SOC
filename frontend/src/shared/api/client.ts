import axios from 'axios';

const CSRF_HEADER = 'X-CSRF-Token';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  withCredentials: true,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

export function setCsrfToken(token: string) {
  api.defaults.headers.common[CSRF_HEADER] = token;
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    
    // Don't retry if:
    // 1. Already retried
    // 2. Request is to /auth/refresh itself (prevent infinite loop)
    // 3. Request is to /auth/login
    const isAuthEndpoint = original.url?.includes('/auth/refresh') || 
                          original.url?.includes('/auth/login');
    
    if (error.response?.status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      try {
        const refreshRes = await api.post('/auth/refresh');
        setCsrfToken(refreshRes.data.csrf_token);
        return api(original);
      } catch (refreshError) {
        // Only redirect if not already on login page
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login?expired=true';
        }
        return Promise.reject(refreshError);
      }
    }
    
    const detail = error.response?.data?.detail || 'Hệ thống gặp sự cố';
    return Promise.reject({ ...error, message: detail });
  }
);

export default api;
