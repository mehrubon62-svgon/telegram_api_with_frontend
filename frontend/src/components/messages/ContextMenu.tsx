import { Copy, Pencil, Reply, Trash2, Pin, SmilePlus } from 'lucide-react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

interface Props {
  x: number;
  y: number;
  isOwn: boolean;
  canPin: boolean;
  onClose: () => void;
  onReply: () => void;
  onCopy: () => void;
  onReact: (emoji: string) => void;
  onEdit: () => void;
  onDelete: () => void;
  onPin: () => void;
}

const QUICK = ['👍', '❤️', '🔥', '😂', '😮', '😢'];

export function ContextMenu({ x, y, isOwn, canPin, onClose, onReply, onCopy, onReact, onEdit, onDelete, onPin }: Props) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [pos, setPos] = useState({ x, y });
  const [showCustom, setShowCustom] = useState(false);
  const [custom, setCustom] = useState('');

  // Корректируем положение, чтобы не вылезало за экран
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    let nx = x;
    let ny = y;
    const W = window.innerWidth;
    const H = window.innerHeight;
    if (nx + r.width + 8 > W) nx = W - r.width - 8;
    if (ny + r.height + 8 > H) ny = H - r.height - 8;
    if (nx < 8) nx = 8;
    if (ny < 8) ny = 8;
    setPos({ x: nx, y: ny });
  }, [x, y]);

  useEffect(() => {
    function onDoc(e: Event) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose();
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    const t = setTimeout(() => {
      document.addEventListener('mousedown', onDoc);
      document.addEventListener('touchstart', onDoc);
    }, 0);
    document.addEventListener('keydown', onKey);
    return () => {
      clearTimeout(t);
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('touchstart', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [onClose]);

  return createPortal(
    <>
      <div className="fixed inset-0 z-[150]" onClick={onClose} />
      <div
        ref={ref}
        style={{ left: pos.x, top: pos.y }}
        className="fixed z-[151] w-[230px] rounded-xl border border-line bg-bg p-1 shadow-2xl animate-fade-in"
      >
        <div className="flex items-center justify-between gap-1 border-b border-line px-2 pb-2 pt-1">
          {QUICK.map((e) => (
            <button
              key={e}
              type="button"
              onClick={() => onReact(e)}
              className="rounded-full p-1.5 text-xl transition-transform hover:scale-125"
              aria-label={`React ${e}`}
            >
              {e}
            </button>
          ))}
        </div>

        {showCustom ? (
          <form
            className="flex items-center gap-2 border-b border-line p-2"
            onSubmit={(e) => {
              e.preventDefault();
              const trimmed = custom.trim();
              if (trimmed) {
                onReact(trimmed);
                setCustom('');
                setShowCustom(false);
              }
            }}
          >
            <input
              autoFocus
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              maxLength={4}
              placeholder="Emoji"
              className="h-8 flex-1 rounded-md bg-bg2 px-2 text-sm outline-none"
            />
            <button type="submit" className="rounded-md bg-accent px-3 py-1 text-sm text-white">
              Set
            </button>
          </form>
        ) : null}

        <Item icon={<Reply className="h-4 w-4" />} label="Reply" onClick={onReply} />
        <Item icon={<Copy className="h-4 w-4" />} label="Copy text" onClick={onCopy} />
        <Item icon={<SmilePlus className="h-4 w-4" />} label="Add reaction" onClick={() => setShowCustom((v) => !v)} />
        {canPin && <Item icon={<Pin className="h-4 w-4" />} label="Pin" onClick={onPin} />}
        {isOwn && <Item icon={<Pencil className="h-4 w-4" />} label="Edit" onClick={onEdit} />}
        {isOwn && <Item icon={<Trash2 className="h-4 w-4" />} label="Delete" destructive onClick={onDelete} />}
      </div>
    </>,
    document.body,
  );
}

function Item({
  icon,
  label,
  onClick,
  destructive,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  destructive?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors ' +
        (destructive ? 'text-danger hover:bg-danger/10' : 'text-text hover:bg-bg2')
      }
    >
      <span className={destructive ? 'text-danger' : 'text-muted'}>{icon}</span>
      {label}
    </button>
  );
}
