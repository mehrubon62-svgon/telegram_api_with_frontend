import { useEffect, useState } from 'react';

type Breakpoint = 'mobile' | 'tablet' | 'desktop' | 'ultra';

export function useResponsive(): { bp: Breakpoint; isMobile: boolean; isTablet: boolean; isDesktop: boolean } {
  const [bp, setBp] = useState<Breakpoint>(() => current());
  useEffect(() => {
    const onResize = (): void => setBp(current());
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return {
    bp,
    isMobile: bp === 'mobile',
    isTablet: bp === 'tablet',
    isDesktop: bp === 'desktop' || bp === 'ultra',
  };
}

function current(): Breakpoint {
  const w = typeof window !== 'undefined' ? window.innerWidth : 1280;
  if (w < 768) return 'mobile';
  if (w < 1024) return 'tablet';
  if (w < 1600) return 'desktop';
  return 'ultra';
}
