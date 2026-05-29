import { Eye, MessageSquare, Pencil, Share2 } from 'lucide-react';
import { useState } from 'react';
import type { ChatType, MessageOut } from '@/api/types';
import { useNavigate } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { mediaUrl } from '@/lib/url';
import { useQuery } from '@tanstack/react-query';
import { chatsApi, messagesApi } from '@/api/endpoints';
import { formatMessageTime } from '@/lib/format';
import { useAuthStore } from '@/store/auth';
import { ContextMenu } from './ContextMenu';
import { useComposerStore } from '@/store/composer';
import { useQueryClient } from '@tanstack/react-query';
import { playDissolve } from '@/lib/dissolve';

interface Props {
  message: MessageOut;
  chatType: ChatType;
  canPin: boolean;
}

export function ChannelPost({ message, canPin }: Props) {
  const me = useAuthStore((s) => s.me);
  const navigate = useNavigate();
  const setReply = useComposerStore((s) => s.setReply);
  const setEditing = useComposerStore((s) => s.setEditing);
  const queryClient = useQueryClient();

  const { data: chat } = useQuery({
    queryKey: ['chat', message.chat_id],
    queryFn: () => chatsApi.get(message.chat_id),
  });
  const linkedId = chat?.linked_chat_id ?? null;

  const isOwn = me?.id === message.sender?.id;
  const [menuPos, setMenuPos] = useState<{ x: number; y: number } | null>(null);

  function openMenu(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    setMenuPos({ x: e.clientX, y: e.clientY });
  }

  // Long-press for mobile
  let lpTimer: ReturnType<typeof setTimeout> | null = null;
  function onTouchStart(e: React.TouchEvent) {
    const t = e.touches[0];
    if (!t) return;
    const x = t.clientX;
    const y = t.clientY;
    lpTimer = setTimeout(() => {
      setMenuPos({ x, y });
    }, 400);
  }
  function onTouchEnd() {
    if (lpTimer) clearTimeout(lpTimer);
    lpTimer = null;
  }

  if (message.is_deleted) {
    return (
      <div className="my-2 flex justify-center">
        <div className="rounded-2xl bg-bg3 px-3 py-1.5 text-xs italic text-muted">
          message deleted
        </div>
      </div>
    );
  }

  const isRecent = Date.now() - new Date(message.created_at).getTime() < 3000;
  const enterAnim = isRecent ? 'animate-msg-in-other' : '';

  // collect images / videos / files
  const images = message.attachments.filter((a) => a.mime_type?.startsWith('image/'));
  const videos = message.attachments.filter((a) => a.mime_type?.startsWith('video/'));
  const files = message.attachments.filter(
    (a) => !a.mime_type?.startsWith('image/') && !a.mime_type?.startsWith('video/'),
  );

  return (
    <div
      data-message-id={message.id}
      onContextMenu={openMenu}
      onTouchStart={onTouchStart}
      onTouchEnd={onTouchEnd}
      onTouchMove={onTouchEnd}
      className={cn(
        'my-3 w-fit max-w-[min(100%,48ch)] overflow-hidden rounded-2xl bg-bg shadow-sm',
        'cursor-pointer',
        enterAnim,
      )}
    >
      {/* Media */}
      {images.length > 0 && (
        <ImageGrid images={images.map((a) => mediaUrl(a.file_url))} />
      )}
      {videos.length > 0 && videos.map((v) => (
        <video key={v.id} src={mediaUrl(v.file_url)} controls className="block w-full" />
      ))}

      {/* Body */}
      {(message.text || files.length > 0) && (
        <div className="px-4 pb-2 pt-3">
          {message.text && (
            <div className="whitespace-pre-wrap break-words text-[15px] leading-snug">
              {linkifyText(message.text)}
            </div>
          )}
          {files.map((f) => (
            <a
              key={f.id}
              href={mediaUrl(f.file_url)}
              target="_blank"
              rel="noreferrer"
              className="mt-2 flex items-center gap-2 rounded-lg bg-bg2 p-2 text-sm tg-link"
              onClick={(e) => e.stopPropagation()}
            >
              📎 {f.file_name ?? 'file'}
            </a>
          ))}
        </div>
      )}

      {/* Reactions */}
      {message.reactions && message.reactions.length > 0 && (
        <div className="flex flex-wrap gap-1.5 px-4 pb-2">
          {message.reactions.map((r) => {
            const chosen = me ? r.user_ids.includes(me.id) : false;
            return (
              <button
                key={r.emoji}
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  messagesApi.toggleReaction(message.id, r.emoji).catch(() => {});
                }}
                className={cn(
                  'flex items-center gap-1 rounded-full px-2.5 py-1 text-sm transition-colors',
                  chosen ? 'bg-accent text-white' : 'bg-bg2 text-text hover:bg-bg3',
                )}
              >
                <span className="text-base">{r.emoji}</span>
                <span className="font-medium">{r.count}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* Footer: views + edited + time */}
      <div className="flex items-center gap-2 px-4 pb-2 text-xs text-muted">
        {message.views_count > 0 && (
          <span className="flex items-center gap-1">
            <Eye className="h-3.5 w-3.5" />
            {formatViews(message.views_count)}
          </span>
        )}
        {message.is_edited && (
          <span className="flex items-center gap-1">
            <Pencil className="h-3 w-3" /> edited
          </span>
        )}
        <span className="ml-auto">{formatMessageTime(message.created_at)}</span>
      </div>

      {/* Comments + share */}
      {linkedId && (
        <div className="flex items-stretch border-t border-line">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/chat/${linkedId}`);
            }}
            className="flex flex-1 items-center justify-center gap-2 py-3 text-sm font-medium text-accent hover:bg-bg2"
          >
            <MessageSquare className="h-4 w-4" />
            Leave a Comment
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              // упрощённо — копируем ссылку на пост
              const url = `${window.location.origin}/chat/${message.chat_id}#${message.id}`;
              navigator.clipboard.writeText(url).catch(() => {});
            }}
            className="flex w-14 items-center justify-center border-l border-line text-muted hover:bg-bg2"
            aria-label="Share"
          >
            <Share2 className="h-4 w-4" />
          </button>
        </div>
      )}

      {menuPos && (
        <ContextMenu
          x={menuPos.x}
          y={menuPos.y}
          isOwn={isOwn}
          canPin={canPin}
          onClose={() => setMenuPos(null)}
          onReply={() => {
            setMenuPos(null);
            // в канале «reply» = коммент в linked-чате
            if (linkedId) navigate(`/chat/${linkedId}`);
            else setReply(message.chat_id, message);
          }}
          onCopy={async () => {
            if (message.text) await navigator.clipboard.writeText(message.text);
            setMenuPos(null);
          }}
          onReact={(emoji) => {
            messagesApi.toggleReaction(message.id, emoji).catch(() => {});
            setMenuPos(null);
          }}
          onEdit={() => {
            setMenuPos(null);
            setEditing(message.chat_id, message);
          }}
          onDelete={async () => {
            setMenuPos(null);
            const node = document.querySelector<HTMLElement>(`[data-message-id="${message.id}"]`);
            const anim = node ? playDissolve(node) : Promise.resolve();
            queryClient.setQueryData<MessageOut[]>(
              ['chat', message.chat_id, 'messages'],
              (old) => (old ? old.filter((m) => m.id !== message.id) : old),
            );
            messagesApi.remove(message.chat_id, message.id, true).catch(() => {});
            await anim;
          }}
          onPin={async () => {
            setMenuPos(null);
            try {
              await messagesApi.pin(message.chat_id, message.id);
            } catch {}
          }}
        />
      )}
    </div>
  );
}

function ImageGrid({ images }: { images: string[] }) {
  if (images.length === 1) {
    return (
      <img
        src={images[0]}
        alt=""
        loading="lazy"
        className="block max-h-[60vh] w-full bg-black object-cover"
      />
    );
  }
  if (images.length === 2) {
    return (
      <div className="grid grid-cols-2 gap-0.5 bg-black">
        {images.map((src, i) => (
          <img key={i} src={src} alt="" loading="lazy" className="aspect-square w-full object-cover" />
        ))}
      </div>
    );
  }
  return (
    <div className="grid grid-cols-3 gap-0.5 bg-black">
      {images.slice(0, 6).map((src, i) => (
        <img
          key={i}
          src={src}
          alt=""
          loading="lazy"
          className={cn('w-full object-cover', i === 0 && images.length >= 3 ? 'col-span-3 h-72' : 'aspect-square')}
        />
      ))}
    </div>
  );
}

function formatViews(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1).replace('.0', '')}K`;
  return String(n);
}

function linkifyText(text: string): React.ReactNode {
  const urlRe = /(https?:\/\/[^\s]+)|(@[a-zA-Z][a-zA-Z0-9_]{2,})/g;
  const parts: React.ReactNode[] = [];
  let lastIdx = 0;
  let m: RegExpExecArray | null;
  let key = 0;
  while ((m = urlRe.exec(text)) !== null) {
    if (m.index > lastIdx) parts.push(text.slice(lastIdx, m.index));
    const matched = m[0];
    if (matched.startsWith('http')) {
      parts.push(
        <a key={key++} href={matched} target="_blank" rel="noreferrer" className="tg-link" onClick={(e) => e.stopPropagation()}>
          {matched}
        </a>,
      );
    } else {
      parts.push(
        <span key={key++} className="tg-link cursor-pointer">
          {matched}
        </span>,
      );
    }
    lastIdx = m.index + matched.length;
  }
  if (lastIdx < text.length) parts.push(text.slice(lastIdx));
  return parts;
}
