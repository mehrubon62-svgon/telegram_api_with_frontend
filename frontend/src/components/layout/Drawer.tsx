import { useEffect } from 'react';
import { cn } from '@/lib/cn';

interface Props {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
  side?: 'left' | 'right';
}

export function Drawer({ open, onClose, children, side = 'left' }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  return (
    <div
      className={cn(
        'fixed inset-0 z-40 transition-opacity',
        open ? 'pointer-events-auto opacity-100' : 'pointer-events-none opacity-0',
      )}
    >
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        className={cn(
          'thin-scrollbar absolute top-0 h-dvh w-[85vw] max-w-[320px] overflow-y-auto bg-bg shadow-2xl transition-transform duration-200 ease-out',
          side === 'left' ? 'left-0' : 'right-0',
          side === 'left'
            ? open
              ? 'translate-x-0'
              : '-translate-x-full'
            : open
              ? 'translate-x-0'
              : 'translate-x-full',
        )}
      >
        {children}
      </div>
    </div>
  );
}
