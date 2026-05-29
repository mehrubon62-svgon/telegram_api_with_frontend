import { useCallback, useRef } from 'react';

interface Handlers {
  onPointerDown: (e: React.PointerEvent) => void;
  onPointerUp: (e: React.PointerEvent) => void;
  onPointerLeave: (e: React.PointerEvent) => void;
  onContextMenu: (e: React.MouseEvent) => void;
}

export function useLongPress(callback: (e: React.PointerEvent | React.MouseEvent) => void, ms = 400): Handlers {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const triggered = useRef(false);

  const start = useCallback(
    (e: React.PointerEvent) => {
      triggered.current = false;
      timer.current = setTimeout(() => {
        triggered.current = true;
        callback(e);
      }, ms);
    },
    [callback, ms],
  );
  const stop = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null;
  }, []);

  return {
    onPointerDown: start,
    onPointerUp: stop,
    onPointerLeave: stop,
    onContextMenu: (e) => {
      e.preventDefault();
      callback(e);
    },
  };
}
