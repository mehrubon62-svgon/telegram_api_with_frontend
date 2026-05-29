import { ArrowLeft, LogOut, Moon, Sun, Monitor } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useRef, useState } from 'react';
import { useAuthStore } from '@/store/auth';
import { useUiStore } from '@/store/ui';
import { Button } from '@/components/ui/Button';
import { Avatar } from '@/components/ui/Avatar';
import { authApi, mediaApi } from '@/api/endpoints';
import { wsClient } from '@/ws/client';
import { toast } from '@/components/ui/Toaster';
import { cn } from '@/lib/cn';
import { NAME_COLORS } from '@/lib/colors';

export function Settings() {
  const me = useAuthStore((s) => s.me);
  const refresh = useAuthStore((s) => s.refreshToken);
  const logout = useAuthStore((s) => s.logout);
  const setMe = useAuthStore((s) => s.setMe);
  const theme = useUiStore((s) => s.theme);
  const setTheme = useUiStore((s) => s.setTheme);
  const navigate = useNavigate();
  const fileRef = useRef<HTMLInputElement>(null);

  async function onLogout() {
    try {
      if (refresh) await authApi.logout(refresh);
    } catch {
      // ignore
    }
    wsClient.disconnect();
    logout();
    navigate('/login', { replace: true });
  }

  async function onAvatar(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    try {
      await mediaApi.uploadAvatar(f);
      const updated = await authApi.me();
      setMe(updated);
      toast.success('Photo updated');
    } catch {
      toast.error('Upload failed');
    }
  }

  const display = me?.username ? `@${me.username}` : me?.phone ?? '';

  return (
    <div className="mx-auto flex h-dvh w-full max-w-2xl flex-col bg-bg">
      <header className="flex h-14 items-center gap-3 border-b border-line px-2 pt-safe">
        <Button variant="ghost" size="icon" onClick={() => navigate(-1)} aria-label="Back">
          <ArrowLeft className="h-5 w-5" />
        </Button>
        <h1 className="text-lg font-medium">Settings</h1>
      </header>

      <div className="thin-scrollbar flex-1 overflow-y-auto pb-safe">
        <section className="flex flex-col items-center gap-3 px-4 py-8">
          <Avatar src={me?.avatar_url} name={me?.username ?? me?.phone} id={me?.id ?? 0} size={96} />
          <input ref={fileRef} type="file" accept="image/*" hidden onChange={onAvatar} />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            className="text-sm font-medium text-accent hover:underline"
          >
            Set new photo
          </button>
          <div className="text-center">
            <div className="text-xl font-medium">{display}</div>
            {me?.phone && me?.username && (
              <div className="text-sm text-muted">{me.phone}</div>
            )}
          </div>
        </section>

        <Section title="Appearance">
          <div className="grid grid-cols-3 gap-2 p-3">
            <ThemeBtn current={theme} value="light" label="Light" icon={<Sun className="h-4 w-4" />} onChange={setTheme} />
            <ThemeBtn current={theme} value="dark" label="Dark" icon={<Moon className="h-4 w-4" />} onChange={setTheme} />
            <ThemeBtn current={theme} value="auto" label="System" icon={<Monitor className="h-4 w-4" />} onChange={setTheme} />
          </div>
        </Section>

        <Section title="Account">
          <Row label="Username" value={me?.username ? `${me.username}` : 'Not set'} />
          <Row label="Phone" value={me?.phone ?? 'Not set'} />
          <Row label="Bio" value={me?.bio ?? 'Not set'} />
          <BirthdayRow />
        </Section>

        <Section title="Name color">
          <div className="flex flex-wrap gap-2 p-4">
            {NAME_COLORS.map((c, i) => {
              const active = (me?.name_color ?? 0) === i;
              return (
                <button
                  key={i}
                  type="button"
                  aria-label={`color ${i}`}
                  onClick={async () => {
                    try {
                      const updated = await authApi.updateMe({ name_color: i });
                      setMe(updated);
                      toast.success('Color updated');
                    } catch {
                      toast.error('Failed');
                    }
                  }}
                  className={cn(
                    'h-9 w-9 rounded-full transition-transform',
                    active ? 'ring-2 ring-offset-2 ring-offset-bg' : '',
                  )}
                  style={{ background: c, ['--tw-ring-color' as string]: c }}
                />
              );
            })}
          </div>
        </Section>

        <Section>
          <button
            onClick={onLogout}
            className="flex w-full items-center gap-3 px-4 py-4 text-left text-danger hover:bg-bg2"
          >
            <LogOut className="h-5 w-5" />
            <span>Log out</span>
          </button>
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }: { title?: string; children: React.ReactNode }) {
  return (
    <section className="mt-2">
      {title && (
        <div className="px-4 pb-1.5 pt-3 text-xs font-medium uppercase tracking-wider text-muted">
          {title}
        </div>
      )}
      <div className="border-y border-line bg-bg">{children}</div>
    </section>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between border-b border-line px-4 py-3 last:border-b-0">
      <span className="text-sm text-muted">{label}</span>
      <span className="text-sm">{value}</span>
    </div>
  );
}

function BirthdayRow() {
  const me = useAuthStore((s) => s.me);
  const setMe = useAuthStore((s) => s.setMe);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');

  if (me?.birthday) {
    const d = new Date(me.birthday);
    return (
      <div className="flex items-center justify-between border-b border-line px-4 py-3 last:border-b-0">
        <span className="text-sm text-muted">Date of birth</span>
        <span className="text-sm">{d.toLocaleDateString(undefined, { day: 'numeric', month: 'long', year: 'numeric' })}</span>
      </div>
    );
  }

  if (!editing) {
    return (
      <button
        onClick={() => setEditing(true)}
        className="flex w-full items-center justify-between border-b border-line px-4 py-3 text-left last:border-b-0 hover:bg-bg2"
      >
        <span className="text-sm text-muted">Date of birth</span>
        <span className="text-sm text-accent">Set</span>
      </button>
    );
  }

  return (
    <div className="flex items-center gap-2 border-b border-line px-4 py-3 last:border-b-0">
      <span className="text-sm text-muted">Date of birth</span>
      <input
        type="date"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="ml-auto rounded-md bg-bg2 px-2 py-1 text-sm outline-none"
      />
      <button
        disabled={!value}
        onClick={async () => {
          try {
            const iso = new Date(value + 'T00:00:00Z').toISOString();
            const updated = await authApi.updateMe({ birthday: iso });
            setMe(updated);
            toast.success('Birthday set (cannot be changed later)');
            setEditing(false);
          } catch (err) {
            const msg = (err as { response?: { data?: { detail?: string } } }).response?.data?.detail;
            toast.error(msg ?? 'Failed');
          }
        }}
        className="rounded-md bg-accent px-3 py-1 text-sm text-white disabled:opacity-50"
      >
        Save
      </button>
    </div>
  );
}

function ThemeBtn<T extends string>({ current, value, label, icon, onChange }: {
  current: string;
  value: T;
  label: string;
  icon: React.ReactNode;
  onChange: (v: T) => void;
}) {
  const active = current === value;
  return (
    <button
      onClick={() => onChange(value)}
      className={cn(
        'flex flex-col items-center gap-1.5 rounded-lg border px-3 py-3 text-sm transition-colors',
        active ? 'border-accent bg-accent/10 text-accent' : 'border-line text-text hover:bg-bg2',
      )}
    >
      {icon}
      {label}
    </button>
  );
}
