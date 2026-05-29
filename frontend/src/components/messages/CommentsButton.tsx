import { MessageSquareText } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { chatsApi } from '@/api/endpoints';

export function CommentsButton({ chatId }: { chatId: number; messageId: number }) {
  const navigate = useNavigate();
  const { data: chat } = useQuery({
    queryKey: ['chat', chatId],
    queryFn: () => chatsApi.get(chatId),
  });
  const linked = chat?.linked_chat_id ?? null;
  if (!linked) return null;

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        navigate(`/chat/${linked}`);
      }}
      className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg bg-bg2/70 py-1.5 text-xs font-medium text-accent transition-colors hover:bg-bg2"
    >
      <MessageSquareText className="h-3.5 w-3.5" />
      <span>View comments</span>
    </button>
  );
}
