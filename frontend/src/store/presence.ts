import { create } from 'zustand';

interface PresenceState {
  online: Set<number>;
  typing: Map<number, Map<number, number>>; // chat_id -> user_id -> timestamp
  lastSeen: Map<number, string>;
  setOnlineUsers: (ids: number[]) => void;
  setOnline: (uid: number, online: boolean, lastSeen?: string) => void;
  setTyping: (chatId: number, userId: number) => void;
  clearTyping: (chatId: number, userId: number) => void;
  isOnline: (uid: number) => boolean;
  getTypingUsers: (chatId: number) => number[];
}

export const usePresenceStore = create<PresenceState>((set, get) => ({
  online: new Set(),
  typing: new Map(),
  lastSeen: new Map(),
  setOnlineUsers: (ids) => set({ online: new Set(ids) }),
  setOnline: (uid, online, lastSeen) =>
    set((s) => {
      const next = new Set(s.online);
      if (online) next.add(uid);
      else next.delete(uid);
      const ls = new Map(s.lastSeen);
      if (lastSeen) ls.set(uid, lastSeen);
      return { online: next, lastSeen: ls };
    }),
  setTyping: (chatId, userId) =>
    set((s) => {
      const map = new Map(s.typing);
      const inner = new Map(map.get(chatId) ?? []);
      inner.set(userId, Date.now());
      map.set(chatId, inner);
      return { typing: map };
    }),
  clearTyping: (chatId, userId) =>
    set((s) => {
      const map = new Map(s.typing);
      const inner = new Map(map.get(chatId) ?? []);
      inner.delete(userId);
      if (inner.size === 0) map.delete(chatId);
      else map.set(chatId, inner);
      return { typing: map };
    }),
  isOnline: (uid) => get().online.has(uid),
  getTypingUsers: (chatId) => {
    const m = get().typing.get(chatId);
    if (!m) return [];
    const cutoff = Date.now() - 6000;
    return Array.from(m.entries())
      .filter(([, ts]) => ts > cutoff)
      .map(([uid]) => uid);
  },
}));

// Глобальный таймер для авто-сброса typing спустя 6 секунд
setInterval(() => {
  const s = usePresenceStore.getState();
  const cutoff = Date.now() - 6000;
  let dirty = false;
  const next = new Map(s.typing);
  for (const [chatId, inner] of next) {
    const filtered = new Map<number, number>();
    for (const [uid, ts] of inner) {
      if (ts > cutoff) filtered.set(uid, ts);
      else dirty = true;
    }
    if (filtered.size === 0) next.delete(chatId);
    else next.set(chatId, filtered);
  }
  if (dirty) usePresenceStore.setState({ typing: next });
}, 2000);
