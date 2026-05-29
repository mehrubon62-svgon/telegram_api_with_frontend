import { X } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import type { ChatOut } from '@/api/types';
import { chatsApi } from '@/api/endpoints';
import { Avatar } from '@/components/ui/Avatar';
import { Spinner } from '@/components/ui/Spinner';
import { cn } from '@/lib/cn';
import { nameColor } from '@/lib/colors';
import { UserStoriesGrid } from '@/components/stories/UserStoriesGrid';
import { UserProfilePanel } from './UserProfilePanel';
import { useAuthStore } from '@/store/auth';

interface Props {
  chat: ChatOut;
  open: boolean;
  onClose: () => void;
}

export function ChatProfilePanel({ chat, open, onClose }: Props) {
  const me = useAuthStore((s) => s.me);
  const isPrivate = chat.type === 'private';

  // Для private достаём собеседника
  const { data: members } = useQuery({
    queryKey: ['chat', chat.id, 'members'],
    queryFn: () => chatsApi.members(chat.id),
    enabled: open && (isPrivate || chat.type === 'group' || chat.type === 'supergroup' || chat.type === 'channel'),
  });

  const partnerId =
    isPrivate && members ? members.find((m) => m.user_id !== me?.id)?.user_id ?? null : null;

  return (
    <div
      className={cn(
        'thin-scrollbar shrink-0 overflow-hidden border-l border-line bg-bg transition-[width] duration-200 ease-out',
        open ? 'w-[360px]' : 'w-0',
      )}
    >
      {open && isPrivate && partnerId && (
        <UserProfilePanel userId={partnerId} onClose={onClose} />
      )}

      {open && isPrivate && !partnerId && (
        <div className="flex h-dvh items-center justify-center">
          <Spinner />
        </div>
      )}

      {open && !isPrivate && (
        <GroupOrChannelInfo chat={chat} members={members} onClose={onClose} />
      )}
    </div>
  );
}

function GroupOrChannelInfo({
  chat,
  members,
  onClose,
}: {
  chat: ChatOut;
  members: { user_id: number; username: string | null; avatar_url: string | null; role: string }[] | undefined;
  onClose: () => void;
}) {
  return (
    <div className="flex h-dvh flex-col overflow-hidden">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-line px-3 pt-safe">
        <h2 className="text-base font-medium">
          {chat.type === 'channel' ? 'Channel info' : 'Group info'}
        </h2>
        <button
          type="button"
          onClick={onClose}
          className="flex h-9 w-9 items-center justify-center rounded-md text-muted hover:bg-bg2"
          aria-label="Close"
        >
          <X className="h-5 w-5" />
        </button>
      </header>

      <div className="thin-scrollbar flex-1 overflow-y-auto">
        <div className="flex flex-col items-center gap-2 px-4 py-6">
          <Avatar src={chat.avatar_url} name={chat.title ?? chat.public_username ?? '?'} id={chat.id} size={112} />
          <div className="mt-2 text-xl font-semibold">{chat.title ?? chat.public_username ?? '—'}</div>
          {chat.public_username && <div className="text-sm text-accent">@{chat.public_username}</div>}
          {chat.description && <p className="mt-2 text-center text-sm text-muted">{chat.description}</p>}
          <div className="text-xs text-muted">
            {chat.members_count} {chat.type === 'channel' ? 'subscribers' : 'members'}
          </div>
        </div>

        {/* Channel stories */}
        <div className="border-t border-line py-2">
          <div className="px-4 pb-1 pt-1 text-xs uppercase tracking-wide text-muted">Stories</div>
          <UserStoriesGrid
            user={{
              id: chat.creator_id ?? chat.id,
              username: chat.public_username,
              full_name: chat.title,
              avatar_url: chat.avatar_url,
            }}
          />
        </div>

        <div className="border-t border-line">
          <div className="px-4 pb-1 pt-3 text-xs uppercase tracking-wide text-muted">
            {chat.type === 'channel' ? 'Subscribers' : 'Members'}
          </div>
          {!members ? (
            <div className="flex justify-center py-6">
              <Spinner />
            </div>
          ) : (
            <ul>
              {members.map((m) => (
                <li key={m.user_id} className="flex items-center gap-3 px-3 py-2 hover:bg-bg2">
                  <Avatar src={m.avatar_url} name={m.username ?? '?'} id={m.user_id} size={42} />
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-medium" style={{ color: nameColor(m.user_id) }}>
                      {m.username ?? `User ${m.user_id}`}
                    </div>
                    {m.role !== 'member' && <div className="text-xs text-muted">{m.role}</div>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
