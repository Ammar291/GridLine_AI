import { useEffect } from 'react';
import type { ApiClient } from '@/api/client';
import type { Event } from '@/api/types';
import { isEngineReset } from './applyEvent';
import { useLiveStore } from './liveStore';
import { LiveSocket } from './socket';

/** At 10x the backend sends about 200 events a second; applying them in batches keeps it to ~20 renders a second. */
export const BATCH_MS = 50;

/** One LiveSocket per client for the component's lifetime, feeding the live store in batches. */
export function useLive(client: ApiClient): void {
  useEffect(() => {
    const { dispatchMany, setConnection, setMode } = useLiveStore.getState();
    setMode(client.mode);
    let queue: Event[] = [];
    let timer: ReturnType<typeof setTimeout> | null = null;
    const flush = () => {
      timer = null;
      const batch = queue;
      queue = [];
      dispatchMany(batch);
    };
    const socket = new LiveSocket({
      client,
      onEvent: (e) => {
        queue.push(e);
        timer ??= setTimeout(flush, BATCH_MS);
        if (isEngineReset(e)) socket.resync(); // the reset world arrives in the new connection's snapshot
      },
      onStatus: setConnection,
    });
    socket.start();
    return () => {
      socket.stop();
      if (timer !== null) clearTimeout(timer);
    };
  }, [client]);
}
