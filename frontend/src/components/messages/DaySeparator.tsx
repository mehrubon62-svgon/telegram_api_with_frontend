import { formatDaySeparator } from '@/lib/format';

export function DaySeparator({ iso }: { iso: string }) {
  return (
    <div className="my-3 flex justify-center">
      <span className="rounded-full bg-black/30 px-3 py-0.5 text-xs font-medium text-white backdrop-blur dark:bg-white/10">
        {formatDaySeparator(iso)}
      </span>
    </div>
  );
}
