import { X } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import type { ChatOut } from '@/api/types';
import { chatsApi } from '@/api/endpoints';
import { Avatar } from '@/components/ui/Avatar';
import { Spinner } from '@/components/ui/Spinner';
import { cn } from '@/lib/cn';
import { nameColor } from '@/lib/colors';
import { UserStoriesGrid } from '@/components/stories/UserStoriesGrid';
import { useAuthStore } from '@/store/auth';

interface Props {
  chat: ChatOut;
  open: boolean;
  onClose: () => void;
}

export function ChatProfilePanel({ chat, open, onClose }: Props) {
  const me = useAuthStore((s) => s.me);
  const { data: members, isLoading } = useQuery({
    queryKey: ['chat', chat.id, 'members'],
    queryFn: () => chatsApi.members(chat.id),
    enabled: open && (chat.type === 'group' || chat.type === 'supergroup' || chat.type === 'channel'),
  });

  // для private — найдём собеседника, чтобы показать его сторис
  const partner = (() => {
    if (!open) return null;
    if (chat.type !== 'private') return null;
    if (!members) return null;
    return members.find((m) => m.user_id !== me?.id) ?? null;
  })();

  const showStoriesFor =
    open && chat.type === 'private'
      ? partner
        ? { id: partner.user_id, username: partner.username, full_name: partner.full_name, avatar_url: partner.avatar_url }
        : null
      : null;

  // для private загрузим members чтобы найти собеседника, даже если query disabled
  const { data: privateMembers } = useQuery({
    queryKey: ['chat', chat.id, 'members'],
    queryFn: () => chatsApi.members(chat.id),
    enabled: open && chat.type === 'private',
  });
  const realPartner = privateMembers?.find((m) => m.user_id !== me?.id);

  const finalPartner =
    showStoriesFor ??
    (realPartner
      ? {
          id: realPartner.user_id,
          username: realPartner.username,
          full_name: realPartner.full_name,
          avatar_url: realPartner.avatar_url,
        }
      : null);

  return (
    <div
      className={cn(
        'thin-scrollbar shrink-0 overflow-hidden border-l border-line bg-bg transition-[width] duration-200 ease-out',
        open ? 'w-[340px]' : 'w-0',
      )}
    >
      {open && (
        <div className="flex h-dvh flex-col overflow-hidden">
          <header className="flex h-14 shrink-0 items-center justify-between border-b border-line px-3 pt-safe">
            <h2 className="text-base font-medium">
              {chat.type === 'private' || chat.type === 'saved'
                ? 'User info'
                : chat.type === 'channel'
                  ? 'Channel info'
                  : 'Group info'}
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
              <Avatar
                src={
                  chat.type === 'private'
                    ? finalPartner?.avatar_url ?? null
                    : chat.avatar_url
                }
                name={
                  chat.type === 'private'
                    ? finalPartner?.username ?? '?'
                    : chat.title ?? chat.public_username ?? '?'
                }
                id={
                  chat.type === 'private'
                    ? finalPartner?.id ?? chat.id
                    : chat.id
                }
                size={120}
              />
              <div className="text-xl font-semibold">
                {chat.type === 'private'
                  ? finalPartner?.username ?? '—'
                  : chat.title ?? chat.public_username ?? '—'}
              </div>
              {chat.public_username && chat.type !== 'private' && (
                <div className="text-sm text-accent">{chat.public_username}</div>
              )}
              {chat.description && (
                <p className="mt-2 text-center text-sm text-muted">{chat.description}</p>
              )}
              {chat.type !== 'private' && chat.type !== 'saved' && (
                <div className="text-xs text-muted">
                  {chat.members_count} {chat.type === 'channel' ? 'subscribers' : 'members'}
                </div>
              )}
            </div>

            {/* Stories */}
            {chat.type === 'private' && finalPartner && (
              <div className="border-t border-line py-2">
                <UserStoriesGrid user={finalPartner} />
              </div>
            )}
            {(chat.type === 'group' || chat.type === 'supergroup' || chat.type === 'channel') && (
              <div className="border-t border-line py-2">
                <div className="px-4 pb-1 pt-1 text-xs uppercase tracking-wide text-muted">
                  Channel stories
                </div>
                <UserStoriesGrid
                  user={{
                    id: chat.creator_id ?? chat.id,
                    username: chat.public_username,
                    full_name: chat.title,
                    avatar_url: chat.avatar_url,
                  }}
                />
              </div>
            )}

            {(chat.type === 'group' || chat.type === 'supergroup' || chat.type === 'channel') && (
              <div className="border-t border-line">
                <div className="px-4 pb-1 pt-3 text-xs uppercase tracking-wide text-muted">
                  {chat.type === 'channel' ? 'Subscribers' : 'Members'}
                </div>
                {isLoading ? (
                  <div className="flex justify-center py-6">
                    <Spinner />
                  </div>
                ) : (
                  <ul>
                    {members?.map((m) => (
                      <li key={m.user_id} className="flex items-center gap-3 px-3 py-2 hover:bg-bg2">
                        <Avatar src={m.avatar_url} name={m.username ?? '?'} id={m.user_id} size={42} />
                        <div className="min-w-0 flex-1">
                          <div
                            className="truncate text-sm font-medium"
                            style={{ color: nameColor(m.user_id) }}
                          >
                            {m.username ?? `User ${m.user_id}`}
                          </div>
                          {m.role !== 'member' && (
                            <div className="text-xs text-muted">{m.role}</div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
