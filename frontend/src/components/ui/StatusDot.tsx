export type DotStatus = 'running' | 'finished' | 'ungrounded' | 'failed' | 'pending' | 'open' | 'reconnecting' | 'closed';

const DOT_CLASSES: Record<DotStatus, string> = {
  running: 'bg-accent animate-pulse',
  finished: 'bg-ok',
  ungrounded: 'bg-band-warning',
  failed: 'bg-band-critical',
  pending: 'bg-ink-3',
  open: 'bg-ok',
  reconnecting: 'bg-band-watch',
  closed: 'bg-band-critical',
};

export function StatusDot({ status, label }: { status: DotStatus; label: string }) {
  return (
    <span role="status" data-status={status} className="inline-flex items-center gap-1.5 text-[12px]">
      <span aria-hidden="true" className={`inline-block size-2 rounded-full ${DOT_CLASSES[status]}`} />
      <span>{label}</span>
    </span>
  );
}
