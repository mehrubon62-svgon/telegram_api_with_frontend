import { create } from 'zustand';
import type { MessageOut } from '@/api/types';

interface ComposerState {
  // chatId → состояние композера
  reply: Record<number, MessageOut | null>;
  editing: Record<number, MessageOut | null>;
  setReply: (chatId: number, m: MessageOut | null) => void;
  setEditing: (chatId: number, m: MessageOut | null) => void;
  clear: (chatId: number) => void;
}

export const useComposerStore = create<ComposerState>((set) => ({
  reply: {},
  editing: {},
  setReply: (chatId, m) =>
    set((s) => ({ reply: { ...s.reply, [chatId]: m }, editing: { ...s.editing, [chatId]: null } })),
  setEditing: (chatId, m) =>
    set((s) => ({ editing: { ...s.editing, [chatId]: m }, reply: { ...s.reply, [chatId]: null } })),
  clear: (chatId) =>
    set((s) => ({ reply: { ...s.reply, [chatId]: null }, editing: { ...s.editing, [chatId]: null } })),
}));
