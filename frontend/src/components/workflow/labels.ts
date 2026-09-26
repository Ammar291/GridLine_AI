import type { WorkflowNode } from '@/api/types';

/** The eleven graph nodes in run order, with the dashboard's step names. */
export const WORKFLOW_STEPS: readonly { node: WorkflowNode; label: string }[] = [
  { node: 'receive', label: 'EVENT RECEIVED' },
  { node: 'observe', label: 'SITUATION ANALYSIS' },
  { node: 'query_graph', label: 'KNOWLEDGE GRAPH QUERY' },
  { node: 'retrieve', label: 'RAG EVIDENCE RETRIEVED' },
  { node: 'reason', label: 'AI REASONING' },
  { node: 'assess', label: 'THREAT ASSESSMENT' },
  { node: 'recommend', label: 'ACTION PLAN' },
  { node: 'approval_gate', label: 'WAITING FOR HUMAN APPROVAL' },
  { node: 'execute', label: 'EXECUTING ACTIONS' },
  { node: 'verify', label: 'VERIFYING' },
  { node: 'complete', label: 'COMPLETED' },
];

export const WORKFLOW_LABELS = Object.fromEntries(WORKFLOW_STEPS.map((s) => [s.node, s.label])) as Record<WorkflowNode, string>;

/** 'THREAT ASSESSMENT' → 'Threat assessment', for sentences. */
export function sentenceLabel(node: WorkflowNode): string {
  const lower = WORKFLOW_LABELS[node].toLowerCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

/** '840 ms' under a second, '4.2 s' above. */
export function fmtMs(ms: number): string {
  return ms < 1000 ? `${String(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;
}
