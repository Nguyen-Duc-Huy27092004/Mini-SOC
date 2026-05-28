import { create } from 'zustand';
import api, { setCsrfToken } from '../../shared/api/client';
import axios, { AxiosError } from 'axios';

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  full_name: string;
  is_active: boolean;
  must_change_password: boolean;
  roles: string[];
  created_at: string;
}

interface LoginResponse {
  user: UserProfile;
  csrf_token: string;
  access_token?: string;
  token_type?: string;
}

interface ApiErrorResponse {
  detail?: string | { msg?: string }[];
  message?: string;
}

interface AuthState {
  user: UserProfile | null;
  csrfToken: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  initialized: boolean;
  error: string | null;

  initialize: () => Promise<void>;

  login: (
    email: string,
    password: string
  ) => Promise<UserProfile>;

  logout: () => Promise<void>;

  logoutAll: () => Promise<void>;

  clearError: () => void;

  setUser: (user: UserProfile | null) => void;
}

const extractErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorResponse>;

    const data = axiosError.response?.data;

    if (typeof data?.detail === 'string') {
      return data.detail;
    }

    if (Array.isArray(data?.detail)) {
      return data.detail
        .map((d) => d.msg || 'Validation error')
        .join(', ');
    }

    if (data?.message) {
      return data.message;
    }

    switch (axiosError.response?.status) {
      case 401:
        return 'Sai tài khoản hoặc mật khẩu';

      case 403:
        return 'Tài khoản không có quyền truy cập';

      case 422:
        return 'Dữ liệu đăng nhập không hợp lệ';

      case 500:
        return 'Lỗi máy chủ';

      default:
        return 'Không thể kết nối tới hệ thống';
    }
  }

  if (error instanceof Error) {
    return error.message;
  }

  return 'Đã xảy ra lỗi không xác định';
};

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  csrfToken: null,
  isAuthenticated: false,
  loading: false,
  initialized: false,
  error: null,

  initialize: async () => {
    try {
      const response = await api.get<UserProfile>('/auth/me');

      set({
        user: response.data,
        isAuthenticated: true,
        initialized: true,
        error: null,
      });
    } catch {
      set({
        user: null,
        isAuthenticated: false,
        initialized: true,
      });
    }
  },

  login: async (email: string, password: string) => {
    set({
      loading: true,
      error: null,
    });

    try {
      const response = await api.post<LoginResponse>(
        '/auth/login',
        {
          email,
          password,
        },
        {
          headers: {
            'Content-Type': 'application/json',
          },
          withCredentials: true,
        }
      );

      const { user, csrf_token } = response.data;

      setCsrfToken(csrf_token);

      set({
        user,
        csrfToken: csrf_token,
        isAuthenticated: true,
        loading: false,
        error: null,
      });

      return user;
    } catch (error: unknown) {
      const message = extractErrorMessage(error);

      set({
        error: message,
        loading: false,
        isAuthenticated: false,
      });

      throw new Error(message);
    }
  },

  logout: async () => {
    try {
      await api.post(
        '/auth/logout',
        {},
        {
          withCredentials: true,
        }
      );
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setCsrfToken('');

      set({
        user: null,
        csrfToken: null,
        isAuthenticated: false,
        error: null,
      });

      window.location.href = '/login';
    }
  },

  logoutAll: async () => {
    try {
      await api.post(
        '/auth/logout-all',
        {},
        {
          withCredentials: true,
        }
      );
    } catch (error) {
      console.error('Logout all failed:', error);
    } finally {
      setCsrfToken('');

      set({
        user: null,
        csrfToken: null,
        isAuthenticated: false,
        error: null,
      });

      window.location.href = '/login';
    }
  },

  clearError: () =>
    set({
      error: null,
    }),

  setUser: (user) =>
    set({
      user,
      isAuthenticated: !!user,
    }),
}));

export const selectUser = (state: AuthState) => state.user;

export const selectIsAuthenticated = (
  state: AuthState
) => state.isAuthenticated;

export const selectAuthLoading = (
  state: AuthState
) => state.loading;

export const selectAuthError = (
  state: AuthState
) => state.error;