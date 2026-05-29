import { Pause, Play } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { formatDuration } from '@/lib/format';

interface Props {
  url: string;
  duration: number;
  waveform?: number[] | null;
}

export function VoicePlayer({ url, duration, waveform }: Props) {
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0); // 0..1
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Если нет waveform — нарисуем фейковую (детерминированную) на основе длины
  const bars = waveform && waveform.length > 0
    ? waveform
    : Array.from({ length: 40 }, (_, i) => Math.abs(Math.sin(i * 1.7)) * 80 + 20);

  useEffect(() => {
    if (!audioRef.current) {
      audioRef.current = new Audio(url);
      audioRef.current.preload = 'metadata';
    }
    const a = audioRef.current;
    function onTime(): void {
      const d = a.duration || duration || 1;
      setProgress(a.currentTime / d);
    }
    function onEnd(): void {
      setPlaying(false);
      setProgress(0);
    }
    a.addEventListener('timeupdate', onTime);
    a.addEventListener('ended', onEnd);
    return () => {
      a.pause();
      a.removeEventListener('timeupdate', onTime);
      a.removeEventListener('ended', onEnd);
    };
  }, [url, duration]);

  function toggle(): void {
    const a = audioRef.current;
    if (!a) return;
    if (playing) {
      a.pause();
      setPlaying(false);
    } else {
      void a.play();
      setPlaying(true);
    }
  }

  return (
    <div className="flex min-w-[220px] items-center gap-2">
      <button
        onClick={toggle}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent text-white"
        aria-label={playing ? 'Pause' : 'Play'}
      >
        {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4 translate-x-0.5" />}
      </button>
      <div className="flex-1">
        <div className="flex h-8 items-center gap-[2px]">
          {bars.map((v, i) => {
            const filled = i / bars.length < progress;
            const h = Math.max(4, Math.min(28, v / 4));
            return (
              <span
                key={i}
                className={
                  'w-[2px] rounded-full transition-colors ' +
                  (filled ? 'bg-accent' : 'bg-muted/50')
                }
                style={{ height: h }}
              />
            );
          })}
        </div>
        <div className="mt-0.5 text-[10px] text-muted">{formatDuration(duration || 0)}</div>
      </div>
    </div>
  );
}
