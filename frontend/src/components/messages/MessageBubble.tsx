import { CheckCheck, Paperclip } from 'lucide-react';
import { useState } from 'react';
import type { ChatType, MessageOut } from '@/api/types';
import { cn } from '@/lib/cn';
import { formatMessageTime } from '@/lib/format';
import { useAuthStore } from '@/store/auth';
import { Avatar } from '@/components/ui/Avatar';
import { mediaUrl } from '@/lib/url';
import { messagesApi } from '@/api/endpoints';
import { useComposerStore } from '@/store/composer';
import { ContextMenu } from './ContextMenu';
import { CommentsButton } from './CommentsButton';
import { VoicePlayer } from '@/components/media/VoicePlayer';
import { playDissolve } from '@/lib/dissolve';
import { useQueryClient } from '@tanstack/react-query';
import { nameColor } from '@/lib/colors';

interface Props {
  message: MessageOut;
  grouped: boolean;
  chatType: ChatType;
  canPin: boolean;
}

export function MessageBubble({ message, grouped, chatType, canPin }: Props) {
  const me = useAuthStore((s) => s.me);
  const isOwn = me?.id === message.sender?.id;
  const setReply = useComposerStore((s) => s.setReply);
  const setEditing = useComposerStore((s) => s.setEditing);
  const queryClient = useQueryClient();

  const [menuPos, setMenuPos] = useState<{ x: number; y: number } | null>(null);

  function openMenu(e: React.MouseEvent | React.TouchEvent, clientX?: number, clientY?: number) {
    e.preventDefault();
    e.stopPropagation();
    const x = clientX ?? ('clientX' in e ? (e as React.MouseEvent).clientX : 0);
    const y = clientY ?? ('clientY' in e ? (e as React.MouseEvent).clientY : 0);
    setMenuPos({ x, y });
  }

  // Long-press на мобиле
  let lpTimer: ReturnType<typeof setTimeout> | null = null;
  function onTouchStart(e: React.TouchEvent) {
    const t = e.touches[0];
    if (!t) return;
    const x = t.clientX;
    const y = t.clientY;
    lpTimer = setTimeout(() => {
      openMenu(e, x, y);
    }, 400);
  }
  function onTouchEnd() {
    if (lpTimer) clearTimeout(lpTimer);
    lpTimer = null;
  }

  if (message.is_deleted) {
    return (
      <div className={cn('flex w-full', isOwn ? 'justify-end' : 'justify-start')}>
        <div className="rounded-2xl bg-bg3 px-3 py-1.5 text-xs italic text-muted">
          message deleted
        </div>
      </div>
    );
  }

  const showName = !grouped && !isOwn && message.sender;
  const att = message.attachments[0];
  const isVoice = message.type === 'voice' || (att?.mime_type?.startsWith('audio/') ?? false);
  const isVideoNote = message.type === 'video_note';

  // Анимация только для свежих сообщений (последние 3 сек), чтобы при
  // первой загрузке истории всё не «прыгало»
  const isRecent = Date.now() - new Date(message.created_at).getTime() < 3000;
  const enterAnim = isRecent ? (isOwn ? 'animate-msg-in-own' : 'animate-msg-in-other') : '';

  return (
    <div
      className={cn(
        'group flex w-full items-end gap-2',
        isOwn ? 'justify-end' : 'justify-start',
        grouped ? 'mt-0.5' : 'mt-2',
        enterAnim,
      )}
    >
      {!isOwn && (
        <div className="w-8 shrink-0">
          {!grouped && (
            <Avatar
              src={message.sender?.avatar_url}
              name={message.sender?.username ?? '?'}
              id={message.sender?.id ?? message.id}
              size={32}
            />
          )}
        </div>
      )}

      {isVideoNote && att ? (
        <div data-message-id={message.id} onContextMenu={openMenu} onTouchStart={onTouchStart} onTouchEnd={onTouchEnd} onTouchMove={onTouchEnd}>
          <video
            src={mediaUrl(att.file_url)}
            controls
            className="h-56 w-56 rounded-full object-cover"
          />
        </div>
      ) : (
        <div
          data-message-id={message.id}
          onContextMenu={openMenu}
          onTouchStart={onTouchStart}
          onTouchEnd={onTouchEnd}
          onTouchMove={onTouchEnd}
          className={cn(
            // ширина по содержимому, но не шире ~48 символов; затем перенос
            'relative w-fit max-w-[min(85%,48ch)] rounded-2xl px-3 py-2 text-[15px] leading-[1.35] shadow-sm sm:max-w-[min(65%,48ch)]',
            isOwn ? 'bg-own text-ownText' : 'bg-bg text-text',
            isOwn
              ? grouped
                ? 'rounded-br-2xl'
                : 'rounded-br-md'
              : grouped
                ? 'rounded-bl-2xl'
                : 'rounded-bl-md',
            'min-w-0 whitespace-pre-wrap break-words',
            '[overflow-wrap:anywhere]',
            'cursor-pointer select-text',
          )}
        >
          {showName && message.sender && (
            <div
              className="mb-0.5 text-sm font-semibold"
              style={{ color: nameColor(message.sender.name_color ?? message.sender.id) }}
            >
              {message.sender.username ?? `User ${message.sender.id}`}
            </div>
          )}

          {message.forward && (
            <div className="mb-1 border-l-2 border-accent pl-2 text-xs italic text-muted">
              Forwarded from {message.forward.sender_name ?? 'unknown'}
            </div>
          )}

          {message.reply_to_id && message.reply_quote_text && (
            <div className="mb-1 max-w-full rounded border-l-2 border-accent bg-bg2 px-2 py-1 text-xs">
              <div className="text-accent">in reply</div>
              <div className="truncate">{message.reply_quote_text}</div>
            </div>
          )}

          {message.attachments.length > 0 && (
            <div className="mb-1 flex flex-col gap-1">
              {message.attachments.map((a) => {
                const isImage = a.mime_type?.startsWith('image/');
                const isVideo = a.mime_type?.startsWith('video/');
                if (isVoice) {
                  return (
                    <VoicePlayer
                      key={a.id}
                      url={mediaUrl(a.file_url)}
                      duration={a.duration ?? 0}
                      waveform={a.waveform}
                    />
                  );
                }
                if (isImage) {
                  return (
                    <img
                      key={a.id}
                      src={mediaUrl(a.file_url)}
                      alt=""
                      className="max-h-[60vh] max-w-full rounded-xl object-contain sm:max-h-[480px]"
                      loading="lazy"
                    />
                  );
                }
                if (isVideo) {
                  return (
                    <video
                      key={a.id}
                      src={mediaUrl(a.file_url)}
                      controls
                      className="max-h-[60vh] max-w-full rounded-xl sm:max-h-[480px]"
                    />
                  );
                }
                return (
                  <a
                    key={a.id}
                    href={mediaUrl(a.file_url)}
                    target="_blank"
                    rel="noreferrer"
                    className="flex items-center gap-2 rounded-lg bg-bg2 p-2 text-sm tg-link"
                  >
                    <Paperclip className="h-4 w-4 shrink-0" />
                    <span className="truncate">{a.file_name ?? 'file'}</span>
                  </a>
                );
              })}
            </div>
          )}

          {message.text && <div className="whitespace-pre-wrap">{message.text}</div>}

          {/* Кнопка комментариев под постом канала */}
          {chatType === 'channel' && (
            <CommentsButton chatId={message.chat_id} messageId={message.id} />
          )}

          {/* Реакции под сообщением */}
          {message.reactions && message.reactions.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {message.reactions.map((r) => {
                const chosen = me ? r.user_ids.includes(me.id) : false;
                return (
                  <button
                    key={r.emoji}
                    onClick={(e) => {
                      e.stopPropagation();
                      messagesApi.toggleReaction(message.id, r.emoji).catch(() => {});
                    }}
                    className={cn(
                      'flex items-center gap-1 rounded-full px-2 py-0.5 text-xs transition-colors',
                      chosen
                        ? 'bg-accent text-white'
                        : 'bg-bg2 text-text hover:bg-bg3',
                    )}
                  >
                    <span>{r.emoji}</span>
                    <span className="font-medium">{r.count}</span>
                  </button>
                );
              })}
            </div>
          )}

          <div className="mt-0.5 flex items-center justify-end gap-1 text-[11px] opacity-70">
            {message.is_edited && <span className="italic">edited</span>}
            <span>{formatMessageTime(message.created_at)}</span>
            {isOwn && (
              <span aria-label="sent">
                <CheckCheck className="h-3.5 w-3.5" />
              </span>
            )}
          </div>
        </div>
      )}

      {menuPos && (
        <ContextMenu
          x={menuPos.x}
          y={menuPos.y}
          onClose={() => setMenuPos(null)}
          isOwn={isOwn}
          onReply={() => {
            setMenuPos(null);
            setReply(message.chat_id, message);
          }}
          onCopy={async () => {
            if (message.text) {
              await navigator.clipboard.writeText(message.text);
            }
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
            const node = document.querySelector<HTMLElement>(
              `[data-message-id="${message.id}"]`,
            );
            // Запускаем эффект параллельно с удалением — чтобы ничего
            // не моргало, СРАЗУ удаляем сообщение из кэша react-query.
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
            } catch {
              // ignore
            }
          }}
          canPin={canPin}
        />
      )}
    </div>
  );
}
