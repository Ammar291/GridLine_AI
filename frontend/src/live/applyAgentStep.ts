// The live agent workflow: agent.step upserts one node of one run; sim.snapshot's agent_run seeds it on connect.
import type { WorkflowNode, WorkflowOutput, WorkflowRun, WorkflowStep } from '@/api/types';
import type { AgentRunState } from './types';

export type RunStatus = 'running' | 'waiting' | 'completed' | 'rejected' | 'failed';

const byIndex = (a: WorkflowStep, b: WorkflowStep) => a.index - b.index;

/** Upsert the step by node; a step of another run starts a fresh run. Steps stay sorted by index. */
export function applyAgentStep(run: AgentRunState | null, step: WorkflowStep): AgentRunState {
  const kept = run !== null && run.runId === step.run_id ? run.steps.filter((s) => s.node !== step.node) : [];
  return { runId: step.run_id, steps: [...kept, step].sort(byIndex) };
}

/** The snapshot's run (null or absent means no run). */
export function agentRunFromSnapshot(run: WorkflowRun | null | undefined): AgentRunState | null {
  return run ? { runId: run.run_id, steps: [...run.steps].sort(byIndex) } : null;
}

/** Mirrors the backend's run_status(): derived from the steps, never stored. */
export function runStatus(steps: readonly WorkflowStep[]): RunStatus {
  if (steps.some((s) => s.status === 'failed')) return 'failed';
  if (steps.some((s) => s.node === 'approval_gate' && s.status === 'waiting')) return 'waiting';
  const done = steps.find((s) => s.node === 'complete');
  if (done?.status === 'done' && done.output?.node === 'complete') return done.output.outcome === 'rejected' ? 'rejected' : 'completed';
  return 'running';
}

/** The typed output of one node, when that node has reported one. */
export function outputOf<N extends WorkflowNode>(
  steps: readonly WorkflowStep[], node: N,
): Extract<WorkflowOutput, { node: N }> | undefined {
  const out = steps.find((s) => s.node === node)?.output;
  return out?.node === node ? (out as Extract<WorkflowOutput, { node: N }>) : undefined;
}
