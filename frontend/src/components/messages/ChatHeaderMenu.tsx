import { Bell, BellOff, Trash2, Info, LogOut } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import type { ChatOut } from '@/api/types';
import { chatsApi } from '@/api/endpoints';
import { toast } from '@/components/ui/Toaster';
import { useNavigate } from 'react-router-dom';

interface Props {
  chat: ChatOut;
  isMuted: boolean;
  anchor: { x: number; y: number };
  onClose: () => void;
  onShowInfo: () => void;
}

export function ChatHeaderMenu({ chat, isMuted, anchor, onClose, onShowInfo }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    function onDoc(e: Event) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    const t = setTimeout(() => {
      document.addEventListener('mousedown', onDoc);
      document.addEventListener('touchstart', onDoc);
    }, 0);
    document.addEventListener('keydown', onKey);
    return () => {
      clearTimeout(t);
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('touchstart', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  return createPortal(
    <>
      <div className="fixed inset-0 z-[150]" onClick={onClose} />
      <div
        ref={ref}
        style={{ left: Math.max(8, anchor.x - 220), top: anchor.y + 8 }}
        className="fixed z-[151] w-[230px] rounded-xl border border-line bg-bg p-1 shadow-2xl animate-fade-in"
      >
        <Item
          icon={<Info className="h-4 w-4" />}
          label="View info"
          onClick={() => {
            onShowInfo();
            onClose();
          }}
        />
        <Item
          icon={isMuted ? <Bell className="h-4 w-4" /> : <BellOff className="h-4 w-4" />}
          label={isMuted ? 'Unmute' : 'Mute'}
          onClick={async () => {
            try {
              await chatsApi.mute(chat.id, { is_muted: !isMuted });
              toast.success(isMuted ? 'Unmuted' : 'Muted');
            } catch {
              toast.error('Failed');
            }
            onClose();
          }}
        />
        {chat.type !== 'private' && chat.type !== 'saved' && (
          <Item
            icon={<LogOut className="h-4 w-4" />}
            label={chat.type === 'channel' ? 'Leave channel' : 'Leave group'}
            destructive
            onClick={async () => {
              try {
                await chatsApi.leave(chat.id);
                toast.success('Left');
                navigate('/');
              } catch {
                toast.error('Failed');
              }
              onClose();
            }}
          />
        )}
        <Item
          icon={<Trash2 className="h-4 w-4" />}
          label="Delete chat"
          destructive
          onClick={async () => {
            if (!confirm('Delete this chat?')) {
              onClose();
              return;
            }
            try {
              await chatsApi.remove(chat.id);
              navigate('/');
            } catch {
              toast.error('Failed');
            }
            onClose();
          }}
        />
      </div>
    </>,
    document.body,
  );
}

function Item({
  icon,
  label,
  onClick,
  destructive,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  destructive?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors ' +
        (destructive ? 'text-danger hover:bg-danger/10' : 'text-text hover:bg-bg2')
      }
    >
      <span className={destructive ? 'text-danger' : 'text-muted'}>{icon}</span>
      {label}
    </button>
  );
}
