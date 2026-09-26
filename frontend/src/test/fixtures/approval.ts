import type { Approval } from '@/api/types';
import { proposedActionsFixture } from './incident';

const [act1, act2] = proposedActionsFixture;
if (!act1 || !act2) throw new Error('fixture: proposed actions missing');

export const pendingApprovalFixture: Approval = {
  id: 'appr_1',
  run_id: 'run_1',
  incident_id: 'inc_1',
  proposed_actions: [
    act1,
    act2,
    {
      action_id: 'act_4',
      tool: 'open_shelter',
      input: { shelter_id: 's1' },
      rationale: 'fixture: rationale four',
      expected_effect: 'fixture: effect four',
      citation_ids: ['dmp-2024#s4.2'],
      requires_approval: true,
    },
  ],
  status: 'pending',
  requested_at: '2026-09-26T10:31:30Z',
  decided_at: null,
  decided_by: null,
  note: null,
  approved_action_ids: [],
  synthetic: false,
};

export const decidedApprovalFixture: Approval = {
  ...pendingApprovalFixture,
  status: 'partial',
  decided_at: '2026-09-26T10:32:00Z',
  decided_by: 'operator',
  note: 'fixture: note',
  approved_action_ids: ['act_1'],
};
