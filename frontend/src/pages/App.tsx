import { lazy, Suspense, useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

import { useAuthStore } from '@/store/auth';
import { applyTheme, useUiStore } from '@/store/ui';
import { wsClient } from '@/ws/client';
import { authApi } from '@/api/endpoints';
import { Toaster } from '@/components/ui/Toaster';
import { Spinner } from '@/components/ui/Spinner';
import { ErrorBoundary } from '@/components/ui/ErrorBoundary';
import { CallManager } from '@/components/calls/CallManager';

const Login = lazy(() => import('./Login').then((m) => ({ default: m.Login })));
const Register = lazy(() => import('./Register').then((m) => ({ default: m.Register })));
const Home = lazy(() => import('./Home').then((m) => ({ default: m.Home })));
const ChatRoute = lazy(() => import('./ChatRoute').then((m) => ({ default: m.ChatRoute })));
const Settings = lazy(() => import('./Settings').then((m) => ({ default: m.Settings })));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30 * 1000,
    },
  },
});

function PrivateOnly({ children }: { children: React.ReactNode }) {
  const access = useAuthStore((s) => s.accessToken);
  const location = useLocation();
  if (!access) return <Navigate to="/login" replace state={{ from: location }} />;
  return <>{children}</>;
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const access = useAuthStore((s) => s.accessToken);
  if (access) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function ThemeApplier() {
  const theme = useUiStore((s) => s.theme);
  useEffect(() => {
    applyTheme(theme);
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = (): void => applyTheme(theme);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, [theme]);
  return null;
}

function BootstrapAuth() {
  const access = useAuthStore((s) => s.accessToken);
  const setMe = useAuthStore((s) => s.setMe);
  useEffect(() => {
    if (!access) return;
    let cancelled = false;
    authApi
      .me()
      .then((u) => {
        if (!cancelled) setMe(u);
      })
      .catch(() => {
        // refresh-flow handled by axios interceptor
      });
    wsClient.connect(access);
    return () => {
      cancelled = true;
    };
  }, [access, setMe]);
  useEffect(() => {
    return () => wsClient.disconnect();
  }, []);
  return null;
}

const Loader = () => (
  <div className="flex h-dvh w-full items-center justify-center bg-bg">
    <Spinner className="h-8 w-8" />
  </div>
);

export function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <ThemeApplier />
          <BootstrapAuth />
          <Suspense fallback={<Loader />}>
            <Routes>
              <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
              <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />
              <Route path="/" element={<PrivateOnly><Home /></PrivateOnly>} />
              <Route path="/chat/:chatId" element={<PrivateOnly><ChatRoute /></PrivateOnly>} />
              <Route path="/settings/*" element={<PrivateOnly><Settings /></PrivateOnly>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </Suspense>
          <Toaster />
          <CallManager />
        </BrowserRouter>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}
