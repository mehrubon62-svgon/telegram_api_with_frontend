import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserMe } from '@/api/types';

interface AuthState {
  accessToken: string | null;
  refreshToken: string | null;
  me: UserMe | null;
  setTokens: (access: string, refresh: string) => void;
  setMe: (user: UserMe | null) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      me: null,
      setTokens: (accessToken, refreshToken) => set({ accessToken, refreshToken }),
      setMe: (me) => set({ me }),
      logout: () => set({ accessToken: null, refreshToken: null, me: null }),
    }),
    { name: 'tg-auth' },
  ),
);
