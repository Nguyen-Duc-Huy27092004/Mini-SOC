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
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      try {
        const refreshRes = await api.post('/auth/refresh');
        setCsrfToken(refreshRes.data.csrf_token);
        return api(original);
      } catch {
        if (!window.location.pathname.startsWith('/login')) {
          window.location.href = '/login?expired=true';
        }
      }
    }
    const detail = error.response?.data?.detail || 'Hệ thống gặp sự cố';
    return Promise.reject({ ...error, message: detail });
  }
);

export default api;
