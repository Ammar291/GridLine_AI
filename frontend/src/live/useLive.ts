import { useEffect } from 'react';
import type { ApiClient } from '@/api/client';
import { useLiveStore } from './liveStore';
import { LiveSocket } from './socket';

/** One LiveSocket per client for the component's lifetime, feeding the live store. */
export function useLive(client: ApiClient): void {
  useEffect(() => {
    const { dispatch, setConnection, setMode } = useLiveStore.getState();
    setMode(client.mode);
    const socket = new LiveSocket({ client, onEvent: dispatch, onStatus: setConnection });
    socket.start();
    return () => { socket.stop(); };
  }, [client]);
}
