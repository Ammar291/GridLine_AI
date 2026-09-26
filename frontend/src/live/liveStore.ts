import { create } from 'zustand';
import { readApiMode, type ApiMode } from '@/api/client';
import type { Event } from '@/api/types';
import { applyEvents } from './applyEvent';
import { initialLiveState, type ConnectionStatus, type LiveState } from './types';

export interface LiveActions {
  dispatch: (e: Event) => void;
  /** Apply a batch of events in one store update (one render for many socket frames). */
  dispatchMany: (events: readonly Event[]) => void;
  setConnection: (c: ConnectionStatus) => void;
  setMode: (m: ApiMode) => void;
  resetLive: () => void;
}
export type LiveStore = LiveState & LiveActions;

export const useLiveStore = create<LiveStore>()((set) => ({
  ...initialLiveState(readApiMode()),
  dispatch: (e) => { set((s) => applyEvents(s, [e])); },
  dispatchMany: (events) => { if (events.length > 0) set((s) => applyEvents(s, events)); },
  setConnection: (connection) => { set({ connection }); },
  setMode: (mode) => { set({ mode }); },
  resetLive: () => { set((s) => ({ ...initialLiveState(s.mode) })); },
}));
