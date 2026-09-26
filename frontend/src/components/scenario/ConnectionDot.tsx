import { StatusDot, type DotStatus } from '@/components/ui/StatusDot';
import type { ConnectionStatus } from '@/live/types';

const MAP: Record<ConnectionStatus, { status: DotStatus; label: string }> = {
  connecting: { status: 'pending', label: 'Connecting' },
  open: { status: 'open', label: 'Live' },
  reconnecting: { status: 'reconnecting', label: 'Reconnecting' },
  closed: { status: 'closed', label: 'Disconnected' },
};

export function ConnectionDot({ connection }: { connection: ConnectionStatus }) {
  const { status, label } = MAP[connection];
  return <StatusDot status={status} label={label} />;
}
