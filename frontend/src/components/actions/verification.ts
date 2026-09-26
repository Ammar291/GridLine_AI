import type { Action } from '@/api/types';
import type { Milestone } from '@/live/types';

export type VerificationState = 'verified' | 'partially_verified' | 'failed' | 'pending' | 'replanning';

/**
 * A verified action stays verified. Otherwise a re-plan of the action's run takes precedence, then the
 * verification result, then an execution failure; anything not yet checked is pending.
 */
export function verificationState(action: Action, replanRunIds: ReadonlySet<string>): VerificationState {
  const status = action.verification?.status;
  if (status === 'verified') return 'verified';
  if (replanRunIds.has(action.run_id)) return 'replanning';
  if (status === 'failed' || action.status === 'failed') return 'failed';
  if (status === 'partially_verified') return 'partially_verified';
  return 'pending';
}

/** Runs named by replan.triggered events (kept as replan milestones in the live store). */
export function replanRunIds(milestones: readonly Milestone[]): Set<string> {
  const ids = new Set<string>();
  for (const m of milestones) if (m.kind === 'replan' && m.runId !== undefined) ids.add(m.runId);
  return ids;
}

/** Whole sim minutes from one sim time to another; null when either is missing or the order is reversed. */
export function simMinutesBetween(from: string | null | undefined, to: string | null): number | null {
  if (!from || !to) return null;
  const ms = Date.parse(to) - Date.parse(from);
  return Number.isFinite(ms) && ms >= 0 ? Math.floor(ms / 60_000) : null;
}
