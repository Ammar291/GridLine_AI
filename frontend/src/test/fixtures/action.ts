import type { Action } from '@/api/types';

export const executedActionFixture: Action = {
  id: 'act_2',
  run_id: 'run_1',
  incident_id: 'inc_1',
  tool: 'dispatch_crew',
  input: { crew_id: 'c3', zone_id: 'hillview', task: 'fixture: slope watch' },
  status: 'executed',
  executed_at: '2026-09-26T10:32:10Z',
  executed_sim_time: '2026-07-14T10:40:00',
  state_changes: [{ entity_type: 'crew', entity_id: 'c3', entity_name: 'Rescue Team 03', field: 'status', from: 'available', to: 'dispatched' }],
  verification: {
    status: 'verified',
    expected: 'fixture: crew at hillview',
    observed: 'fixture: crew at hillview',
    failures: [],
    checked_sim_time: '2026-07-14T10:50:00',
  },
};

export const failedActionFixture: Action = {
  id: 'act_5',
  run_id: 'run_1',
  incident_id: 'inc_1',
  tool: 'close_road',
  input: { road_id: 'b04' },
  status: 'executed',
  executed_at: '2026-09-26T10:33:00Z',
  executed_sim_time: '2026-07-14T10:45:00',
  state_changes: [{ entity_type: 'road', entity_id: 'b04', entity_name: 'Kalinadi Bridge B-04', field: 'status', from: 'open', to: 'closed' }],
  verification: {
    status: 'failed',
    expected: 'fixture: road closed and crew rerouted',
    observed: 'fixture: road closed, crew route blocked',
    failures: ['fixture: crew C-2 route blocked'],
    checked_sim_time: '2026-07-14T10:55:00',
  },
};

export const pendingActionFixture: Action = {
  ...executedActionFixture,
  id: 'act_6',
  verification: { status: 'pending', expected: 'fixture: crew at hillview', observed: '', failures: [], checked_sim_time: null },
};
