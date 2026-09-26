import type { Action } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { KeyValue } from '@/components/ui/KeyValue';
import { fmtSimTime, statusLabel, toolVerb } from '@/live/format';
import { StateTransition } from './StateTransition';
import type { VerificationState } from './verification';
import { VerificationBadge } from './VerificationBadge';

interface ActionRowProps {
  action: Action;
  targetName: string;
  verification: VerificationState;
  /** Sim minutes since execution, shown while verification is pending. */
  minutesWaited: number | null;
  onWhy: () => void;
}

/** One executed (or executing) action: what changed in the city, and whether re-reading the world confirmed it. */
export function ActionRow({ action, targetName, verification, minutesWaited, onWhy }: ActionRowProps) {
  const verb = toolVerb(action.tool);
  const title = targetName === '' ? verb : `${verb}: ${targetName}`;
  const v = action.verification;
  return (
    <article aria-label={title} className="flex flex-col gap-1.5 px-3 py-2.5 border-b border-line">
      <div className="flex items-center gap-2 min-w-0">
        <h3 className="condensed text-[14px] font-medium shrink-0">{verb}</h3>
        <span className="text-ink-2 truncate">{targetName}</span>
        <span className="ml-auto shrink-0 tnum text-[11px] text-ink-3">
          {action.executed_sim_time ? `Executed ${fmtSimTime(action.executed_sim_time)}` : statusLabel(action.status)}
        </span>
        <VerificationBadge state={verification} minutesWaited={minutesWaited} />
        <Button size="sm" aria-label={`Why? ${verb}`} onClick={onWhy}>Why?</Button>
      </div>
      {action.state_changes.length > 0 ? (
        <ul aria-label="State changes" className="flex flex-col gap-1">
          {action.state_changes.map((c) => <StateTransition key={`${c.entity_type}:${c.entity_id}:${c.field}`} change={c} />)}
        </ul>
      ) : (
        <p className="text-[12px] text-ink-3">No state change recorded.</p>
      )}
      {v && (
        <KeyValue columns={2} items={[
          { label: 'Expected', value: v.expected },
          { label: 'Observed', value: v.observed === '' ? 'Not checked yet' : v.observed, muted: v.observed === '' },
        ]} />
      )}
      {v && v.failures.length > 0 && (
        <ul aria-label="Verification failures" className="flex flex-col gap-0.5 text-[12px] text-band-critical-text">
          {v.failures.map((f, i) => <li key={`${String(i)}:${f}`}>{f}</li>)}
        </ul>
      )}
    </article>
  );
}
