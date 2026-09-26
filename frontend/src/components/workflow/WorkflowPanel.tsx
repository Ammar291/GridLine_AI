import { useEffect, useRef } from 'react';
import { EmptyState } from '@/components/ui/EmptyState';
import { Panel } from '@/components/ui/Panel';
import { useLiveStore } from '@/live/liveStore';
import { WORKFLOW_STEPS } from './labels';
import { WorkflowHeader } from './WorkflowHeader';
import { WorkflowStepRow } from './WorkflowStepRow';

/** The live agent workflow: every graph node of the current run, in order, with what each one produced. */
export function WorkflowPanel() {
  const run = useLiveStore((s) => s.agentRun);
  const activeRef = useRef<HTMLLIElement>(null);
  const steps = run?.steps ?? [];
  // The step in progress (running, waiting or failed), else the furthest one reached.
  const active = [...steps].reverse().find((s) => s.status !== 'done') ?? steps.at(-1);
  const activeKey = active ? `${active.run_id}:${active.node}:${active.status}` : '';

  useEffect(() => {
    // jsdom has no scrollIntoView.
    if (activeKey !== '' && typeof activeRef.current?.scrollIntoView === 'function') {
      activeRef.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [activeKey]);

  return (
    <Panel title="LIVE AGENT WORKFLOW" testId="workflow-panel">
      {run === null ? (
        <EmptyState title="No agent run yet. A run starts when an infrastructure failure is reported." />
      ) : (
        <>
          <WorkflowHeader steps={steps} />
          {/* Keyed by run so a new run starts with fresh approval buttons. */}
          <ol key={run.runId} aria-label="Workflow steps">
            {WORKFLOW_STEPS.map(({ node, label }, i) => {
              const isActive = active?.node === node;
              return (
                <WorkflowStepRow key={node} node={node} index={i + 1} label={label} step={steps.find((s) => s.node === node)}
                  active={isActive} rowRef={isActive ? activeRef : undefined} />
              );
            })}
          </ol>
        </>
      )}
    </Panel>
  );
}
