import type { ApiMode } from '@/api/client';
import type { ConnectionStatus } from '@/live/types';

function bannerText(mode: ApiMode, connection: ConnectionStatus): string | null {
  if (mode === 'mock') return 'Mock data. Backend not connected.';
  if (connection === 'open') return null;
  if (connection === 'connecting') return 'Connecting…';
  if (connection === 'reconnecting') return 'Connection lost. Reconnecting…';
  return 'Disconnected from the backend.';
}

export function ModeBanner({ mode, connection }: { mode: ApiMode; connection: ConnectionStatus }) {
  const text = bannerText(mode, connection);
  if (text === null) return null;
  const tone = mode === 'mock' ? 'border-band-watch text-band-watch-text' : 'border-band-warning text-band-warning-text';
  return (
    <div role="status" className={`px-4 py-1 text-[12px] bg-panel border-b border-l-2 ${tone}`}>
      {text}
    </div>
  );
}
