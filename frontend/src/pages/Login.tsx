import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '@/api/endpoints';
import { useAuthStore } from '@/store/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Logo } from '@/components/ui/Logo';
import { toast } from '@/components/ui/Toaster';

export function Login() {
  const navigate = useNavigate();
  const setTokens = useAuthStore((s) => s.setTokens);
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const tokens = await authApi.login({
        identifier: identifier.trim(),
        password,
        device_name: 'Web',
      });
      setTokens(tokens.access_token, tokens.refresh_token);
      navigate('/', { replace: true });
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      if (msg === '2FA_REQUIRED') {
        toast.error('Two-factor verification is not yet supported in the web client.');
      } else {
        toast.error(msg ?? 'Sign-in failed');
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-bg px-6 py-safe">
      <div className="w-full max-w-sm">
        <div className="mb-10 flex flex-col items-center text-center">
          <Logo size={88} />
          <h1 className="mt-6 text-2xl font-medium">Sign in</h1>
          <p className="mt-2 text-sm text-muted">
            Enter your phone number or username
          </p>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted">
              Phone number or username
            </label>
            <Input
              autoFocus
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              placeholder="+1 234 567 8900"
              autoComplete="username"
              inputMode="tel"
              required
            />
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted">
              Password
            </label>
            <Input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••"
              autoComplete="current-password"
              required
              minLength={6}
            />
          </div>

          <Button type="submit" disabled={loading} className="w-full" size="lg">
            {loading ? 'Signing in…' : 'Next'}
          </Button>
        </form>

        <p className="mt-8 text-center text-sm text-muted">
          New to Telegramm?{' '}
          <Link to="/register" className="font-medium tg-link">
            Create account
          </Link>
        </p>
      </div>
    </div>
  );
}
