import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef } from 'react';
import { messagesApi } from '@/api/endpoints';
import type { MessageOut } from '@/api/types';
import { wsClient } from '@/ws/client';
import { Spinner } from '@/components/ui/Spinner';
import { MessageBubble } from './MessageBubble';
import { DaySeparator } from './DaySeparator';
import { isSameDay } from 'date-fns';

interface Props {
  chatId: number;
  chatType: import('@/api/types').ChatType;
}

export function MessageList({ chatId, chatType }: Props) {
  const queryClient = useQueryClient();
  const containerRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);

  const { data, isLoading } = useQuery({
    queryKey: ['chat', chatId, 'messages'],
    queryFn: () => messagesApi.history(chatId, { limit: 80 }),
  });

  // Подписка на WS события — мутируем кэш query
  useEffect(() => {
    const unsub = wsClient.subscribe((event) => {
      if (event.type === 'new_message') {
        const msg = event.message as MessageOut | undefined;
        if (!msg || msg.chat_id !== chatId) return;
        queryClient.setQueryData<MessageOut[]>(['chat', chatId, 'messages'], (old) => {
          const list = old ?? [];
          if (list.some((m) => m.id === msg.id)) return list;
          return [...list, msg];
        });
        // Помечаем прочитанным сразу, если мы в чате
        if (document.visibilityState === 'visible') {
          wsClient.send({ type: 'read', chat_id: chatId, message_id: msg.id });
        }
      } else if (event.type === 'message_edited') {
        const msg = event.message as MessageOut | undefined;
        if (!msg || msg.chat_id !== chatId) return;
        queryClient.setQueryData<MessageOut[]>(['chat', chatId, 'messages'], (old) => {
          if (!old) return old;
          return old.map((m) => (m.id === msg.id ? msg : m));
        });
      } else if (event.type === 'message_deleted') {
        if (event.chat_id !== chatId) return;
        const mid = event.message_id as number;
        const node = document.querySelector<HTMLElement>(`[data-message-id="${mid}"]`);
        const removeFromCache = (): void => {
          queryClient.setQueryData<MessageOut[]>(['chat', chatId, 'messages'], (old) => {
            if (!old) return old;
            return old.filter((m) => m.id !== mid);
          });
        };
        if (node) {
          import('@/lib/dissolve').then(({ playDissolve }) => {
            playDissolve(node).then(removeFromCache);
          });
        } else {
          removeFromCache();
        }
      } else if (event.type === 'reaction') {
        if (event.chat_id !== chatId) return;
        const mid = event.message_id as number;
        const userId = event.user_id as number;
        const emoji = event.emoji as string;
        queryClient.setQueryData<MessageOut[]>(['chat', chatId, 'messages'], (old) => {
          if (!old) return old;
          return old.map((m) => {
            if (m.id !== mid) return m;
            const reactions = [...(m.reactions ?? [])];
            const idx = reactions.findIndex((r) => r.emoji === emoji);
            if (idx === -1) {
              // новой эмодзи ещё не было — toggle on
              reactions.push({ emoji, count: 1, chosen: false, user_ids: [userId] });
            } else {
              const r = reactions[idx]!;
              const has = r.user_ids.includes(userId);
              const nextUsers = has ? r.user_ids.filter((u) => u !== userId) : [...r.user_ids, userId];
              if (nextUsers.length === 0) {
                reactions.splice(idx, 1);
              } else {
                reactions[idx] = { ...r, user_ids: nextUsers, count: nextUsers.length };
              }
            }
            return { ...m, reactions };
          });
        });
      }
    });
    return unsub;
  }, [chatId, queryClient]);

  // Авто-прокрутка к низу при новых сообщениях, если пользователь и так был внизу
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    if (stickToBottomRef.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [data?.length]);

  // Отслеживаем, прижат ли скролл вниз
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onScroll = (): void => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickToBottomRef.current = distance < 60;
    };
    el.addEventListener('scroll', onScroll, { passive: true });
    return () => el.removeEventListener('scroll', onScroll);
  }, []);

  // Авто-mark read при открытии чата
  useEffect(() => {
    if (!data || data.length === 0) return;
    const last = data[data.length - 1];
    if (!last) return;
    wsClient.send({ type: 'read', chat_id: chatId, message_id: last.id });
  }, [chatId, data]);

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  const messages = data ?? [];
  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center text-sm text-muted">
        No messages yet. Say hi!
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="thin-scrollbar flex-1 overflow-y-auto px-2 py-2 sm:px-4"
    >
      <div className="flex flex-col gap-1">
        {messages.map((m, i) => {
          const prev = messages[i - 1];
          const showDay = !prev || !isSameDay(new Date(m.created_at), new Date(prev.created_at));
          const groupedWithPrev =
            !showDay && prev && prev.sender?.id === m.sender?.id && i > 0;
          return (
            <div key={m.id}>
              {showDay && <DaySeparator iso={m.created_at} />}
              <MessageBubble message={m} grouped={!!groupedWithPrev} chatType={chatType} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
