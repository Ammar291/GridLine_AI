import { useMemo, type ReactNode } from 'react';
import type { Action } from '@/api/types';
import { actionTargetName } from '@/components/approvals/actionTarget';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { Panel } from '@/components/ui/Panel';
import { useLiveStore } from '@/live/liveStore';
import { useUiStore } from '@/ui/uiStore';
import { ActionRow } from './ActionRow';
import { replanRunIds, simMinutesBetween, verificationState } from './verification';

// Actions still executing have no executed_at yet; they are the newest.
const executedAt = (a: Action) => a.executed_at ?? '￿';

/** Every action across incidents, newest first, with its state transitions and verification. */
export function ActionsLog() {
  const hasSnapshot = useLiveStore((s) => s.hasSnapshot);
  const connection = useLiveStore((s) => s.connection);
  const actions = useLiveStore((s) => s.actions);
  const milestones = useLiveStore((s) => s.milestones);
  const assets = useLiveStore((s) => s.assets);
  const city = useLiveStore((s) => s.city);
  const simTime = useLiveStore((s) => s.sim.simTime);
  const openWhy = useUiStore((s) => s.openWhy);

  const replanning = useMemo(() => replanRunIds(milestones), [milestones]);
  const list = useMemo(
    () => Object.values(actions).sort((a, b) => executedAt(b).localeCompare(executedAt(a)) || a.id.localeCompare(b.id)),
    [actions],
  );

  let body: ReactNode;
  if (!hasSnapshot) {
    body = connection === 'closed'
      ? <ErrorState message="Live connection closed before the city state arrived. Reload the page to reconnect." />
      : <LoadingState label="Waiting for city state" />;
  } else if (list.length === 0) {
    body = <EmptyState title="No actions yet. Approved actions appear here as they execute." />;
  } else {
    body = list.map((action) => {
      const state = verificationState(action, replanning);
      return (
        <ActionRow
          key={action.id}
          action={action}
          targetName={action.state_changes[0]?.entity_name ?? actionTargetName(action.tool, action.input, assets, city)}
          verification={state}
          minutesWaited={state === 'pending' ? simMinutesBetween(action.executed_sim_time, simTime) : null}
          onWhy={() => { openWhy({ kind: 'action', actionId: action.id, incidentId: action.incident_id }); }}
        />
      );
    });
  }

  return (
    <Panel title="Actions" count={hasSnapshot ? list.length : undefined}>
      {body}
    </Panel>
  );
}
