import { useMemo } from 'react';
import { usePresenceStore } from '@/store/presence';

export function TypingIndicator({ chatId, fallback }: { chatId: number; fallback: string }) {
  // Берём «сырой» Map; селектор стабилен пока Map не подменили
  const typingMap = usePresenceStore((s) => s.typing);
  const typingCount = useMemo(() => {
    const inner = typingMap.get(chatId);
    if (!inner) return 0;
    const cutoff = Date.now() - 6000;
    let n = 0;
    for (const ts of inner.values()) {
      if (ts > cutoff) n++;
    }
    return n;
  }, [typingMap, chatId]);

  if (typingCount === 0) return <span>{fallback}</span>;
  return (
    <span className="flex items-center gap-1 text-accent">
      <span className="flex gap-0.5">
        <span className="h-1 w-1 animate-pulse-dot rounded-full bg-accent" />
        <span className="h-1 w-1 animate-pulse-dot rounded-full bg-accent" style={{ animationDelay: '0.15s' }} />
        <span className="h-1 w-1 animate-pulse-dot rounded-full bg-accent" style={{ animationDelay: '0.3s' }} />
      </span>
      <span>typing</span>
    </span>
  );
}
