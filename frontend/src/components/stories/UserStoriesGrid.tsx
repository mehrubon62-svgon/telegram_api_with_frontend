import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { storiesApi } from '@/api/endpoints';
import { mediaUrl } from '@/lib/url';
import { Spinner } from '@/components/ui/Spinner';
import { StoryViewer } from './StoryViewer';
import type { StoryFeedItem, StoryAuthor } from '@/api/types';

interface Props {
  user: StoryAuthor;
}

/**
 * Лента сторис конкретного пользователя в профиле.
 * Показываем активные (не истекшие) + закреплённые (pinned).
 */
export function UserStoriesGrid({ user }: Props) {
  const { data: active, isLoading: l1 } = useQuery({
    queryKey: ['user-stories', user.id, 'active'],
    queryFn: () => storiesApi.byUser(user.id),
  });
  const { data: pinned, isLoading: l2 } = useQuery({
    queryKey: ['user-stories', user.id, 'pinned'],
    queryFn: () => storiesApi.pinnedByUser(user.id),
  });

  const [openIdx, setOpenIdx] = useState<number | null>(null);

  if (l1 || l2) {
    return (
      <div className="flex justify-center py-4">
        <Spinner />
      </div>
    );
  }

  // Объединим (pinned идут отдельной секцией ниже)
  const list = active ?? [];
  const pinnedList = (pinned ?? []).filter(
    (s) => !list.some((a) => a.id === s.id),
  );

  if (list.length === 0 && pinnedList.length === 0) {
    return (
      <div className="px-4 py-3 text-center text-xs text-muted">
        No stories
      </div>
    );
  }

  // Подаём в StoryViewer как один автор
  const feedItem: StoryFeedItem = {
    author: user,
    has_unviewed: list.some((s) => !s.is_viewed),
    stories: [...list, ...pinnedList],
  };

  return (
    <div>
      {list.length > 0 && (
        <Section title="Active stories">
          <Grid stories={list} onOpen={(i) => setOpenIdx(i)} />
        </Section>
      )}
      {pinnedList.length > 0 && (
        <Section title="Pinned to profile">
          <Grid
            stories={pinnedList}
            onOpen={(i) => setOpenIdx(list.length + i)}
            archived
          />
        </Section>
      )}

      {openIdx !== null && (
        <StoryViewer
          authors={[feedItem]}
          startIndex={0}
          onClose={() => setOpenIdx(null)}
        />
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="px-4 pb-1 pt-2 text-xs uppercase tracking-wide text-muted">{title}</div>
      {children}
    </div>
  );
}

function Grid({
  stories,
  onOpen,
  archived,
}: {
  stories: { id: number; media_url: string; thumbnail_url: string | null; is_viewed: boolean }[];
  onOpen: (idx: number) => void;
  archived?: boolean;
}) {
  return (
    <div className="grid grid-cols-3 gap-1 px-2">
      {stories.map((s, i) => (
        <button
          key={s.id}
          type="button"
          onClick={() => onOpen(i)}
          className="relative aspect-[9/16] overflow-hidden rounded-md transition-transform active:scale-95"
        >
          <img
            src={mediaUrl(s.thumbnail_url ?? s.media_url)}
            alt=""
            loading="lazy"
            className="h-full w-full object-cover"
          />
          {!s.is_viewed && !archived && (
            <span className="absolute right-1 top-1 h-2.5 w-2.5 rounded-full border-2 border-bg bg-accent" />
          )}
        </button>
      ))}
    </div>
  );
}
