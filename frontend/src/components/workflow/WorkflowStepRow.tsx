import type { Ref } from 'react';
import type { WorkflowNode, WorkflowStep } from '@/api/types';
import { IconCheck, IconClose, IconPause, IconPending } from '@/components/ui/icons';
import { fmtMs } from './labels';
import { StepBody } from './StepBody';

type RowStatus = WorkflowStep['status'] | 'pending';

function StatusIcon({ status }: { status: RowStatus }) {
  switch (status) {
    case 'pending': return <IconPending className="size-4 text-ink-3" title="Not reached" />;
    case 'running':
      return (
        <span role="img" aria-label="Running" title="Running"
          className="inline-block size-3.5 m-px rounded-full border-2 border-accent border-t-transparent animate-spin" />
      );
    case 'done': return <IconCheck className="size-4 text-ok-text" title="Done" />;
    case 'waiting': return <IconPause className="size-4 text-band-watch-text" title="Waiting" />;
    case 'failed': return <IconClose className="size-4 text-band-critical-text" title="Failed" />;
  }
}

interface RowProps {
  node: WorkflowNode;
  index: number;
  label: string;
  step: WorkflowStep | undefined;
  active: boolean;
  rowRef?: Ref<HTMLLIElement>;
}

/** One numbered step of the run: its state, how long it took, and what it produced. */
export function WorkflowStepRow({ node, index, label, step, active, rowRef }: RowProps) {
  const status: RowStatus = step?.status ?? 'pending';
  return (
    <li ref={rowRef} data-node={node} data-status={status} aria-current={active ? 'step' : undefined}
      className={`grid grid-cols-[1.5rem_1fr] gap-x-2 px-3 py-2 border-b border-line ${active ? 'bg-raised' : ''}`}>
      <span className={`tnum text-[12px] pt-px text-right ${status === 'pending' ? 'text-ink-3' : 'text-ink-2'}`}>{index}</span>
      <div className="min-w-0 flex flex-col gap-1.5">
        <div className="flex items-center gap-2">
          <StatusIcon status={status} />
          <h3 className={`condensed text-[13px] font-semibold tracking-wide ${status === 'pending' ? 'text-ink-3' : ''}`}>{label}</h3>
          {step?.duration_ms != null && <span className="ml-auto text-[11px] text-ink-3 tnum">{fmtMs(step.duration_ms)}</span>}
        </div>
        {step && (
          <div className="text-[13px]">
            {step.error && <p role="alert" className="text-[12px] text-band-critical-text">{step.error}</p>}
            <StepBody step={step} />
          </div>
        )}
      </div>
    </li>
  );
}
