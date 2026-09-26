import type { AgentRun } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { StatusDot } from '@/components/ui/StatusDot';
import { fmtNumber } from '@/live/format';
import { useUiStore } from '@/ui/uiStore';
import { NODE_LABELS } from './nodeLabels';

/** Every step the run has taken, in order, each with its timing and a Why? entry point. */
export function StepList({ run }: { run: AgentRun }) {
  const openWhy = useUiStore((s) => s.openWhy);
  if (run.steps.length === 0) return <p className="text-ink-3">No node has started yet.</p>;
  return (
    <ul aria-label="Steps" className="flex flex-col">
      {run.steps.map((step) => (
        <li key={step.id} className="flex flex-col py-1 border-b border-line last:border-b-0">
          <div className="flex items-center gap-3">
            <StatusDot status={step.status} label={NODE_LABELS[step.node]} />
            <span className="ml-auto tnum text-[11px] text-ink-3">
              {step.duration_ms == null ? '' : `${fmtNumber(step.duration_ms)} ms`}
            </span>
            <Button size="sm" aria-label={`Why? ${NODE_LABELS[step.node]}`}
              onClick={() => { openWhy({ kind: 'step', stepId: step.id, runId: run.id, incidentId: run.incident_id }); }}>
              Why?
            </Button>
          </div>
          {step.status === 'ungrounded' && (
            <p className="text-[12px] text-band-warning-text">Grounding check failed; confidence lowered.</p>
          )}
          {step.status === 'failed' && <p className="text-[12px] text-band-critical-text">This node failed.</p>}
        </li>
      ))}
    </ul>
  );
}
