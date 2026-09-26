import type { WorkflowApprovalOutput, WorkflowStep } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { fmtWall } from '@/live/format';
import { Meta } from './bits';
import { useDecideRunApproval } from './useDecideRunApproval';

/** The human gate: approve or reject the plan while the run waits; afterwards, the recorded decision. */
export function ApprovalBody({ step, out }: { step: WorkflowStep; out: WorkflowApprovalOutput }) {
  const decide = useDecideRunApproval(step.run_id);
  const n = out.action_ids.length;
  const count = `${String(n)} ${n === 1 ? 'action' : 'actions'}`;

  if (out.decision !== null) {
    const when = out.decided_at ? ` at ${fmtWall(out.decided_at)}` : '';
    return (
      <div className="flex flex-col gap-0.5">
        <p className={out.decision === 'approve' ? 'text-ok-text' : 'text-band-critical-text'}>
          {`${out.decision === 'approve' ? 'Approved' : 'Rejected'} ${count}${when}`}
        </p>
        {out.note && <Meta>{`Note: ${out.note}`}</Meta>}
      </div>
    );
  }
  if (step.status !== 'waiting') return <Meta>{`${count} submitted for approval`}</Meta>;

  const busy = decide.isPending || decide.isSuccess;
  return (
    <div className="flex flex-col gap-2 rounded-[3px] border border-band-watch bg-band-watch/10 p-2.5">
      <p className="text-[13px]">{`The agent is waiting for your decision on ${count}. Nothing changes in the city until you decide.`}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="primary" className="h-9 px-5 text-[14px] font-semibold tracking-wide" disabled={busy}
          onClick={() => { decide.mutate({ decision: 'approve' }); }}>
          APPROVE ACTIONS
        </Button>
        <Button disabled={busy} onClick={() => { decide.mutate({ decision: 'reject' }); }}>Reject</Button>
        {decide.isPending && <span className="text-[12px] text-ink-2">Sending decision</span>}
        {decide.isSuccess && <span className="text-[12px] text-ink-2">Decision sent, resuming the run</span>}
      </div>
      {decide.isError && <p role="alert" className="text-[12px] text-band-critical-text">{`Decision failed: ${decide.error.message}`}</p>}
    </div>
  );
}
