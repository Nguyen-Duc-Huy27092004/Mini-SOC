import axios from 'axios';

const CSRF_HEADER = 'X-CSRF-Token';

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1';

export const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
});

export function setCsrfToken(token: string) {
  api.defaults.headers.common[CSRF_HEADER] = token;
}

// ── Request interceptor: log outgoing calls ─────────────────────────────────
api.interceptors.request.use((config) => {
  if (import.meta.env.DEV) {
    console.debug(
      `[API] → ${config.method?.toUpperCase()} ${config.baseURL}${config.url}`,
      config.params ?? ''
    );
  }
  return config;
});

// ── Response interceptor: handle 401 refresh + logging ──────────────────────
api.interceptors.response.use(
  (response) => {
    if (import.meta.env.DEV) {
      console.debug(
        `[API] ← ${response.status} ${response.config.url}`
      );
    }
    return response;
  },
  async (error) => {
    const original = error.config;

    // Always log errors in dev
    if (import.meta.env.DEV) {
      console.error(
        `[API] ✗ ${error.response?.status ?? 'NETWORK'} ${original?.url}`,
        error.response?.data ?? error.message
      );
    }

    const isAuthEndpoint =
      original?.url?.includes('/auth/refresh') ||
      original?.url?.includes('/auth/login');

    if (error.response?.status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true;
      try {
        const refreshRes = await api.post('/auth/refresh');
        setCsrfToken(refreshRes.data.csrf_token);
        return api(original);
      } catch (refreshError) {
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
