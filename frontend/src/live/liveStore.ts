import { create } from 'zustand';
import { readApiMode, type ApiMode } from '@/api/client';
import type { Event } from '@/api/types';
import { applyEvent } from './applyEvent';
import { initialLiveState, type ConnectionStatus, type LiveState } from './types';

export interface LiveActions {
  dispatch: (e: Event) => void;
  setConnection: (c: ConnectionStatus) => void;
  setMode: (m: ApiMode) => void;
  resetLive: () => void;
}
export type LiveStore = LiveState & LiveActions;

export const useLiveStore = create<LiveStore>()((set) => ({
  ...initialLiveState(readApiMode()),
  dispatch: (e) => { set((s) => applyEvent(s, e)); },
  setConnection: (connection) => { set({ connection }); },
  setMode: (mode) => { set({ mode }); },
  resetLive: () => { set((s) => ({ ...initialLiveState(s.mode) })); },
}));
