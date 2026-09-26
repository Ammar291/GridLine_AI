import type { NodeName } from '@/api/types';

// One source for node labels: the event feed (describeEvent) and the reasoning trace must agree.
export { NODE_LABELS } from '@/live/format';

/** Graph order of the agent's nodes; `replan` only runs after a failed verification. */
export const NODE_ORDER: readonly NodeName[] = [
  'observe', 'retrieve', 'assess', 'predict', 'cascade', 'recommend', 'approval_gate', 'execute', 'verify', 'replan',
];
