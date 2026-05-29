import { useEffect, useState } from 'react';

/** Высота visual viewport — нужна, чтобы поле ввода не уезжало под клавиатурой на iOS. */
export function useViewportHeight(): number {
  const [h, setH] = useState<number>(() =>
    typeof window === 'undefined' ? 0 : window.visualViewport?.height ?? window.innerHeight,
  );
  useEffect(() => {
    const vv = window.visualViewport;
    if (!vv) return;
    const onResize = (): void => setH(vv.height);
    vv.addEventListener('resize', onResize);
    vv.addEventListener('scroll', onResize);
    return () => {
      vv.removeEventListener('resize', onResize);
      vv.removeEventListener('scroll', onResize);
    };
  }, []);
  return h;
}
