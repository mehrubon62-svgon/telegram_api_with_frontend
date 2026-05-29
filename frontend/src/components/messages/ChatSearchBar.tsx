import { ChevronDown, ChevronUp, Search, X } from 'lucide-react';
import { useEffect, useState } from 'react';
import { messagesApi } from '@/api/endpoints';
import type { MessageOut } from '@/api/types';
import { Spinner } from '@/components/ui/Spinner';

interface Props {
  chatId: number;
  onClose: () => void;
}

export function ChatSearchBar({ chatId, onClose }: Props) {
  const [q, setQ] = useState('');
  const [results, setResults] = useState<MessageOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [idx, setIdx] = useState(0);

  useEffect(() => {
    if (q.trim().length < 1) {
      setResults([]);
      return;
    }
    setLoading(true);
    let cancelled = false;
    const t = setTimeout(async () => {
      try {
        const r = await messagesApi.searchInChat(chatId, q.trim());
        if (!cancelled) {
          setResults(r);
          setIdx(0);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [q, chatId]);

  // Прокрутка к найденному сообщению
  useEffect(() => {
    if (results.length === 0) return;
    const target = results[idx];
    if (!target) return;
    const node = document.querySelector(`[data-message-id="${target.id}"]`);
    if (node) {
      node.scrollIntoView({ behavior: 'smooth', block: 'center' });
      (node as HTMLElement).animate(
        [{ background: 'rgb(var(--accent) / 0.3)' }, { background: 'transparent' }],
        { duration: 1200 },
      );
    }
  }, [results, idx]);

  return (
    <div className="flex h-12 shrink-0 items-center gap-2 border-b border-line bg-bg px-2 animate-fade-in">
      <Search className="h-4 w-4 shrink-0 text-muted" />
      <input
        autoFocus
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Search in chat"
        className="h-9 flex-1 bg-transparent text-sm outline-none"
      />
      {loading && <Spinner className="h-4 w-4" />}
      {results.length > 0 && (
        <>
          <span className="text-xs text-muted">
            {idx + 1} / {results.length}
          </span>
          <button
            type="button"
            disabled={idx <= 0}
            onClick={() => setIdx((i) => Math.max(0, i - 1))}
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-bg2 disabled:opacity-30"
          >
            <ChevronUp className="h-4 w-4" />
          </button>
          <button
            type="button"
            disabled={idx >= results.length - 1}
            onClick={() => setIdx((i) => Math.min(results.length - 1, i + 1))}
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-bg2 disabled:opacity-30"
          >
            <ChevronDown className="h-4 w-4" />
          </button>
        </>
      )}
      <button
        type="button"
        onClick={onClose}
        className="flex h-8 w-8 items-center justify-center rounded-md text-muted hover:bg-bg2"
        aria-label="Close search"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
