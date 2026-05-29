import { useQuery } from '@tanstack/react-query';
import { ArrowLeft, MoreVertical, Phone, Search, Video } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { callsApi, chatsApi } from '@/api/endpoints';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { useResponsive } from '@/hooks/useResponsive';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { TypingIndicator } from './TypingIndicator';
import { Spinner } from '@/components/ui/Spinner';
import { useCallsStore } from '@/store/calls';
import { toast } from '@/components/ui/Toaster';
import { useAuthStore } from '@/store/auth';
import { ChatHeaderMenu } from './ChatHeaderMenu';
import { ChatSearchBar } from './ChatSearchBar';
import { ChatProfilePanel } from './ChatProfilePanel';
import { chatAvatar, chatAvatarId, chatDisplayName } from '@/lib/chat';
import { formatLastSeen } from '@/lib/format';

interface Props {
  chatId: number;
}

export function ChatView({ chatId }: Props) {
  const navigate = useNavigate();
  const { isMobile, isDesktop } = useResponsive();
  const setActive = useCallsStore((s) => s.setActive);
  const me = useAuthStore((s) => s.me);

  const { data: chat, isLoading } = useQuery({
    queryKey: ['chat', chatId],
    queryFn: () => chatsApi.get(chatId),
    enabled: Number.isFinite(chatId),
  });

  const { data: chatList } = useQuery({
    queryKey: ['chats'],
    queryFn: () => chatsApi.list(),
  });
  const myChat = chatList?.find((c) => c.chat.id === chatId);
  const isMuted = myChat?.is_muted ?? false;

  const [searchOpen, setSearchOpen] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState<{ x: number; y: number } | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);

  if (!Number.isFinite(chatId)) {
    return (
      <div className="flex flex-1 items-center justify-center text-muted">Invalid chat</div>
    );
  }

  if (isLoading || !chat) {
    return (
      <div className="flex flex-1 items-center justify-center bg-chat">
        <Spinner />
      </div>
    );
  }

  const subtitleByType = (() => {
    if (chat.type === 'channel') return `${chat.members_count} subscribers`;
    if (chat.type === 'group' || chat.type === 'supergroup') {
      return `${chat.members_count} members`;
    }
    if (chat.type === 'saved') return 'your private notes';
    if (chat.type === 'private' && chat.peer) {
      return chat.peer.is_online ? 'online' : formatLastSeen(chat.peer.last_seen);
    }
    return 'last seen recently';
  })();

  async function startCall(video: boolean): Promise<void> {
    if (!chat || chat.type !== 'private') return;
    try {
      const members = await chatsApi.members(chat.id);
      const other = members.find((m) => m.user_id !== me?.id);
      if (!other) return;
      const call = await callsApi.start({
        callee_id: other.user_id,
        type: video ? 'video' : 'audio',
        is_video: video,
      });
      setActive(call);
    } catch {
      toast.error('Could not start call');
    }
  }

  return (
    <>
      <div className="relative flex h-dvh flex-1 flex-col bg-chat">
        <header className="flex h-14 shrink-0 items-center gap-2 border-b border-line bg-bg px-2 pt-safe">
          {isMobile && (
            <Button variant="ghost" size="icon" aria-label="Back" onClick={() => navigate('/')}>
              <ArrowLeft className="h-5 w-5" />
            </Button>
          )}
          <button
            type="button"
            onClick={() => setProfileOpen((v) => !v)}
            className="flex min-w-0 flex-1 items-center gap-3 rounded-md p-1 text-left transition-colors hover:bg-bg2"
          >
            <Avatar
              src={chatAvatar(chat)}
              name={chatDisplayName(chat)}
              id={chatAvatarId(chat)}
              size={40}
              online={chat.peer?.is_online ?? false}
            />
            <div className="min-w-0">
              <div className="truncate font-medium">
                {chatDisplayName(chat)}
              </div>
              <div className="truncate text-xs text-muted">
                <TypingIndicator chatId={chatId} fallback={subtitleByType} />
              </div>
            </div>
          </button>
          <Button variant="ghost" size="icon" aria-label="Search" onClick={() => setSearchOpen((v) => !v)}>
            <Search className="h-5 w-5" />
          </Button>
          {chat.type === 'private' && (
            <>
              <Button variant="ghost" size="icon" aria-label="Voice call" onClick={() => startCall(false)}>
                <Phone className="h-5 w-5" />
              </Button>
              <Button variant="ghost" size="icon" aria-label="Video call" onClick={() => startCall(true)}>
                <Video className="h-5 w-5" />
              </Button>
            </>
          )}
          <Button
            variant="ghost"
            size="icon"
            aria-label="More"
            onClick={(e) => {
              const r = (e.currentTarget as HTMLElement).getBoundingClientRect();
              setMenuAnchor({ x: r.right, y: r.bottom });
            }}
          >
            <MoreVertical className="h-5 w-5" />
          </Button>
        </header>

        {searchOpen && <ChatSearchBar chatId={chatId} onClose={() => setSearchOpen(false)} />}

        <MessageList chatId={chatId} chatType={chat.type} />
        {chat.type !== 'channel' && <MessageInput chatId={chatId} chatType={chat.type} />}
      </div>

      {isDesktop && (
        <ChatProfilePanel
          chat={chat}
          open={profileOpen}
          onClose={() => setProfileOpen(false)}
        />
      )}

      {menuAnchor && (
        <ChatHeaderMenu
          chat={chat}
          isMuted={isMuted}
          anchor={menuAnchor}
          onClose={() => setMenuAnchor(null)}
          onShowInfo={() => setProfileOpen(true)}
        />
      )}
    </>
  );
}
