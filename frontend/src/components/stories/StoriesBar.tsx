import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Plus } from 'lucide-react';
import { useEffect, useState } from 'react';
import { storiesApi } from '@/api/endpoints';
import { Avatar } from '@/components/ui/Avatar';
import { useAuthStore } from '@/store/auth';
import { StoryViewer } from './StoryViewer';
import { StoryEditor } from './StoryEditor';
import { wsClient } from '@/ws/client';
import type { StoryFeedItem } from '@/api/types';

export function StoriesBar() {
  const me = useAuthStore((s) => s.me);
  const queryClient = useQueryClient();
  const { data } = useQuery({
    queryKey: ['stories', 'feed'],
    queryFn: () => storiesApi.feed(),
    staleTime: 30_000,
  });
  const [openIndex, setOpenIndex] = useState<number | null>(null);
  const [editor, setEditor] = useState(false);

  // Подписка на WS: views счётчик + изменение контактов
  useEffect(() => {
    const unsub = wsClient.subscribe((event) => {
      if (event.type === 'story_viewed') {
        const sid = event.story_id as number;
        const views = event.views_count as number;
        queryClient.setQueryData<StoryFeedItem[]>(['stories', 'feed'], (old) => {
          if (!old) return old;
          return old.map((item) => {
            const idx = item.stories.findIndex((s) => s.id === sid);
            if (idx === -1) return item;
            const stories = item.stories.slice();
            stories[idx] = { ...stories[idx]!, views_count: views };
            return { ...item, stories };
          });
        });
      }
      if (event.type === 'contact_changed') {
        // Контакт добавлен/удалён — лента сторис зависит от контактов
        queryClient.invalidateQueries({ queryKey: ['stories', 'feed'] });
        const cid = event.contact_id as number | undefined;
        if (cid) {
          queryClient.invalidateQueries({ queryKey: ['user-profile', cid] });
        }
      }
    });
    return unsub;
  }, [queryClient]);

  const items = data ?? [];

  // Свой блок: если есть свои сторис — показываем их аватар (как все),
  // плюс всегда есть кнопка с плюсиком
  const myItem = items.find((it) => it.author.id === me?.id);
  const others = items.filter((it) => it.author.id !== me?.id);

  return (
    <>
      <div className="thin-scrollbar flex gap-3 overflow-x-auto border-b border-line bg-bg px-3 py-3">
        {/* Свой круг — кнопка добавления, без сине-градиентного ободка */}
        <button
          type="button"
          onClick={() => setEditor(true)}
          className="flex w-16 shrink-0 flex-col items-center gap-1"
        >
          <span className="relative">
            <span className="flex h-16 w-16 items-center justify-center rounded-full bg-line p-[2px] transition-transform active:scale-95">
              <span className="flex h-full w-full items-center justify-center rounded-full bg-bg p-[2px]">
                <Avatar
                  src={me?.avatar_url ?? null}
                  name={me?.username ?? '?'}
                  id={me?.id ?? 0}
                  size={56}
                />
              </span>
            </span>
            <span className="absolute bottom-0 right-0 flex h-5 w-5 items-center justify-center rounded-full border-2 border-bg bg-accent text-white">
              <Plus className="h-3 w-3" strokeWidth={3} />
            </span>
          </span>
          <span className="w-full truncate text-xs text-text/80">Your story</span>
        </button>

        {/* Если у меня есть свои сторис, рядом дам клик «открыть мои» */}
        {myItem && (
          <button
            type="button"
            onClick={() => setOpenIndex(items.indexOf(myItem))}
            className="flex w-16 shrink-0 flex-col items-center gap-1"
          >
            <span
              className={
                'flex h-16 w-16 items-center justify-center rounded-full p-[2px] transition-transform active:scale-95 ' +
                (myItem.has_unviewed
                  ? 'bg-gradient-to-tr from-accent via-accentHover to-accent'
                  : 'bg-line')
              }
            >
              <span className="flex h-full w-full items-center justify-center rounded-full bg-bg p-[2px]">
                <Avatar
                  src={me?.avatar_url ?? null}
                  name={me?.username ?? '?'}
                  id={me?.id ?? 0}
                  size={56}
                />
              </span>
            </span>
            <span className="w-full truncate text-xs text-text/80">My story</span>
          </button>
        )}

        {others.map((item) => {
          const idx = items.indexOf(item);
          return (
            <button
              key={item.author.id}
              type="button"
              onClick={() => setOpenIndex(idx)}
              className="flex w-16 shrink-0 flex-col items-center gap-1"
            >
              <span
                className={
                  'flex h-16 w-16 items-center justify-center rounded-full p-[2px] transition-transform active:scale-95 ' +
                  (item.has_unviewed
                    ? 'bg-gradient-to-tr from-accent via-accentHover to-accent'
                    : 'bg-line')
                }
              >
                <span className="flex h-full w-full items-center justify-center rounded-full bg-bg p-[2px]">
                  <Avatar
                    src={item.author.avatar_url}
                    name={item.author.username ?? '?'}
                    id={item.author.id}
                    size={56}
                  />
                </span>
              </span>
              <span className="w-full truncate text-xs text-text/80">
                {item.author.username ?? `User ${item.author.id}`}
              </span>
            </button>
          );
        })}
      </div>
      {openIndex !== null && (
        <StoryViewer
          authors={items}
          startIndex={openIndex}
          onClose={() => setOpenIndex(null)}
        />
      )}
      {editor && <StoryEditor onClose={() => setEditor(false)} />}
    </>
  );
}
