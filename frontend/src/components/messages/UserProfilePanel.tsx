import { X, Phone, Video, MessageCircle, MoreHorizontal, Copy, UserPlus, UserMinus, Ban, Cake } from 'lucide-react';
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { authApi, blocksApi, callsApi, contactsApi } from '@/api/endpoints';
import { Avatar } from '@/components/ui/Avatar';
import { Spinner } from '@/components/ui/Spinner';
import { cn } from '@/lib/cn';
import { toast } from '@/components/ui/Toaster';
import { formatLastSeen } from '@/lib/format';
import { UserStoriesGrid } from '@/components/stories/UserStoriesGrid';
import { useCallsStore } from '@/store/calls';
import { format } from 'date-fns';

interface Props {
  userId: number;
  onClose: () => void;
}

type Tab = 'groups' | 'posts';

export function UserProfilePanel({ userId, onClose }: Props) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const setActiveCall = useCallsStore((s) => s.setActive);
  const [tab, setTab] = useState<Tab>('groups');

  const { data: profile, isLoading } = useQuery({
    queryKey: ['user-profile', userId],
    queryFn: () => authApi.getProfile(userId),
  });

  if (isLoading || !profile) {
    return (
      <div className="flex h-dvh w-full flex-col">
        <div className="flex h-14 items-center justify-between border-b border-line px-3 pt-safe">
          <span className="text-base font-medium">Info</span>
          <button onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-md text-muted hover:bg-bg2">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <Spinner />
        </div>
      </div>
    );
  }

  async function startCall(video: boolean): Promise<void> {
    try {
      const call = await callsApi.start({ callee_id: userId, type: video ? 'video' : 'audio', is_video: video });
      setActiveCall(call);
    } catch {
      toast.error('Could not start call');
    }
  }

  async function toggleContact(): Promise<void> {
    try {
      if (profile!.is_contact) {
        await contactsApi.remove(userId);
        toast.success('Removed from contacts');
      } else {
        await contactsApi.add({ user_id: userId });
        toast.success('Added to contacts');
      }
      queryClient.invalidateQueries({ queryKey: ['user-profile', userId] });
      queryClient.invalidateQueries({ queryKey: ['stories', 'feed'] });
    } catch {
      toast.error('Failed');
    }
  }

  async function toggleBlock(): Promise<void> {
    try {
      if (profile!.is_blocked) {
        await blocksApi.unblock(userId);
        toast.success('Unblocked');
      } else {
        await blocksApi.block(userId);
        toast.success('Blocked');
      }
      queryClient.invalidateQueries({ queryKey: ['user-profile', userId] });
    } catch {
      toast.error('Failed');
    }
  }

  return (
    <div className="flex h-dvh w-full flex-col bg-bg">
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-line px-3 pt-safe">
        <span className="text-base font-medium">Info</span>
        <button onClick={onClose} aria-label="Close" className="flex h-9 w-9 items-center justify-center rounded-md text-muted hover:bg-bg2">
          <X className="h-5 w-5" />
        </button>
      </header>

      <div className="thin-scrollbar flex-1 overflow-y-auto">
        {/* Аватар + имя */}
        <div className="flex flex-col items-center gap-1 px-4 py-6">
          <Avatar src={profile.avatar_url} name={profile.username ?? '?'} id={profile.id} size={112} />
          <div className="mt-3 text-xl font-semibold">
            {profile.full_name ?? profile.username ?? `User ${profile.id}`}
          </div>
          <div className="text-sm text-muted">{formatLastSeen(profile.last_seen)}</div>
        </div>

        {/* Action buttons */}
        <div className="grid grid-cols-3 gap-2 px-4">
          <ActionButton
            icon={<MessageCircle className="h-5 w-5" />}
            label="Message"
            onClick={async () => {
              const { chatsApi } = await import('@/api/endpoints');
              const chat = await chatsApi.createPrivate(userId);
              onClose();
              navigate(`/chat/${chat.id}`);
            }}
          />
          <ActionButton icon={<Phone className="h-5 w-5" />} label="Call" onClick={() => startCall(false)} />
          <ActionButton icon={<Video className="h-5 w-5" />} label="Video" onClick={() => startCall(true)} />
        </div>

        {/* Info card */}
        <div className="mx-4 mt-4 overflow-hidden rounded-xl bg-bg2">
          {profile.username && (
            <div className="flex items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <div className="text-xs text-muted">username</div>
                <div className="truncate text-accent">@{profile.username}</div>
              </div>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(`@${profile.username}`).catch(() => {});
                  toast.success('Copied');
                }}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-muted hover:bg-bg3"
                aria-label="Copy username"
              >
                <Copy className="h-4 w-4" />
              </button>
            </div>
          )}

          {profile.bio && (
            <div className="border-t border-line px-4 py-3">
              <div className="text-xs text-muted">bio</div>
              <div className="whitespace-pre-wrap text-sm">{profile.bio}</div>
            </div>
          )}

          {profile.birthday && (
            <div className="flex items-center gap-3 border-t border-line px-4 py-3">
              <Cake className="h-5 w-5 text-muted" />
              <div>
                <div className="text-sm">{format(new Date(profile.birthday), 'd MMMM')}</div>
                <div className="text-xs text-muted">Date of birth</div>
              </div>
            </div>
          )}

          <button
            onClick={toggleContact}
            className="flex w-full items-center gap-3 border-t border-line px-4 py-3 text-left text-accent hover:bg-bg3"
          >
            {profile.is_contact ? <UserMinus className="h-5 w-5" /> : <UserPlus className="h-5 w-5" />}
            {profile.is_contact ? 'Remove Contact' : 'Add Contact'}
          </button>

          <button
            onClick={toggleBlock}
            className="flex w-full items-center gap-3 border-t border-line px-4 py-3 text-left text-danger hover:bg-danger/10"
          >
            <Ban className="h-5 w-5" />
            {profile.is_blocked ? 'Unblock User' : 'Block User'}
          </button>
        </div>

        {/* Tabs */}
        <div className="mt-4 flex border-b border-line">
          <TabButton active={tab === 'groups'} label="Groups" onClick={() => setTab('groups')} />
          <TabButton active={tab === 'posts'} label="Posts" onClick={() => setTab('posts')} />
        </div>

        {tab === 'groups' ? (
          <div>
            {profile.common_chats.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-muted">No groups in common</div>
            ) : (
              <ul>
                {profile.common_chats.map((c) => (
                  <li key={c.id}>
                    <button
                      onClick={() => {
                        onClose();
                        navigate(`/chat/${c.id}`);
                      }}
                      className="flex w-full items-center gap-3 px-4 py-2 text-left hover:bg-bg2"
                    >
                      <Avatar src={c.avatar_url} name={c.title ?? c.public_username ?? '?'} id={c.id} size={42} />
                      <div className="min-w-0">
                        <div className="truncate font-medium">{c.title ?? c.public_username}</div>
                        <div className="text-xs text-muted">{c.members_count} members</div>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <div className="py-2">
            <UserStoriesGrid
              user={{
                id: profile.id,
                username: profile.username,
                full_name: profile.full_name,
                avatar_url: profile.avatar_url,
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function ActionButton({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-center gap-1 rounded-xl bg-bg2 py-3 text-accent transition-colors hover:bg-bg3"
    >
      {icon}
      <span className="text-xs">{label}</span>
    </button>
  );
}

function TabButton({ active, label, onClick }: { active: boolean; label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'relative flex-1 py-3 text-sm font-medium transition-colors',
        active ? 'text-accent' : 'text-muted hover:text-text',
      )}
    >
      {label}
      {active && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-accent" />}
    </button>
  );
}

// Подавляем неиспользуемый импорт MoreHorizontal — оставлен для возможного More-меню
void MoreHorizontal;
