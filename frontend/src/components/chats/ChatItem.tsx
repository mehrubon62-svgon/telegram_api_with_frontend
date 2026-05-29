import { Pin, VolumeX, CheckCheck } from 'lucide-react';
import type { ChatListItem } from '@/api/types';
import { Avatar } from '@/components/ui/Avatar';
import { cn } from '@/lib/cn';
import { formatChatListTime } from '@/lib/format';
import { useAuthStore } from '@/store/auth';
import { usePresenceStore } from '@/store/presence';

interface Props {
  item: ChatListItem;
  active: boolean;
  onClick: () => void;
}

export function ChatItem({ item, active, onClick }: Props) {
  const me = useAuthStore((s) => s.me);
  const { chat, last_message } = item;

  const typingMap = usePresenceStore((s) => s.typing);
  const typingCount = (() => {
    const inner = typingMap.get(chat.id);
    if (!inner) return 0;
    const cutoff = Date.now() - 6000;
    let n = 0;
    for (const ts of inner.values()) if (ts > cutoff) n++;
    return n;
  })();

  const title =
    chat.type === 'saved'
      ? 'Saved Messages'
      : chat.title ?? chat.public_username ?? `Chat ${chat.id}`;

  const isOwnLast = last_message?.sender_id === me?.id;
  const isGroupLike = chat.type === 'group' || chat.type === 'supergroup';

  let preview: React.ReactNode;
  if (typingCount > 0) {
    preview = <span className="text-accent">typing…</span>;
  } else if (last_message) {
    if (last_message.is_deleted) {
      preview = <span className="italic text-muted">message deleted</span>;
    } else {
      const senderTag =
        isOwnLast
          ? 'You: '
          : isGroupLike && last_message.sender_username
            ? `${last_message.sender_username}: `
            : '';
      preview = (
        <>
          {senderTag && <span className="text-text/80">{senderTag}</span>}
          <span className="text-muted">{last_message.text || '...'}</span>
        </>
      );
    }
  } else {
    preview = <span className="text-muted">No messages yet</span>;
  }

  const time = last_message?.created_at
    ? formatChatListTime(last_message.created_at)
    : '';

  return (
    <button
      role="listitem"
      onClick={onClick}
      className={cn(
        'flex w-full items-center gap-3 px-3 py-2 text-left transition-colors',
        active ? 'bg-accent/15' : 'hover:bg-bg2',
      )}
    >
      <Avatar src={chat.avatar_url} name={title} id={chat.id} size={50} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-1">
            <span className={cn('truncate font-medium', active && 'text-accent')}>{title}</span>
            {item.is_muted && <VolumeX className="h-4 w-4 shrink-0 text-muted" />}
          </div>
          <div className="flex shrink-0 items-center gap-1 text-xs text-muted">
            {isOwnLast && <CheckCheck className="h-3.5 w-3.5 text-accent" />}
            <span>{time}</span>
          </div>
        </div>
        <div className="mt-0.5 flex items-center justify-between gap-2">
          <span className="truncate text-sm">{preview}</span>
          <div className="flex shrink-0 items-center gap-1">
            {item.is_pinned && <Pin className="h-3.5 w-3.5 text-muted" />}
            {item.unread_count > 0 && (
              <span
                className={cn(
                  'min-w-[20px] rounded-full px-1.5 py-0.5 text-center text-xs font-semibold text-white',
                  item.is_muted ? 'bg-muted' : 'bg-accent',
                )}
              >
                {item.unread_count > 99 ? '99+' : item.unread_count}
              </span>
            )}
          </div>
        </div>
      </div>
    </button>
  );
}
