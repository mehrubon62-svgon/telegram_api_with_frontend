import * as DropdownMenu from '@radix-ui/react-dropdown-menu';
import { Copy, Pencil, Reply, SmilePlus, Trash2, Pin } from 'lucide-react';
import type { MessageOut } from '@/api/types';
import { messagesApi } from '@/api/endpoints';
import { toast } from '@/components/ui/Toaster';

interface Props {
  message: MessageOut;
  isOwn: boolean;
  open: boolean;
  pos: { x: number; y: number } | null;
  onOpenChange: (v: boolean) => void;
  onReply: () => void;
  onEdit: () => void;
  onReact: (emoji: string) => void;
}

const QUICK = ['👍', '❤️', '🔥', '😂', '😮', '😢'];

export function MessageMenu({
  message,
  isOwn,
  open,
  pos,
  onOpenChange,
  onReply,
  onEdit,
  onReact,
}: Props) {
  if (!pos) return null;

  return (
    <DropdownMenu.Root open={open} onOpenChange={onOpenChange} modal={false}>
      <DropdownMenu.Trigger asChild>
        <span
          aria-hidden
          style={{
            position: 'fixed',
            left: pos.x,
            top: pos.y,
            width: 1,
            height: 1,
          }}
        />
      </DropdownMenu.Trigger>
      <DropdownMenu.Portal>
        <DropdownMenu.Content
          sideOffset={4}
          align="start"
          className="z-50 min-w-[200px] rounded-xl border border-line bg-bg p-1 shadow-xl animate-fade-in"
        >
          <div className="flex items-center justify-between gap-1 border-b border-line px-2 pb-2 pt-1">
            {QUICK.map((e) => (
              <button
                key={e}
                onClick={() => {
                  onReact(e);
                  onOpenChange(false);
                }}
                className="rounded-full p-1.5 text-xl transition-transform hover:scale-125 active:scale-110"
                aria-label={`React ${e}`}
              >
                {e}
              </button>
            ))}
          </div>

          <Item icon={<Reply className="h-4 w-4" />} label="Reply" onClick={onReply} />
          <Item
            icon={<Copy className="h-4 w-4" />}
            label="Copy text"
            onClick={async () => {
              if (message.text) {
                await navigator.clipboard.writeText(message.text);
                toast.success('Copied');
              }
            }}
            disabled={!message.text}
          />
          <Item
            icon={<SmilePlus className="h-4 w-4" />}
            label="Add reaction"
            onClick={() => {
              const emoji = window.prompt('Reaction emoji', '👍');
              if (emoji) onReact(emoji);
            }}
          />
          <Item
            icon={<Pin className="h-4 w-4" />}
            label="Pin"
            onClick={async () => {
              try {
                await messagesApi.pin(message.chat_id, message.id);
                toast.success('Pinned');
              } catch {
                toast.error('Failed to pin');
              }
            }}
          />
          {isOwn && (
            <Item icon={<Pencil className="h-4 w-4" />} label="Edit" onClick={onEdit} />
          )}
          {isOwn && (
            <Item
              icon={<Trash2 className="h-4 w-4" />}
              label="Delete"
              destructive
              onClick={async () => {
                if (!confirm('Delete this message for everyone?')) return;
                try {
                  await messagesApi.remove(message.chat_id, message.id, true);
                } catch {
                  toast.error('Failed to delete');
                }
              }}
            />
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  );
}

function Item({
  icon,
  label,
  onClick,
  destructive,
  disabled,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  destructive?: boolean;
  disabled?: boolean;
}) {
  return (
    <DropdownMenu.Item
      disabled={disabled}
      onSelect={(e) => {
        e.preventDefault();
        if (!disabled) onClick();
      }}
      className={
        'flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm outline-none ' +
        (destructive
          ? 'text-danger hover:bg-danger/10 focus:bg-danger/10'
          : 'text-text hover:bg-bg2 focus:bg-bg2') +
        (disabled ? ' pointer-events-none opacity-50' : '')
      }
    >
      <span className="text-muted">{icon}</span>
      {label}
    </DropdownMenu.Item>
  );
}
