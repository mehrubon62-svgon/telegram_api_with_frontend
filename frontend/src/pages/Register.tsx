import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authApi } from '@/api/endpoints';
import { useAuthStore } from '@/store/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Logo } from '@/components/ui/Logo';
import { toast } from '@/components/ui/Toaster';

type Step = 'phone' | 'username' | 'password';

function normalizePhone(raw: string): string {
  const digits = raw.replace(/[^\d]/g, '');
  return digits ? `+${digits}` : '';
}

function syntheticEmail(phone: string): string {
  // Бэкенд требует email; пользователь его не вводит.
  // Используем телефон как локальную часть (только цифры).
  const digits = phone.replace(/[^\d]/g, '');
  return `${digits}@tg.local`;
}

export function Register() {
  const navigate = useNavigate();
  const setTokens = useAuthStore((s) => s.setTokens);

  const [step, setStep] = useState<Step>('phone');
  const [phoneRaw, setPhoneRaw] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  function nextFromPhone(e: React.FormEvent) {
    e.preventDefault();
    const phone = normalizePhone(phoneRaw);
    if (phone.length < 6) {
      toast.error('Please enter a valid phone number');
      return;
    }
    setStep('username');
  }

  function nextFromUsername(e: React.FormEvent) {
    e.preventDefault();
    if (!/^[a-zA-Z][a-zA-Z0-9_]{2,49}$/.test(username)) {
      toast.error('Username must be 3–50 chars, start with a letter');
      return;
    }
    setStep('password');
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }
    setLoading(true);
    try {
      const phone = normalizePhone(phoneRaw);
      const tokens = await authApi.register({
        email: syntheticEmail(phone),
        password,
        username,
        phone,
      });
      setTokens(tokens.access_token, tokens.refresh_token);
      navigate('/', { replace: true });
    } catch (err) {
      const msg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast.error(msg ?? 'Registration failed');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-dvh flex-col items-center justify-center bg-bg px-6 py-safe">
      <div className="w-full max-w-sm">
        <div className="mb-10 flex flex-col items-center text-center">
          <Logo size={88} />
          {step === 'phone' && (
            <>
              <h1 className="mt-6 text-2xl font-medium">Your phone number</h1>
              <p className="mt-2 text-sm text-muted">We&apos;ll use it to sign you in</p>
            </>
          )}
          {step === 'username' && (
            <>
              <h1 className="mt-6 text-2xl font-medium">Choose a username</h1>
              <p className="mt-2 text-sm text-muted">
                Letters, numbers and underscores. Starts with a letter.
              </p>
            </>
          )}
          {step === 'password' && (
            <>
              <h1 className="mt-6 text-2xl font-medium">Set a password</h1>
              <p className="mt-2 text-sm text-muted">At least 6 characters</p>
            </>
          )}
        </div>

        {step === 'phone' && (
          <form onSubmit={nextFromPhone} className="space-y-4">
            <Input
              autoFocus
              value={phoneRaw}
              onChange={(e) => setPhoneRaw(e.target.value)}
              placeholder="+1 234 567 8900"
              inputMode="tel"
              required
            />
            <Button type="submit" className="w-full" size="lg">
              Next
            </Button>
          </form>
        )}

        {step === 'username' && (
          <form onSubmit={nextFromUsername} className="space-y-4">
            <div className="relative">
              <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted">
                @
              </span>
              <Input
                autoFocus
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="username"
                className="pl-9"
                required
                pattern="^[a-zA-Z][a-zA-Z0-9_]{2,49}$"
                autoCapitalize="none"
                autoCorrect="off"
              />
            </div>
            <Button type="submit" className="w-full" size="lg">
              Next
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="w-full"
              size="lg"
              onClick={() => setStep('phone')}
            >
              Back
            </Button>
          </form>
        )}

        {step === 'password' && (
          <form onSubmit={submit} className="space-y-4">
            <Input
              autoFocus
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••"
              required
              minLength={6}
            />
            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? 'Creating…' : 'Create account'}
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="w-full"
              size="lg"
              onClick={() => setStep('username')}
            >
              Back
            </Button>
          </form>
        )}

        <p className="mt-8 text-center text-sm text-muted">
          Already have an account?{' '}
          <Link to="/login" className="font-medium tg-link">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
