import { useParams } from 'react-router-dom';
import { useResponsive } from '@/hooks/useResponsive';
import { Sidebar } from '@/components/layout/Sidebar';
import { ChatView } from '@/components/messages/ChatView';
import { Resizer } from '@/components/layout/Resizer';
import { useUiStore } from '@/store/ui';

export function ChatRoute() {
  const { chatId: idParam } = useParams();
  const chatId = Number(idParam);
  const { isMobile } = useResponsive();
  const sidebarWidth = useUiStore((s) => s.sidebarWidth);
  const setSidebarWidth = useUiStore((s) => s.setSidebarWidth);

  return (
    <div className="flex h-dvh w-full overflow-hidden bg-bg">
      {!isMobile && <Sidebar width={sidebarWidth} />}
      {!isMobile && <Resizer onResize={(dx) => setSidebarWidth(sidebarWidth + dx)} />}
      <ChatView chatId={chatId} />
    </div>
  );
}
