import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'light' | 'dark' | 'auto';

interface UiState {
  theme: Theme;
  rightPanelOpen: boolean;
  sidebarWidth: number;
  setTheme: (t: Theme) => void;
  toggleRightPanel: () => void;
  setRightPanel: (open: boolean) => void;
  setSidebarWidth: (px: number) => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      theme: 'auto',
      rightPanelOpen: false,
      sidebarWidth: 360,
      setTheme: (theme) => set({ theme }),
      toggleRightPanel: () => set((s) => ({ rightPanelOpen: !s.rightPanelOpen })),
      setRightPanel: (open) => set({ rightPanelOpen: open }),
      setSidebarWidth: (px) => {
        // 20%/80% от ширины окна, но не меньше 280
        const W = typeof window !== 'undefined' ? window.innerWidth : 1280;
        const min = Math.max(280, Math.round(W * 0.2));
        const max = Math.round(W * 0.8);
        set({ sidebarWidth: Math.min(Math.max(min, Math.round(px)), max) });
      },
    }),
    { name: 'tg-ui' },
  ),
);

export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  const dark =
    theme === 'dark' ||
    (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  root.classList.toggle('dark', dark);
  // theme-color
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', dark ? '#212121' : '#3390ec');
}
