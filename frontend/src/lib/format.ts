import { format, isToday, isYesterday, isThisWeek, isThisYear, formatDistanceToNowStrict } from 'date-fns';

export function formatChatListTime(iso: string | Date): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso;
  if (isToday(d)) return format(d, 'HH:mm');
  if (isYesterday(d)) return 'Yesterday';
  if (isThisWeek(d)) return format(d, 'EEE');
  if (isThisYear(d)) return format(d, 'd MMM');
  return format(d, 'dd.MM.yy');
}

export function formatMessageTime(iso: string | Date): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso;
  return format(d, 'HH:mm');
}

export function formatDaySeparator(iso: string | Date): string {
  const d = typeof iso === 'string' ? new Date(iso) : iso;
  if (isToday(d)) return 'Today';
  if (isYesterday(d)) return 'Yesterday';
  if (isThisYear(d)) return format(d, 'd MMMM');
  return format(d, 'd MMMM yyyy');
}

export function formatLastSeen(iso: string | Date | null | undefined): string {
  if (!iso) return 'last seen recently';
  const d = typeof iso === 'string' ? new Date(iso) : iso;
  if (isToday(d)) return `last seen at ${format(d, 'HH:mm')}`;
  if (isYesterday(d)) return `last seen yesterday at ${format(d, 'HH:mm')}`;
  return `last seen ${formatDistanceToNowStrict(d, { addSuffix: true })}`;
}

export function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export function bytesToHuman(bytes: number | null | undefined): string {
  if (!bytes) return '';
  const units = ['B', 'KB', 'MB', 'GB'];
  let val = bytes;
  let i = 0;
  while (val >= 1024 && i < units.length - 1) {
    val /= 1024;
    i++;
  }
  return `${val.toFixed(val < 10 ? 1 : 0)} ${units[i]}`;
}

export function getInitials(name: string | null | undefined): string {
  if (!name) return '?';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return (parts[0]![0]! + parts[1]![0]!).toUpperCase();
}

const COLORS = ['#e17076', '#eda86c', '#a695e7', '#7bc862', '#6ec9cb', '#65aadd', '#ee7aae', '#67abf2'];
export function colorFromId(id: number | string): string {
  const n = typeof id === 'number' ? id : id.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
  return COLORS[Math.abs(n) % COLORS.length]!;
}
