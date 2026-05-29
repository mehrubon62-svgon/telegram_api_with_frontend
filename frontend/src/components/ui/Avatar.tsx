import { cn } from '@/lib/cn';
import { colorFromId, getInitials } from '@/lib/format';
import { mediaUrl } from '@/lib/url';

interface Props {
  src?: string | null;
  name: string | null | undefined;
  id: number | string;
  size?: number;
  online?: boolean;
  className?: string;
}

export function Avatar({ src, name, id, size = 48, online, className }: Props) {
  const url = src ? mediaUrl(src) : '';
  return (
    <div
      className={cn('relative shrink-0 select-none', className)}
      style={{ width: size, height: size }}
    >
      {url ? (
        <img
          src={url}
          alt={name ?? ''}
          className="h-full w-full rounded-full object-cover"
          loading="lazy"
        />
      ) : (
        <div
          className="flex h-full w-full items-center justify-center rounded-full text-white"
          style={{ backgroundColor: colorFromId(id), fontSize: size * 0.4 }}
        >
          {getInitials(name)}
        </div>
      )}
      {online && (
        <span className="absolute bottom-0 right-0 h-3 w-3 rounded-full border-2 border-bg bg-green-500" />
      )}
    </div>
  );
}
