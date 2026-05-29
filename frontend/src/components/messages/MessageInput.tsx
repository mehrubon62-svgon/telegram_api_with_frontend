import { Paperclip, Send, Smile, X, Reply as ReplyIcon, Image, Film, FileText, Video } from 'lucide-react';
import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { useEffect, useRef, useState } from 'react';
import { mediaApi, messagesApi } from '@/api/endpoints';
import { wsClient } from '@/ws/client';
import { Button } from '@/components/ui/Button';
import { toast } from '@/components/ui/Toaster';
import { throttle } from '@/lib/throttle';
import type { ChatType } from '@/api/types';
import { useComposerStore } from '@/store/composer';
import { VoiceRecorder } from '@/components/media/VoiceRecorder';

interface Props {
  chatId: number;
  chatType: ChatType;
}

export function MessageInput({ chatId }: Props) {
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const photoRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLInputElement>(null);
  const stopTypingTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);

  const reply = useComposerStore((s) => s.reply[chatId]);
  const editing = useComposerStore((s) => s.editing[chatId]);
  const setReply = useComposerStore((s) => s.setReply);
  const setEditing = useComposerStore((s) => s.setEditing);
  const clear = useComposerStore((s) => s.clear);

  // Подгрузка draft при открытии чата
  useEffect(() => {
    let cancelled = false;
    setText('');
    void messagesApi.getDraft(chatId).then((d) => {
      if (!cancelled && d?.text) setText(d.text);
    });
    return () => {
      cancelled = true;
    };
  }, [chatId]);

  // При входе в режим edit подменяем текст
  useEffect(() => {
    if (editing) {
      setText(editing.text ?? '');
      taRef.current?.focus();
    }
  }, [editing]);

  // При reply фокусируем поле
  useEffect(() => {
    if (reply) taRef.current?.focus();
  }, [reply]);

  // Сохраняем draft (только если не edit)
  useEffect(() => {
    if (editing) return;
    const t = setTimeout(() => {
      void messagesApi.saveDraft(chatId, { text: text || null });
    }, 1500);
    return () => clearTimeout(t);
  }, [text, chatId, editing]);

  // Авто-рост textarea
  useEffect(() => {
    const el = taRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
  }, [text]);

  const sendTypingThrottled = useRef(
    throttle(() => wsClient.send({ type: 'typing', chat_id: chatId }), 4500),
  ).current;

  function onChange(e: React.ChangeEvent<HTMLTextAreaElement>): void {
    setText(e.target.value);
    if (e.target.value && !editing) {
      sendTypingThrottled();
      if (stopTypingTimer.current) clearTimeout(stopTypingTimer.current);
      stopTypingTimer.current = setTimeout(() => {
        wsClient.send({ type: 'stop_typing', chat_id: chatId });
      }, 3000);
    } else {
      wsClient.send({ type: 'stop_typing', chat_id: chatId });
    }
  }

  async function send(): Promise<void> {
    const t = text.trim();
    if (!t || sending) return;
    setSending(true);
    const stash = t;
    setText('');
    wsClient.send({ type: 'stop_typing', chat_id: chatId });
    try {
      if (editing) {
        await messagesApi.edit(chatId, editing.id, { text: t });
        setEditing(chatId, null);
      } else {
        const reply_to_id = reply?.id;
        await messagesApi.send(chatId, {
          text: t,
          ...(reply_to_id ? { reply_to_id } : {}),
        });
        setReply(chatId, null);
        void messagesApi.deleteDraft(chatId).catch(() => {});
      }
    } catch {
      toast.error('Send failed');
      setText(stash);
    } finally {
      setSending(false);
    }
  }

  function onKey(e: React.KeyboardEvent<HTMLTextAreaElement>): void {
    if (e.key === 'Escape') {
      if (editing || reply) {
        clear(chatId);
        e.preventDefault();
      }
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  async function handleFile(file: File, kind: 'photo' | 'video' | 'file'): Promise<void> {
    try {
      const up = await mediaApi.upload(file, kind);
      await messagesApi.send(chatId, {
        text: text.trim() || undefined,
        ...(reply ? { reply_to_id: reply.id } : {}),
        attachments: [
          {
            file_url: up.file_url,
            mime_type: up.mime_type,
            size_bytes: up.size_bytes,
            width: up.width,
            height: up.height,
            duration: up.duration,
            file_name: up.file_name,
          },
        ] as unknown[],
      });
      setText('');
      setReply(chatId, null);
    } catch {
      toast.error('Upload failed');
    }
  }

  function pickInput(ref: React.RefObject<HTMLInputElement>, accept: string, kind: 'photo' | 'video' | 'file'): void {
    const el = ref.current;
    if (!el) return;
    el.accept = accept;
    el.dataset.kind = kind;
    el.click();
  }

  async function onInputChange(e: React.ChangeEvent<HTMLInputElement>): Promise<void> {
    const f = e.target.files?.[0];
    const kind = (e.target.dataset.kind ?? 'file') as 'photo' | 'video' | 'file';
    e.target.value = '';
    if (!f) return;
    await handleFile(f, kind);
  }

  return (
    <div className="shrink-0 border-t border-line bg-bg pb-safe">
      {(reply || editing) && (
        <div className="flex items-center gap-2 border-b border-line bg-bg2 px-3 py-2">
          <ReplyIcon className="h-4 w-4 shrink-0 text-accent" />
          <div className="min-w-0 flex-1">
            <div className="text-xs font-medium text-accent">
              {editing ? 'Editing message' : `Reply to ${reply?.sender?.username ? `@${reply.sender.username}` : 'message'}`}
            </div>
            <div className="truncate text-xs text-muted">
              {(editing?.text ?? reply?.text) || '...'}
            </div>
          </div>
          <button
            onClick={() => clear(chatId)}
            className="flex h-7 w-7 items-center justify-center rounded-full text-muted hover:bg-bg3"
            aria-label="Cancel"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      <div className="flex items-end gap-2 px-2 pt-2 sm:px-4">
        <DropdownMenu.Root>
          <DropdownMenu.Trigger asChild>
            <button
              type="button"
              aria-label="Attach"
              className="flex h-11 w-11 items-center justify-center rounded-lg text-text hover:bg-bg2"
            >
              <Paperclip className="h-5 w-5" />
            </button>
          </DropdownMenu.Trigger>
          <DropdownMenu.Portal>
            <DropdownMenu.Content
              sideOffset={8}
              align="start"
              className="z-50 min-w-[200px] rounded-xl border border-line bg-bg p-1 shadow-xl animate-fade-in"
            >
              <AttachItem icon={<Image className="h-4 w-4" />} label="Photo" onClick={() => pickInput(photoRef, 'image/*', 'photo')} />
              <AttachItem icon={<Film className="h-4 w-4" />} label="Video" onClick={() => pickInput(videoRef, 'video/*', 'video')} />
              <AttachItem icon={<FileText className="h-4 w-4" />} label="File" onClick={() => pickInput(fileRef, '*/*', 'file')} />
              <AttachItem icon={<Video className="h-4 w-4" />} label="Video message" onClick={() => recordVideoNote(chatId, reply?.id, () => setReply(chatId, null))} />
            </DropdownMenu.Content>
          </DropdownMenu.Portal>
        </DropdownMenu.Root>

        <input ref={fileRef} type="file" hidden onChange={onInputChange} data-kind="file" />
        <input ref={photoRef} type="file" hidden onChange={onInputChange} data-kind="photo" />
        <input ref={videoRef} type="file" hidden onChange={onInputChange} data-kind="video" />

        <textarea
          ref={taRef}
          value={text}
          onChange={onChange}
          onKeyDown={onKey}
          placeholder={editing ? 'Edit message…' : 'Message'}
          rows={1}
          className="thin-scrollbar max-h-40 min-h-[44px] flex-1 resize-none rounded-2xl bg-bg2 px-4 py-2.5 text-sm outline-none focus:bg-bg3"
        />

        <button
          type="button"
          aria-label="Emoji"
          className="flex h-11 w-11 items-center justify-center rounded-lg text-text hover:bg-bg2"
          onClick={() => {
            // быстрый picker: вставляет один из шести
            const e = window.prompt('Insert emoji', '😀');
            if (e) setText((t) => t + e);
          }}
        >
          <Smile className="h-5 w-5" />
        </button>

        {!text.trim() && !editing ? (
          <VoiceRecorder chatId={chatId} onDone={() => {}} />
        ) : (
          <Button
            variant="primary"
            size="icon"
            onClick={send}
            disabled={!text.trim() || sending}
            aria-label="Send"
          >
            <Send className="h-5 w-5" />
          </Button>
        )}
      </div>
    </div>
  );
}

function AttachItem({ icon, label, onClick }: { icon: React.ReactNode; label: string; onClick: () => void }) {
  return (
    <DropdownMenu.Item
      onSelect={(e) => {
        e.preventDefault();
        onClick();
      }}
      className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm outline-none hover:bg-bg2 focus:bg-bg2"
    >
      <span className="text-muted">{icon}</span>
      {label}
    </DropdownMenu.Item>
  );
}

// === Кружок (video note) — простая запись через MediaRecorder ===
async function recordVideoNote(chatId: number, replyToId: number | undefined, onDone: () => void): Promise<void> {
  let stream: MediaStream | null = null;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
  } catch {
    toast.error('Camera access denied');
    return;
  }
  const mr = new MediaRecorder(stream, { mimeType: 'video/webm' });
  const chunks: Blob[] = [];
  mr.ondataavailable = (e) => e.data.size > 0 && chunks.push(e.data);

  // мини-окно с превью + кнопкой "Stop"
  const overlay = document.createElement('div');
  overlay.className =
    'fixed inset-0 z-[100] flex items-center justify-center bg-black/80';
  const video = document.createElement('video');
  video.autoplay = true;
  video.muted = true;
  video.srcObject = stream;
  video.className = 'h-72 w-72 rounded-full object-cover';
  const stopBtn = document.createElement('button');
  stopBtn.textContent = 'Stop & Send';
  stopBtn.className =
    'mt-6 rounded-full bg-accent px-6 py-3 text-white';
  const wrap = document.createElement('div');
  wrap.className = 'flex flex-col items-center';
  wrap.appendChild(video);
  wrap.appendChild(stopBtn);
  overlay.appendChild(wrap);
  document.body.appendChild(overlay);

  function cleanup(): void {
    overlay.remove();
    stream?.getTracks().forEach((t) => t.stop());
  }

  await new Promise<void>((resolve) => {
    stopBtn.onclick = () => resolve();
    mr.start();
    setTimeout(() => resolve(), 60000); // hard cap 60s
  });

  await new Promise<void>((resolve) => {
    mr.addEventListener('stop', () => resolve(), { once: true });
    mr.stop();
  });

  cleanup();

  const blob = new Blob(chunks, { type: 'video/webm' });
  const file = new File([blob], `circle-${Date.now()}.webm`, { type: 'video/webm' });
  try {
    const up = await mediaApi.upload(file, 'video');
    await messagesApi.send(chatId, {
      type: 'video_note',
      ...(replyToId ? { reply_to_id: replyToId } : {}),
      attachments: [
        {
          file_url: up.file_url,
          mime_type: up.mime_type ?? 'video/webm',
          size_bytes: up.size_bytes,
          duration: up.duration,
          file_name: up.file_name,
        },
      ] as unknown[],
    });
    onDone();
  } catch {
    toast.error('Failed to send video');
  }
}
