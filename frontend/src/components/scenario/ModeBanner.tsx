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
  // Band colours mean severity only: the mock notice is ink on slate; a lost connection is a warning.
  const tone = mode === 'mock' ? 'border-l-line-strong text-ink-2' : 'border-l-band-warning text-band-warning-text';
  return (
    <div role="status" className={`px-4 py-1 text-[12px] bg-panel border-b border-b-line border-l-2 ${tone}`}>
      {text}
    </div>
  );
}
