import type { Action, Approval, ProposedAction } from '@/api/types';

export type ProposedActionState = 'proposed' | 'auto_approved' | 'approved' | 'rejected' | 'executing' | 'executed' | 'verified' | 'failed';

export const PROPOSED_ACTION_STATE_LABELS: Record<ProposedActionState, string> = {
  proposed: 'Proposed',
  auto_approved: 'Auto-approved',
  approved: 'Approved',
  rejected: 'Rejected',
  executing: 'Executing',
  executed: 'Executed',
  verified: 'Verified',
  failed: 'Failed',
};

/**
 * Where a proposed action stands. The approval decision comes first: an action that needs approval cannot have
 * run while its approval is pending or after it was left out, whatever else the store holds.
 */
export function proposedActionState(a: ProposedAction, approval: Approval, executed: Action | undefined): ProposedActionState {
  if (a.requires_approval) {
    if (approval.status === 'pending') return 'proposed';
    const approved = approval.status === 'approved' || approval.approved_action_ids.includes(a.action_id);
    if (!approved) return 'rejected';
  }
  if (executed) {
    if (executed.status === 'failed' || executed.verification?.status === 'failed') return 'failed';
    if (executed.verification?.status === 'verified') return 'verified';
    return executed.status === 'executed' ? 'executed' : 'executing';
  }
  return a.requires_approval ? 'approved' : 'auto_approved';
}
