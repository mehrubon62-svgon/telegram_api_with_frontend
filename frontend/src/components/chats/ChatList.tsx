import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { chatsApi } from '@/api/endpoints';
import type { ChatListItem, MessageOut } from '@/api/types';
import { ChatItem } from './ChatItem';
import { Spinner } from '@/components/ui/Spinner';
import { wsClient } from '@/ws/client';
import { usePresenceStore } from '@/store/presence';
import { useAuthStore } from '@/store/auth';

export function ChatList() {
  const { data, isLoading } = useQuery({
    queryKey: ['chats'],
    queryFn: () => chatsApi.list(),
    refetchOnMount: 'always',
  });
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { chatId } = useParams();
  const activeId = chatId ? Number(chatId) : null;
  const myId = useAuthStore((s) => s.me?.id);

  // Подписка на WS события: новое сообщение → бамп чата вверх + lastMessage
  useEffect(() => {
    const unsub = wsClient.subscribe((event) => {
      if (event.type === 'new_message' || event.type === 'message_edited') {
        const msg = event.message as MessageOut | undefined;
        if (!msg) return;
        queryClient.setQueryData<ChatListItem[]>(['chats'], (old) => {
          if (!old) return old;
          const idx = old.findIndex((c) => c.chat.id === msg.chat_id);
          if (idx === -1) {
            queryClient.invalidateQueries({ queryKey: ['chats'] });
            return old;
          }
          const item = old[idx]!;
          const fromOther = msg.sender?.id !== myId;
          const updated: ChatListItem = {
            ...item,
            chat: { ...item.chat, last_message_id: msg.id },
            unread_count:
              event.type === 'new_message' && fromOther && msg.chat_id !== activeId
                ? item.unread_count + 1
                : item.unread_count,
          };
          const next = [...old];
          next.splice(idx, 1);
          // Сортировка: pinned сверху, обычные в начало неперезакреплённых
          const firstNonPinned = next.findIndex((c) => !c.is_pinned);
          next.splice(firstNonPinned === -1 ? next.length : firstNonPinned, 0, updated);
          return next;
        });
      }
      if (event.type === 'presence') {
        usePresenceStore
          .getState()
          .setOnline(event.user_id as number, event.is_online as boolean, event.last_seen as string);
      }
      if (event.type === 'hello') {
        usePresenceStore.getState().setOnlineUsers((event.online_users as number[]) ?? []);
      }
      if (event.type === 'typing') {
        usePresenceStore.getState().setTyping(event.chat_id as number, event.user_id as number);
      }
      if (event.type === 'stop_typing') {
        usePresenceStore.getState().clearTyping(event.chat_id as number, event.user_id as number);
      }
    });
    return unsub;
  }, [queryClient, activeId]);

  // На reconnect — заново зачитать чаты
  useEffect(() => {
    wsClient.onReconnect(() => {
      queryClient.invalidateQueries({ queryKey: ['chats'] });
    });
  }, [queryClient]);

  if (isLoading) {
    return (
      <div className="flex justify-center py-10">
        <Spinner />
      </div>
    );
  }

  const items = data ?? [];
  if (items.length === 0) {
    return (
      <div className="px-6 py-10 text-center text-sm text-muted">
        No chats yet. Find someone via search at the top.
      </div>
    );
  }

  return (
    <div role="list">
      {items.map((it) => (
        <ChatItem
          key={it.chat.id}
          item={it}
          active={activeId === it.chat.id}
          onClick={() => navigate(`/chat/${it.chat.id}`)}
        />
      ))}
    </div>
  );
}
