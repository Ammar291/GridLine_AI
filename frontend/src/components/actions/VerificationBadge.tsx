import { IconCheck, IconPending, IconReplan, IconWarning } from '@/components/ui/icons';
import type { VerificationState } from './verification';

const TEXT: Record<VerificationState, string> = {
  verified: 'Verified',
  partially_verified: 'Partially verified',
  failed: 'Failed',
  pending: 'Verifying…',
  replanning: 'Re-planning',
};
const TONE: Record<VerificationState, string> = {
  verified: 'text-ok-text',
  partially_verified: 'text-band-critical-text',
  failed: 'text-band-critical-text',
  pending: 'text-ink-2',
  replanning: 'text-band-watch-text',
};

function icon(state: VerificationState) {
  switch (state) {
    case 'verified': return <IconCheck className="shrink-0" />;
    case 'partially_verified':
    case 'failed': return <IconWarning className="shrink-0" />;
    case 'pending': return <IconPending className="shrink-0 animate-spin" />;
    case 'replanning': return <IconReplan className="shrink-0" />;
  }
}

/** Outcome of re-reading the world after an action: always an icon and words, never colour alone. */
export function VerificationBadge({ state, minutesWaited }: { state: VerificationState; minutesWaited?: number | null }) {
  return (
    <span data-testid="verification-badge" data-state={state} className={`inline-flex items-center gap-1 text-[12px] font-medium shrink-0 ${TONE[state]}`}>
      {icon(state)}
      {TEXT[state]}
      {state === 'pending' && minutesWaited != null && (
        <span className="tnum font-normal text-ink-3">{`${String(minutesWaited)} min`}</span>
      )}
    </span>
  );
}
