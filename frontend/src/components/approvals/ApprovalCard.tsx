import { useId, useMemo, useState } from 'react';
import type { Action, Approval, ApprovalDecision, ApprovalStatus } from '@/api/types';
import { runCitations } from '@/components/incident/citations';
import { zoneName } from '@/live/derive';
import { fmtWall, statusLabel } from '@/live/format';
import { useLiveStore } from '@/live/liveStore';
import { useLiveAssets } from '@/live/useLiveAssets';
import { useUiStore } from '@/ui/uiStore';
import { actionTargetName } from './actionTarget';
import { DecisionBar } from './DecisionBar';
import { ProposedActionCard } from './ProposedActionCard';
import { proposedActionState } from './proposedActionState';

interface ApprovalCardProps {
  approval: Approval;
  actions: Record<string, Action>;
  onDecide: (body: ApprovalDecision) => void;
  deciding: boolean;
  error: string | null;
  /** The decision was accepted; the card waits for approval.decided before it moves. */
  sent?: boolean;
}

const STATUS_CHIP: Record<ApprovalStatus, string> = {
  pending: 'border border-accent text-accent',
  approved: 'border border-ok text-ok-text',
  partial: 'border border-line-strong text-ink',
  rejected: 'border border-band-critical text-band-critical-text',
};

/** One approval request: the proposed plan, and while it is pending, the operator's decision bar. */
export function ApprovalCard({ approval, actions, onDecide, deciding, error, sent = false }: ApprovalCardProps) {
  const city = useLiveStore((s) => s.city);
  const assets = useLiveAssets();
  const incident = useLiveStore((s) => s.incidents[approval.incident_id]);
  const openWhy = useUiStore((s) => s.openWhy);
  const headingId = useId();
  const needsDecision = approval.proposed_actions.filter((a) => a.requires_approval).map((a) => a.action_id);
  const [selected, setSelected] = useState<ReadonlySet<string>>(() => new Set(needsDecision));
  const [note, setNote] = useState('');
  const citations = useMemo(() => runCitations(incident?.runs.find((r) => r.id === approval.run_id)), [incident, approval.run_id]);

  const pending = approval.status === 'pending';
  const locked = pending && (deciding || sent);
  const title = incident ? `${statusLabel(incident.hazard)} in ${zoneName(city, incident.zone_id)}` : `Incident ${approval.incident_id}`;
  const chosen = needsDecision.filter((id) => selected.has(id));
  const recordedNote = note.trim() === '' ? null : note.trim();
  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };
  const decidedLine = `${approval.decided_by ? `Decided by ${approval.decided_by}` : 'Decided'}${approval.decided_at ? ` at ${fmtWall(approval.decided_at)}` : ''}`;

  return (
    <section aria-labelledby={headingId} className="px-3 py-2.5 border-b border-line">
      <header className="flex items-center gap-2 min-w-0">
        <h3 id={headingId} className="condensed text-[13px] font-medium truncate">{title}</h3>
        <span className="text-[11px] text-ink-3 tnum shrink-0">{pending ? `Requested ${fmtWall(approval.requested_at)}` : decidedLine}</span>
        {approval.synthetic && <span className="shrink-0 rounded-[3px] bg-raised px-1.5 text-[11px] leading-5 text-ink-2">Auto-approved (demo)</span>}
        <span className={`ml-auto shrink-0 rounded-[3px] px-1.5 text-[11px] leading-5 font-medium ${STATUS_CHIP[approval.status]}`}>
          {statusLabel(approval.status)}
        </span>
      </header>
      {!pending && approval.note && (
        <p className="text-[12px] text-ink-2 mt-1"><span className="text-ink-3">Note </span><span>{approval.note}</span></p>
      )}
      <div>
        {approval.proposed_actions.map((a) => (
          <ProposedActionCard
            key={a.action_id}
            action={a}
            state={proposedActionState(a, approval, actions[a.action_id])}
            selectable={pending && a.requires_approval}
            selected={selected.has(a.action_id)}
            onToggle={() => { toggle(a.action_id); }}
            onWhy={() => { openWhy({ kind: 'action', actionId: a.action_id, incidentId: approval.incident_id }); }}
            targetName={actionTargetName(a.tool, a.input, assets, city)}
            citations={citations}
            disabled={locked}
          />
        ))}
      </div>
      {pending && (
        <DecisionBar
          total={needsDecision.length}
          selected={chosen.length}
          onApproveAll={() => { onDecide({ decision: 'approve', approved_action_ids: needsDecision, note: recordedNote }); }}
          onApproveSelected={() => { onDecide({ decision: 'partial', approved_action_ids: chosen, note: recordedNote }); }}
          onReject={() => { onDecide({ decision: 'reject', approved_action_ids: [], note: recordedNote }); }}
          note={note}
          onNote={setNote}
          disabled={locked}
        />
      )}
      {pending && deciding && <p role="status" className="mt-1.5 text-[12px] text-ink-2">Sending decision…</p>}
      {pending && sent && <p role="status" className="mt-1.5 text-[12px] text-ink-2">Decision sent. Waiting for confirmation.</p>}
      {pending && error !== null && <p role="alert" className="mt-1.5 text-[12px] text-band-critical-text">{error}</p>}
    </section>
  );
}
