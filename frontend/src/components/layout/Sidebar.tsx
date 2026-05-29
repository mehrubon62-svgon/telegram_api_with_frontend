import { Menu, Search, Pencil } from 'lucide-react';
import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ChatList } from '@/components/chats/ChatList';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useResponsive } from '@/hooks/useResponsive';
import { Drawer } from '@/components/layout/Drawer';
import { Settings as SettingsIcon, Phone, Bookmark, MoonStar } from 'lucide-react';
import { useUiStore } from '@/store/ui';
import { cn } from '@/lib/cn';
import { GlobalSearch } from '@/components/chats/GlobalSearch';
import { Avatar } from '@/components/ui/Avatar';
import { useAuthStore } from '@/store/auth';
import { StoriesBar } from '@/components/stories/StoriesBar';

export function Sidebar({ width = 360 }: { width?: number }) {
  const { isMobile } = useResponsive();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [query, setQuery] = useState('');
  const navigate = useNavigate();
  const location = useLocation();
  const me = useAuthStore((s) => s.me);
  const setTheme = useUiStore((s) => s.setTheme);
  const theme = useUiStore((s) => s.theme);

  const isOnChat = location.pathname.startsWith('/chat/');
  if (isMobile && isOnChat) return null;

  return (
    <aside
      className={cn(
        'flex h-dvh flex-col border-r border-line bg-bg',
        isMobile ? 'w-full' : 'shrink-0',
      )}
      style={isMobile ? undefined : { width }}
    >
      <div className="flex h-14 items-center gap-2 border-b border-line px-2 pt-safe">
        <Button variant="ghost" size="icon" aria-label="Menu" onClick={() => setDrawerOpen(true)}>
          <Menu className="h-5 w-5" />
        </Button>
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search"
            className="h-10 pl-10 text-sm"
          />
        </div>
      </div>

      <div className="thin-scrollbar flex-1 overflow-y-auto">
        {query.trim().length > 0 ? (
          <GlobalSearch query={query.trim()} onClose={() => setQuery('')} />
        ) : (
          <>
            <StoriesBar />
            <ChatList />
          </>
        )}
      </div>

      {isMobile && !isOnChat && (
        <button
          aria-label="New chat"
          onClick={() => navigate('/settings')}
          className="absolute bottom-6 right-4 flex h-14 w-14 items-center justify-center rounded-full bg-accent text-white shadow-lg active:scale-95"
        >
          <Pencil className="h-6 w-6" />
        </button>
      )}

      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
        <div className="bg-accent px-4 pb-4 pt-12 text-white">
          <Avatar src={me?.avatar_url} name={me?.username ?? me?.phone} id={me?.id ?? 0} size={64} />
          <div className="mt-3 text-lg font-medium">
            {me?.username ? `@${me.username}` : me?.phone ?? ''}
          </div>
          {me?.phone && me?.username && (
            <div className="text-sm opacity-80">{me.phone}</div>
          )}
        </div>
        <nav className="flex flex-col py-2">
          <DrawerItem icon={<Bookmark className="h-5 w-5" />} label="Saved Messages" onClick={() => setDrawerOpen(false)} />
          <DrawerItem icon={<Phone className="h-5 w-5" />} label="Calls" onClick={() => setDrawerOpen(false)} />
          <DrawerItem
            icon={<SettingsIcon className="h-5 w-5" />}
            label="Settings"
            onClick={() => {
              setDrawerOpen(false);
              navigate('/settings');
            }}
          />
          <DrawerItem
            icon={<MoonStar className="h-5 w-5" />}
            label={theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
            onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
          />
        </nav>
      </Drawer>
    </aside>
  );
}

function DrawerItem({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-4 px-4 py-3 text-left hover:bg-bg2"
    >
      <span className="text-muted">{icon}</span>
      {label}
    </button>
  );
}
