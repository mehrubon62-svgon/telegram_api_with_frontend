import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '@/api/endpoints';
import { useAuthStore } from '@/store/auth';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Logo } from '@/components/ui/Logo';
import { toast } from '@/components/ui/Toaster';

type Step = 'phone' | 'code' | 'register';

function normalizePhone(raw: string): string {
  const digits = raw.replace(/[^\d]/g, '');
  return digits ? `+${digits}` : '';
}

export function Login() {
  const navigate = useNavigate();
  const setTokens = useAuthStore((s) => s.setTokens);

  const [step, setStep] = useState<Step>('phone');
  const [phoneRaw, setPhoneRaw] = useState('');
  const [code, setCode] = useState('');
  const [sentCode, setSentCode] = useState<string | null>(null);
  const [fullName, setFullName] = useState('');
  const [username, setUsername] = useState('');
  const [loading, setLoading] = useState(false);

  const phone = normalizePhone(phoneRaw);

  async function requestCode(e: React.FormEvent) {
    e.preventDefault();
    if (phone.length < 6) {
      toast.error('Enter a valid phone number');
      return;
    }
    setLoading(true);
    try {
      const r = await authApi.requestCode(phone);
      setSentCode(r.code);
      setStep('code');
    } catch {
      toast.error('Failed to send code');
    } finally {
      setLoading(false);
    }
  }

  async function verifyCode(e: React.FormEvent) {
    e.preventDefault();
    if (code.length < 4) return;
    setLoading(true);
    try {
      const tokens = await authApi.verifyCode({ phone, code, device_name: 'Web' });
      setTokens(tokens.access_token, tokens.refresh_token);
      navigate('/', { replace: true });
    } catch (err) {
      const status = (err as { response?: { status?: number } }).response?.status;
      if (status === 404) {
        // Номер не зарегистрирован → к регистрации
        setStep('register');
      } else {
        const msg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
        toast.error(msg ?? 'Invalid code');
      }
    } finally {
      setLoading(false);
    }
  }

  async function register(e: React.FormEvent) {
    e.preventDefault();
    if (!fullName.trim()) {
      toast.error('Enter your name');
      return;
    }
    if (!/^[a-zA-Z][a-zA-Z0-9_]{2,49}$/.test(username)) {
      toast.error('Username: 3–50 chars, starts with a letter');
      return;
    }
    setLoading(true);
    try {
      const tokens = await authApi.registerPhone({ phone, full_name: fullName.trim(), username });
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
        <div className="mb-8 flex flex-col items-center text-center">
          <Logo size={88} />
          {step === 'phone' && (
            <>
              <h1 className="mt-6 text-2xl font-medium">Your phone number</h1>
              <p className="mt-2 text-sm text-muted">We will send you a code to sign in</p>
            </>
          )}
          {step === 'code' && (
            <>
              <h1 className="mt-6 text-2xl font-medium">{phone}</h1>
              <p className="mt-2 text-sm text-muted">Enter the code we sent you</p>
            </>
          )}
          {step === 'register' && (
            <>
              <h1 className="mt-6 text-2xl font-medium">Create your account</h1>
              <p className="mt-2 text-sm text-muted">{phone}</p>
            </>
          )}
        </div>

        {step === 'phone' && (
          <form onSubmit={requestCode} className="space-y-4">
            <Input
              autoFocus
              value={phoneRaw}
              onChange={(e) => setPhoneRaw(e.target.value)}
              placeholder="+1 234 567 8900"
              inputMode="tel"
              required
            />
            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? 'Sending…' : 'Next'}
            </Button>
          </form>
        )}

        {step === 'code' && (
          <form onSubmit={verifyCode} className="space-y-4">
            {sentCode && (
              <div className="rounded-xl border border-accent/40 bg-accent/10 px-4 py-3 text-center text-sm">
                <span className="text-muted">Demo code: </span>
                <span className="font-mono text-lg font-semibold tracking-widest text-accent">{sentCode}</span>
              </div>
            )}
            <Input
              autoFocus
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 5))}
              placeholder="Code"
              inputMode="numeric"
              className="text-center text-xl tracking-[0.5em]"
              required
            />
            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? 'Checking…' : 'Sign in'}
            </Button>
            <Button type="button" variant="ghost" className="w-full" size="lg" onClick={() => setStep('phone')}>
              Change number
            </Button>
          </form>
        )}

        {step === 'register' && (
          <form onSubmit={register} className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted">Name</label>
              <Input autoFocus value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="John Doe" required />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-muted">Username</label>
              <div className="relative">
                <span className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-muted">@</span>
                <Input
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="username"
                  className="pl-9"
                  autoCapitalize="none"
                  autoCorrect="off"
                  required
                />
              </div>
            </div>
            <Button type="submit" disabled={loading} className="w-full" size="lg">
              {loading ? 'Creating…' : 'Create account'}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
