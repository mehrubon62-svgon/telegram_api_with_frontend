import { ChevronLeft, ChevronRight, X, Heart, Send, Eye, Trash2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import type { StoryFeedItem } from '@/api/types';
import { mediaUrl } from '@/lib/url';
import { storiesApi } from '@/api/endpoints';
import { useAuthStore } from '@/store/auth';
import { toast } from '@/components/ui/Toaster';

interface Props {
  authors: StoryFeedItem[];
  startIndex: number;
  onClose: () => void;
}

const PHOTO_DURATION = 5000;
const QUICK_REACTIONS = ['❤️', '🔥', '😂', '😮', '👍', '🎉'];

export function StoryViewer({ authors, startIndex, onClose }: Props) {
  const me = useAuthStore((s) => s.me);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [authorIdx, setAuthorIdx] = useState(startIndex);
  const [storyIdx, setStoryIdx] = useState(0);
  const [progress, setProgress] = useState(0);
  const [paused, setPaused] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [sending, setSending] = useState(false);
  const startedAtRef = useRef<number>(performance.now());
  const elapsedRef = useRef<number>(0); // pause-aware
  const rafRef = useRef<number | null>(null);

  const currentAuthor = authors[authorIdx];
  const currentStory = currentAuthor?.stories[storyIdx];
  const isOwn = me?.id === currentAuthor?.author.id;

  // Авто-mark viewed
  useEffect(() => {
    if (!currentStory) return;
    storiesApi.get(currentStory.id).catch(() => {});
  }, [currentStory?.id]);

  // Прогресс
  useEffect(() => {
    if (!currentStory) return;
    elapsedRef.current = 0;
    startedAtRef.current = performance.now();
    setProgress(0);
    const dur =
      currentStory.media_type === 'video'
        ? Math.max(2000, (currentStory.duration ?? 5) * 1000)
        : PHOTO_DURATION;

    const tick = (): void => {
      if (paused) {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      const now = performance.now();
      elapsedRef.current += now - startedAtRef.current;
      startedAtRef.current = now;
      const t = elapsedRef.current / dur;
      if (t >= 1) {
        next();
        return;
      }
      setProgress(t);
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStory?.id, paused]);

  function next(): void {
    if (!currentAuthor) return;
    if (storyIdx + 1 < currentAuthor.stories.length) {
      setStoryIdx((i) => i + 1);
    } else if (authorIdx + 1 < authors.length) {
      setAuthorIdx((i) => i + 1);
      setStoryIdx(0);
    } else {
      onClose();
    }
  }

  function prev(): void {
    if (storyIdx > 0) {
      setStoryIdx((i) => i - 1);
    } else if (authorIdx > 0) {
      setAuthorIdx((i) => i - 1);
      const prevAuthor = authors[authorIdx - 1];
      setStoryIdx((prevAuthor?.stories.length ?? 1) - 1);
    }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent): void {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowRight') next();
      if (e.key === 'ArrowLeft') prev();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authorIdx, storyIdx]);

  async function react(emoji: string): Promise<void> {
    if (!currentStory || isOwn) return;
    try {
      await storiesApi.react(currentStory.id, emoji);
      toast.success(`Reacted ${emoji}`);
    } catch {
      // ignore
    }
  }

  async function sendReply(): Promise<void> {
    if (!currentStory || !replyText.trim() || isOwn) return;
    setSending(true);
    try {
      const r = await storiesApi.reply(currentStory.id, replyText.trim());
      toast.success('Reply sent');
      setReplyText('');
      onClose();
      navigate(`/chat/${r.chat_id}`);
    } catch {
      toast.error('Failed');
    } finally {
      setSending(false);
    }
  }

  async function remove(): Promise<void> {
    if (!currentStory) return;
    if (!confirm('Delete this story?')) return;
    try {
      await storiesApi.remove(currentStory.id);
      queryClient.invalidateQueries({ queryKey: ['stories', 'feed'] });
      queryClient.invalidateQueries({ queryKey: ['user-stories'] });
      onClose();
    } catch {
      toast.error('Failed to delete');
    }
  }

  if (!currentAuthor || !currentStory) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[300] flex items-center justify-center bg-black/95 animate-fade-in"
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative flex h-full max-h-[100dvh] w-full max-w-[420px] flex-col"
      >
        {/* Прогресс */}
        <div className="flex gap-1 px-3 pt-3 pt-safe">
          {currentAuthor.stories.map((_, i) => (
            <div key={i} className="h-1 flex-1 overflow-hidden rounded bg-white/20">
              <div
                className="h-full bg-white"
                style={{
                  width:
                    i < storyIdx
                      ? '100%'
                      : i === storyIdx
                        ? `${progress * 100}%`
                        : '0%',
                  transition: i === storyIdx ? 'none' : 'width 0.2s',
                }}
              />
            </div>
          ))}
        </div>

        {/* Шапка */}
        <div className="flex items-center gap-2 px-3 py-2 text-white">
          <div className="flex-1 truncate text-sm font-medium">
            {currentAuthor.author.username ?? `User ${currentAuthor.author.id}`}
          </div>
          {isOwn && (
            <button
              type="button"
              onClick={remove}
              aria-label="Delete"
              className="flex h-9 w-9 items-center justify-center rounded-full text-white/80 hover:bg-white/10"
            >
              <Trash2 className="h-5 w-5" />
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="flex h-9 w-9 items-center justify-center rounded-full hover:bg-white/10"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Медиа */}
        <div
          className="relative flex flex-1 items-center justify-center"
          onPointerDown={() => setPaused(true)}
          onPointerUp={() => setPaused(false)}
          onPointerCancel={() => setPaused(false)}
        >
          {currentStory.media_type === 'video' ? (
            <video
              key={currentStory.id}
              src={mediaUrl(currentStory.media_url)}
              autoPlay
              playsInline
              muted={false}
              className="max-h-full max-w-full object-contain"
            />
          ) : (
            <img
              key={currentStory.id}
              src={mediaUrl(currentStory.media_url)}
              alt=""
              className="max-h-full max-w-full object-contain"
            />
          )}

          <button
            type="button"
            aria-label="Previous"
            onClick={(e) => {
              e.stopPropagation();
              prev();
            }}
            className="absolute inset-y-0 left-0 w-1/3 cursor-pointer"
          />
          <button
            type="button"
            aria-label="Next"
            onClick={(e) => {
              e.stopPropagation();
              next();
            }}
            className="absolute inset-y-0 right-0 w-2/3 cursor-pointer"
          />

          {currentStory.caption && (
            <div className="pointer-events-none absolute bottom-20 left-0 right-0 px-4 text-center text-sm text-white drop-shadow-lg">
              {currentStory.caption}
            </div>
          )}
        </div>

        {/* Низ */}
        {isOwn ? (
          <ViewersFooter storyId={currentStory.id} viewsCount={currentStory.views_count} />
        ) : (
          <div className="space-y-2 px-3 py-3 pb-safe">
            <div className="flex justify-center gap-2">
              {QUICK_REACTIONS.map((e) => (
                <button
                  key={e}
                  type="button"
                  onClick={() => react(e)}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-xl transition-transform hover:scale-110 active:scale-95"
                >
                  {e}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                aria-label="Previous"
                onClick={prev}
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white/70 hover:bg-white/10"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
              <input
                value={replyText}
                onChange={(e) => setReplyText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendReply()}
                onFocus={() => setPaused(true)}
                onBlur={() => setPaused(false)}
                placeholder={`Reply to ${currentAuthor.author.username ?? 'user'}…`}
                disabled={!currentStory.allow_replies}
                className="h-10 flex-1 rounded-full bg-white/10 px-4 text-sm text-white placeholder:text-white/50 outline-none disabled:opacity-50"
              />
              {replyText.trim() ? (
                <button
                  type="button"
                  disabled={sending}
                  onClick={sendReply}
                  aria-label="Send"
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-accent text-white"
                >
                  <Send className="h-4 w-4" />
                </button>
              ) : (
                <>
                  {currentStory.allow_reactions && (
                    <button
                      type="button"
                      onClick={() => react('❤️')}
                      aria-label="Like"
                      className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white/80 hover:bg-white/10"
                    >
                      <Heart className="h-5 w-5" />
                    </button>
                  )}
                  <button
                    type="button"
                    aria-label="Next"
                    onClick={next}
                    className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white/70 hover:bg-white/10"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>,
    document.body,
  );
}

function ViewersFooter({ storyId, viewsCount }: { storyId: number; viewsCount: number }) {
  const [show, setShow] = useState(false);
  return (
    <div className="px-4 py-3 pb-safe">
      <button
        type="button"
        onClick={() => setShow((v) => !v)}
        className="flex w-full items-center justify-center gap-2 rounded-full bg-white/10 py-2 text-sm text-white/90 hover:bg-white/20"
      >
        <Eye className="h-4 w-4" />
        {viewsCount === 0
          ? 'No views yet'
          : `${viewsCount} ${viewsCount === 1 ? 'view' : 'views'}`}
      </button>
      {show && <ViewersList storyId={storyId} />}
    </div>
  );
}

function ViewersList({ storyId }: { storyId: number }) {
  // Используем встроенный fetch на эндпоинт viewers
  const [viewers, setViewers] = useState<
    Array<{ user_id: number; username: string | null; avatar_url: string | null; reaction: string | null }>
  >([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const tok = useAuthStore.getState().accessToken;
        const r = await fetch(`http://127.0.0.1:8000/stories/${storyId}/viewers`, {
          headers: { Authorization: `Bearer ${tok ?? ''}` },
        });
        const data = await r.json();
        if (!cancelled) setViewers(data ?? []);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [storyId]);

  if (loading) return <div className="py-3 text-center text-sm text-white/60">Loading…</div>;
  if (viewers.length === 0) return null;

  return (
    <ul className="thin-scrollbar mt-2 max-h-44 overflow-y-auto rounded-lg bg-white/5">
      {viewers.map((v) => (
        <li key={v.user_id} className="flex items-center gap-2 px-3 py-2 text-sm text-white">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/10 text-xs">
            {(v.username ?? '?').slice(0, 1).toUpperCase()}
          </span>
          <span className="flex-1 truncate">{v.username ?? `User ${v.user_id}`}</span>
          {v.reaction && <span className="text-base">{v.reaction}</span>}
        </li>
      ))}
    </ul>
  );
}
