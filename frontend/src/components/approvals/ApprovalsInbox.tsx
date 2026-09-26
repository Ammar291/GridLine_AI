import { useState, type ReactNode } from 'react';
import { ApiError } from '@/api/client';
import { useDecideApproval } from '@/api/queries';
import type { Approval } from '@/api/types';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { IconChevron } from '@/components/ui/icons';
import { LoadingState } from '@/components/ui/LoadingState';
import { Panel } from '@/components/ui/Panel';
import { useSelectedIncident } from '@/hooks/useSelectedIncident';
import { useLiveStore } from '@/live/liveStore';
import { ApprovalCard } from './ApprovalCard';

function errorText(err: unknown): string {
  return err instanceof ApiError ? `Decision failed (${String(err.status)}). Try again.` : 'Decision failed. Try again.';
}

/** Approvals across all incidents: pending first (the selected incident's on top), decided ones folded away. */
export function ApprovalsInbox() {
  const hasSnapshot = useLiveStore((s) => s.hasSnapshot);
  const connection = useLiveStore((s) => s.connection);
  const approvals = useLiveStore((s) => s.approvals);
  const actions = useLiveStore((s) => s.actions);
  const { incidentId } = useSelectedIncident();
  const decide = useDecideApproval();
  const [showDecided, setShowDecided] = useState(false);

  const all = Object.values(approvals);
  const selectedFirst = (a: Approval) => (a.incident_id === incidentId ? 0 : 1);
  const pending = all
    .filter((a) => a.status === 'pending')
    .sort((a, b) => selectedFirst(a) - selectedFirst(b) || a.requested_at.localeCompare(b.requested_at));
  const decided = all
    .filter((a) => a.status !== 'pending')
    .sort((a, b) => (b.decided_at ?? '').localeCompare(a.decided_at ?? ''));

  const target = decide.variables?.id;
  const card = (approval: Approval) => (
    <ApprovalCard
      key={approval.id}
      approval={approval}
      actions={actions}
      onDecide={(body) => { decide.mutate({ id: approval.id, body }); }}
      deciding={decide.isPending && target === approval.id}
      sent={decide.isSuccess && target === approval.id}
      error={decide.isError && target === approval.id ? errorText(decide.error) : null}
    />
  );

  let body: ReactNode;
  if (!hasSnapshot) {
    body = connection === 'closed'
      ? <ErrorState message="Live connection closed before the city state arrived. Reload the page to reconnect." />
      : <LoadingState label="Waiting for city state" />;
  } else {
    body = (
      <>
        {pending.length === 0
          ? <EmptyState title="No approvals waiting. Proposed actions appear here when the agent asks for a decision." />
          : pending.map(card)}
        {decided.length > 0 && (
          <div>
            <button type="button" aria-expanded={showDecided} onClick={() => { setShowDecided((v) => !v); }}
              className="flex items-center gap-2 w-full h-8 px-3 text-left text-[12px] text-ink-2 hover:bg-raised border-b border-line">
              <IconChevron className={`shrink-0 text-ink-3 ${showDecided ? 'rotate-90' : ''}`} />
              Decided
              <span className="tnum text-ink-3">{decided.length}</span>
            </button>
            {showDecided && decided.map(card)}
          </div>
        )}
      </>
    );
  }

  return (
    <Panel title="Approvals" count={hasSnapshot ? pending.length : undefined}>
      {body}
    </Panel>
  );
}
