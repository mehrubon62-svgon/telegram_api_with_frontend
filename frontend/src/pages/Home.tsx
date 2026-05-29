import { useResponsive } from '@/hooks/useResponsive';
import { Sidebar } from '@/components/layout/Sidebar';
import { ChatPlaceholder } from '@/components/chats/ChatPlaceholder';
import { Resizer } from '@/components/layout/Resizer';
import { useUiStore } from '@/store/ui';

export function Home() {
  const { isMobile } = useResponsive();
  const sidebarWidth = useUiStore((s) => s.sidebarWidth);
  const setSidebarWidth = useUiStore((s) => s.setSidebarWidth);

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-bg">
      <Sidebar width={sidebarWidth} />
      {!isMobile && <Resizer onResize={(dx) => setSidebarWidth(sidebarWidth + dx)} />}
      {!isMobile && <ChatPlaceholder />}
    </div>
  );
}
