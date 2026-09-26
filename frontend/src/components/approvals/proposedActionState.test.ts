import { describe, expect, it } from 'vitest';
import type { ProposedAction } from '@/api/types';
import { executedActionFixture, failedActionFixture } from '@/test/fixtures/action';
import { decidedApprovalFixture, pendingApprovalFixture } from '@/test/fixtures/approval';
import { proposedActionsFixture } from '@/test/fixtures/incident';
import { proposedActionState } from './proposedActionState';

const [halt, dispatch, inspect] = proposedActionsFixture as [ProposedAction, ProposedAction, ProposedAction];
const approvedAll = { ...pendingApprovalFixture, status: 'approved' as const, approved_action_ids: ['act_1', 'act_2', 'act_4'] };

describe('proposedActionState', () => {
  it('is proposed while the approval is pending, even if the store holds an action with the same id', () => {
    expect(proposedActionState(dispatch, pendingApprovalFixture, executedActionFixture)).toBe('proposed');
  });
  it('follows the decision for actions that need approval', () => {
    expect(proposedActionState(halt, decidedApprovalFixture, undefined)).toBe('approved');
    expect(proposedActionState(dispatch, decidedApprovalFixture, executedActionFixture)).toBe('rejected');
  });
  it('follows execution and verification once approved', () => {
    expect(proposedActionState(dispatch, approvedAll, { ...executedActionFixture, status: 'executing', verification: null })).toBe('executing');
    expect(proposedActionState(dispatch, approvedAll, { ...executedActionFixture, verification: null })).toBe('executed');
    expect(proposedActionState(dispatch, approvedAll, executedActionFixture)).toBe('verified');
    expect(proposedActionState(dispatch, approvedAll, { ...failedActionFixture, id: 'act_2' })).toBe('failed');
  });
  it('actions that need no approval are auto-approved until they run', () => {
    expect(proposedActionState(inspect, pendingApprovalFixture, undefined)).toBe('auto_approved');
    expect(proposedActionState(inspect, pendingApprovalFixture, { ...executedActionFixture, id: 'act_3' })).toBe('verified');
  });
});
