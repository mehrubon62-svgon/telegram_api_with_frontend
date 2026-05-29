import { useEffect, useRef } from 'react';

interface Props {
  onResize: (deltaPx: number) => void;
}

/** Вертикальная полоска-разделитель: захватываем pointer и стримим dx. */
export function Resizer({ onResize }: Props) {
  const lastX = useRef<number | null>(null);

  useEffect(() => {
    function move(e: PointerEvent): void {
      if (lastX.current === null) return;
      const dx = e.clientX - lastX.current;
      lastX.current = e.clientX;
      onResize(dx);
    }
    function up(): void {
      lastX.current = null;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    }
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', up);
    return () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      window.removeEventListener('pointercancel', up);
    };
  }, [onResize]);

  function down(e: React.PointerEvent): void {
    lastX.current = e.clientX;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.currentTarget.setPointerCapture(e.pointerId);
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      onPointerDown={down}
      className="group relative w-1 shrink-0 cursor-col-resize bg-line transition-colors hover:bg-accent/40"
    >
      <div className="absolute inset-y-0 -left-2 -right-2" />
    </div>
  );
}
