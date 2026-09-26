import type { AgentRun, AgentStep, NodeName } from '@/api/types';
import { NODE_LABELS, NODE_ORDER } from './nodeLabels';

type NodeStatus = AgentStep['status'] | 'not_started';

const DOT: Record<NodeStatus, string> = {
  running: 'bg-accent animate-pulse',
  finished: 'bg-ok',
  ungrounded: 'bg-band-warning',
  failed: 'bg-band-critical',
  not_started: 'border border-ink-3',
};
const TEXT: Record<NodeStatus, string> = {
  running: 'running', finished: 'finished', ungrounded: 'ungrounded', failed: 'failed', not_started: 'not started',
};

function nodeStatus(run: AgentRun | undefined, node: NodeName): NodeStatus {
  let status: NodeStatus = 'not_started';
  for (const s of run?.steps ?? []) if (s.node === node) status = s.status;
  return status;
}

/** Where the run is in the graph: one dot per node, re-plan only once the run has reached it. */
export function NodeRail({ run }: { run: AgentRun | undefined }) {
  const hasReplan = run?.steps.some((s) => s.node === 'replan') ?? false;
  const nodes = hasReplan ? NODE_ORDER : NODE_ORDER.filter((n) => n !== 'replan');
  return (
    <ol aria-label="Agent nodes" className="flex flex-wrap items-center gap-x-3 gap-y-1">
      {nodes.map((node) => {
        const status = nodeStatus(run, node);
        return (
          <li key={node} aria-label={`${NODE_LABELS[node]}: ${TEXT[status]}`} data-status={status}
            className={`flex items-center gap-1.5 text-[11px] ${status === 'not_started' ? 'text-ink-3' : 'text-ink-2'}`}>
            <span aria-hidden="true" className={`inline-block size-2 rounded-full ${DOT[status]}`} />
            {NODE_LABELS[node]}
          </li>
        );
      })}
    </ol>
  );
}
