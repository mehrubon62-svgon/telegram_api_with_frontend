import axios, { AxiosError, AxiosInstance, type InternalAxiosRequestConfig } from 'axios';
import { API_BASE } from '@/lib/url';
import { useAuthStore } from '@/store/auth';

interface RetryConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refresh = useAuthStore.getState().refreshToken;
  if (!refresh) return null;
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    try {
      const r = await axios.post(`${API_BASE}/users/refresh`, { refresh_token: refresh });
      const access = r.data.access_token as string;
      const newRefresh = r.data.refresh_token as string;
      useAuthStore.getState().setTokens(access, newRefresh);
      return access;
    } catch {
      useAuthStore.getState().logout();
      return null;
    } finally {
      refreshPromise = null;
    }
  })();
  return refreshPromise;
}

export const api: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const config = error.config as RetryConfig | undefined;
    if (!config) return Promise.reject(error);

    // 2FA — отдельный поток, не трогаем
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
    if (error.response?.status === 401 && detail === '2FA_REQUIRED') {
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !config._retry) {
      config._retry = true;
      const newAccess = await refreshAccessToken();
      if (newAccess) {
        config.headers.set('Authorization', `Bearer ${newAccess}`);
        return api(config);
      }
    }
    return Promise.reject(error);
  },
);
