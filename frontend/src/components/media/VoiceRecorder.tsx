import { Mic, X, Send } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { mediaApi, messagesApi } from '@/api/endpoints';
import { toast } from '@/components/ui/Toaster';
import { formatDuration } from '@/lib/format';

interface Props {
  chatId: number;
  onDone?: () => void;
}

/** Кнопка записи голосового. Click-to-start / click-to-send. */
export function VoiceRecorder({ chatId, onDone }: Props) {
  const [recording, setRecording] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef<number>(0);
  const tickerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => {
    recorderRef.current?.stop();
    if (tickerRef.current) clearInterval(tickerRef.current);
  }, []);

  async function startRecord(): Promise<void> {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      recorderRef.current = mr;
      chunksRef.current = [];
      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
      };
      mr.start();
      startedAtRef.current = Date.now();
      setSeconds(0);
      setRecording(true);
      tickerRef.current = setInterval(() => {
        setSeconds(Math.floor((Date.now() - startedAtRef.current) / 1000));
      }, 250);
    } catch {
      toast.error('Microphone access denied');
    }
  }

  async function cancelRecord(): Promise<void> {
    if (tickerRef.current) clearInterval(tickerRef.current);
    recorderRef.current?.stop();
    setRecording(false);
    setSeconds(0);
    chunksRef.current = [];
  }

  async function sendRecord(): Promise<void> {
    if (tickerRef.current) clearInterval(tickerRef.current);
    const mr = recorderRef.current;
    if (!mr) return;

    await new Promise<void>((resolve) => {
      mr.addEventListener('stop', () => resolve(), { once: true });
      mr.stop();
    });

    setRecording(false);
    const duration = Math.max(1, Math.round((Date.now() - startedAtRef.current) / 1000));
    const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
    const file = new File([blob], `voice-${Date.now()}.webm`, { type: 'audio/webm' });

    try {
      const up = await mediaApi.upload(file, 'voice', { duration });
      await messagesApi.send(chatId, {
        type: 'voice',
        attachments: [
          {
            file_url: up.file_url,
            mime_type: up.mime_type ?? 'audio/webm',
            duration,
            size_bytes: up.size_bytes,
            file_name: up.file_name,
          },
        ] as unknown[],
      });
      onDone?.();
    } catch {
      toast.error('Failed to send voice');
    }
  }

  if (!recording) {
    return (
      <button
        type="button"
        aria-label="Record voice"
        onClick={startRecord}
        className="flex h-11 w-11 items-center justify-center rounded-lg text-text hover:bg-bg2"
      >
        <Mic className="h-5 w-5" />
      </button>
    );
  }

  return (
    <div className="flex h-11 items-center gap-2 rounded-xl bg-bg2 px-3">
      <span className="h-2 w-2 animate-pulse rounded-full bg-danger" />
      <span className="text-sm tabular-nums">{formatDuration(seconds)}</span>
      <button
        type="button"
        onClick={cancelRecord}
        aria-label="Cancel"
        className="flex h-9 w-9 items-center justify-center rounded-lg text-danger hover:bg-danger/10"
      >
        <X className="h-5 w-5" />
      </button>
      <button
        type="button"
        onClick={sendRecord}
        aria-label="Send voice"
        className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent text-white"
      >
        <Send className="h-5 w-5" />
      </button>
    </div>
  );
}
