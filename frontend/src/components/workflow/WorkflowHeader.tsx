import type { WorkflowStep } from '@/api/types';
import { StatusDot, type DotStatus } from '@/components/ui/StatusDot';
import { outputOf, runStatus, type RunStatus } from '@/live/applyAgentStep';
import { statusLabel } from '@/live/format';

const RUN_DOT: Record<RunStatus, { dot: DotStatus; label: string }> = {
  running: { dot: 'running', label: 'Running' },
  waiting: { dot: 'ungrounded', label: 'Waiting for approval' },
  completed: { dot: 'finished', label: 'Completed' },
  rejected: { dot: 'pending', label: 'Rejected' },
  failed: { dot: 'failed', label: 'Failed' },
};

/** Which model reasoned: Ollama by name, or the mock reasoner and why it was used. */
export function ProviderBadge({ steps }: { steps: readonly WorkflowStep[] }) {
  const outs = [outputOf(steps, 'reason'), outputOf(steps, 'recommend')].filter((o) => o !== undefined);
  const fallback = outs.find((o) => o.fallback_reason !== null);
  const first = outs[0];
  if (first === undefined) return null;
  const base = 'inline-block max-w-[320px] truncate rounded-[3px] border px-1.5 text-[11px] leading-5';
  if (fallback) {
    const text = `mock — Ollama unavailable: ${fallback.fallback_reason ?? ''}`;
    return <span title={text} className={`${base} border-band-warning text-band-warning-text`}>{text}</span>;
  }
  if (first.provider === 'ollama') return <span className={`${base} border-ok text-ok-text`}>{`ollama · ${first.model ?? ''}`}</span>;
  return <span className={`${base} border-line text-ink-2`}>mock (offline)</span>;
}

/** The trigger (hazard, asset, zone from the received event) and the run's derived status. */
export function WorkflowHeader({ steps }: { steps: readonly WorkflowStep[] }) {
  const trigger = outputOf(steps, 'receive');
  const status = RUN_DOT[runStatus(steps)];
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2 border-b border-line">
      <p className="min-w-0 text-[13px]">
        {trigger ? (
          <>
            <span className="font-semibold">{`${statusLabel(trigger.hazard)} at ${trigger.asset.id}`}</span>{' '}
            <span className="text-ink-2">{`${trigger.asset.name}, ${trigger.zone_name}`}</span>
          </>
        ) : <span className="text-ink-2">Receiving the event</span>}
      </p>
      <span className="ml-auto flex items-center gap-2">
        <ProviderBadge steps={steps} />
        <StatusDot status={status.dot} label={status.label} />
      </span>
    </div>
  );
}
