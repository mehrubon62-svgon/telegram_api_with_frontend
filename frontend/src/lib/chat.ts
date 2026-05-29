import type { ChatOut } from '@/api/types';

/** Отображаемое имя чата: для private — имя собеседника. */
export function chatDisplayName(chat: ChatOut): string {
  if (chat.type === 'saved') return 'Saved Messages';
  if (chat.type === 'private' && chat.peer) {
    return chat.peer.full_name ?? chat.peer.username ?? `User ${chat.peer.id}`;
  }
  return chat.title ?? chat.public_username ?? `Chat ${chat.id}`;
}

/** Аватар чата: для private — аватар собеседника. */
export function chatAvatar(chat: ChatOut): string | null {
  if (chat.type === 'private' && chat.peer) return chat.peer.avatar_url;
  return chat.avatar_url;
}

/** id для генерации цвета аватара. */
export function chatAvatarId(chat: ChatOut): number {
  if (chat.type === 'private' && chat.peer) return chat.peer.id;
  return chat.id;
}
