import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { authApi, chatsApi, messagesApi } from '@/api/endpoints';
import { Avatar } from '@/components/ui/Avatar';
import { Spinner } from '@/components/ui/Spinner';
import { useAuthStore } from '@/store/auth';
import type { ChatOut } from '@/api/types';

interface Props {
  query: string;
  onClose: () => void;
}

export function GlobalSearch({ query, onClose }: Props) {
  const navigate = useNavigate();
  const { data: users, isFetching: u1 } = useQuery({
    queryKey: ['search-users', query],
    queryFn: () => authApi.searchUsers(query),
    enabled: query.length > 0,
  });
  const { data: publicChats, isFetching: u3 } = useQuery({
    queryKey: ['search-public-chats', query],
    queryFn: async () => {
      const r = await fetch(`http://127.0.0.1:8000/chats/search?q=${encodeURIComponent(query)}`, {
        headers: { Authorization: `Bearer ${useAuthStore.getState().accessToken ?? ''}` },
      });
      return (await r.json()) as ChatOut[];
    },
    enabled: query.length > 0,
  });
  const { data: messages, isFetching: u2 } = useQuery({
    queryKey: ['search-messages', query],
    queryFn: () => messagesApi.searchGlobal(query),
    enabled: query.length > 1,
  });

  async function openWithUser(uid: number) {
    const chat = await chatsApi.createPrivate(uid);
    onClose();
    navigate(`/chat/${chat.id}`);
  }

  if (u1 && u2 && u3) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  return (
    <div>
      {users && users.length > 0 && (
        <Section title="Users">
          {users.map((u) => (
            <button
              key={u.id}
              onClick={() => openWithUser(u.id)}
              className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-bg2"
            >
              <Avatar src={u.avatar_url} name={u.username ?? '?'} id={u.id} size={42} online={u.is_online} />
              <div className="min-w-0">
                <div className="truncate font-medium">
                  {u.username ?? `User ${u.id}`}
                </div>
                {u.bio && <div className="truncate text-sm text-muted">{u.bio}</div>}
              </div>
            </button>
          ))}
        </Section>
      )}
      {publicChats && publicChats.length > 0 && (
        <Section title="Groups & Channels">
          {publicChats.map((c) => (
            <button
              key={c.id}
              onClick={() => {
                onClose();
                navigate(`/chat/${c.id}`);
              }}
              className="flex w-full items-center gap-3 px-3 py-2 text-left hover:bg-bg2"
            >
              <Avatar src={c.avatar_url} name={c.title ?? c.public_username ?? '?'} id={c.id} size={42} />
              <div className="min-w-0">
                <div className="truncate font-medium">{c.title ?? c.public_username}</div>
                <div className="truncate text-sm text-muted">
                  {c.public_username} · {c.type}
                </div>
              </div>
            </button>
          ))}
        </Section>
      )}
      {messages && messages.length > 0 && (
        <Section title="Messages">
          {messages.map((m) => (
            <button
              key={m.id}
              onClick={() => {
                onClose();
                navigate(`/chat/${m.chat_id}`);
              }}
              className="flex w-full items-start gap-3 px-3 py-2 text-left hover:bg-bg2"
            >
              <Avatar src={m.sender?.avatar_url} name={m.sender?.username ?? '?'} id={m.sender?.id ?? m.id} size={42} />
              <div className="min-w-0">
                <div className="truncate text-sm font-medium">
                  {m.sender?.username ? `@${m.sender.username}` : 'User'}
                </div>
                <div className="truncate text-sm text-muted">{m.text}</div>
              </div>
            </button>
          ))}
        </Section>
      )}
      {users?.length === 0 && messages?.length === 0 && (publicChats?.length ?? 0) === 0 && (
        <div className="px-6 py-10 text-center text-sm text-muted">
          Nothing found.
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="py-2">
      <div className="px-4 pb-1 text-xs uppercase tracking-wide text-muted">{title}</div>
      {children}
    </div>
  );
}
