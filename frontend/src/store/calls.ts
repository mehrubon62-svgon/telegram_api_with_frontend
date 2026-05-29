import { create } from 'zustand';
import type { CallOut } from '@/api/types';

interface CallsState {
  active: CallOut | null;
  incoming: CallOut | null;
  setActive: (c: CallOut | null) => void;
  setIncoming: (c: CallOut | null) => void;
}

export const useCallsStore = create<CallsState>((set) => ({
  active: null,
  incoming: null,
  setActive: (active) => set({ active }),
  setIncoming: (incoming) => set({ incoming }),
}));
