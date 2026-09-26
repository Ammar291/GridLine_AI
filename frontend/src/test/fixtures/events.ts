import type { AgentRun, Event, EventOf } from '@/api/types';
import { cityFixture } from './city';
import { incidentFixture } from './incident';
import { decidedApprovalFixture, pendingApprovalFixture } from './approval';
import { executedActionFixture } from './action';

const TS = '2026-09-26T10:31:04Z';
const SIM = '2026-07-14T10:31:04';

function base<T extends Event['type']>(type: T, incident_id: string | null = null) {
  return { id: `evt_${type}`, ts: TS, sim_time: SIM, incident_id, type };
}

const run2: AgentRun = {
  id: 'run_2',
  incident_id: 'inc_1',
  thread_id: 'inc_1',
  trigger: 'band_change',
  replan_reason: null,
  status: 'running',
  started_at: TS,
  finished_at: null,
  steps: [],
};

export const eventsFixture: { [K in Event['type']]: EventOf<K> } = {
  'state.snapshot': {
    ...base('state.snapshot'),
    payload: {
      city: cityFixture,
      sim: { scenario: 'hillside_landslide', running: true, speed: 1, sim_time: SIM, tick: 12 },
      llm: { provider: 'mock', model: null },
      incidents: [incidentFixture],
      approvals: [pendingApprovalFixture],
      actions: [executedActionFixture],
      alerts: [],
    },
  },
  'sim.tick': { ...base('sim.tick'), payload: { sim_time: SIM, tick: 13, running: true, speed: 1 } },
  'sensor.reading': {
    ...base('sensor.reading'),
    payload: { sensor_id: 'RG-02', kind: 'rain', zone_id: 'hillview', value: 84, unit: 'mm/h' },
  },
  'zone.state': {
    ...base('zone.state'),
    payload: {
      zone_id: 'hillview',
      prev_band: 'watch',
      band: 'warning',
      saturation: 0.71,
      rain_24h_mm: 120,
      rain_intensity_mm_h: 84,
      landslide_index: 0.61,
      flood_index: 0.05,
      updated_sim_time: SIM,
    },
  },
  'threat.detected': {
    ...base('threat.detected', 'inc_1'),
    payload: { incident_id: 'inc_1', zone_id: 'hillview', hazard: 'landslide', band: 'watch', prev_band: 'normal', index: 0.36 },
  },
  'threat.escalated': {
    ...base('threat.escalated', 'inc_1'),
    payload: { incident_id: 'inc_1', zone_id: 'hillview', hazard: 'landslide', band: 'warning', prev_band: 'watch', index: 0.61 },
  },
  'incident.opened': { ...base('incident.opened', 'inc_1'), payload: incidentFixture },
  'incident.closed': {
    ...base('incident.closed', 'inc_1'),
    payload: { ...incidentFixture, status: 'closed', closed_at: '2026-09-26T11:00:00Z' },
  },
  'agent.run.started': { ...base('agent.run.started', 'inc_1'), payload: run2 },
  'agent.run.finished': {
    ...base('agent.run.finished', 'inc_1'),
    payload: { ...run2, status: 'finished', finished_at: '2026-09-26T10:32:00Z' },
  },
  'agent.node.started': {
    ...base('agent.node.started', 'inc_1'),
    payload: { run_id: 'run_2', incident_id: 'inc_1', node: 'assess', step_id: 'step_r2_assess' },
  },
  'agent.node.finished': {
    ...base('agent.node.finished', 'inc_1'),
    payload: {
      id: 'step_r2_assess',
      run_id: 'run_2',
      node: 'assess',
      status: 'finished',
      started_at: TS,
      finished_at: '2026-09-26T10:31:06Z',
      duration_ms: 2000,
      output: {
        node: 'assess',
        hazard: 'landslide',
        summary: 'fixture: second assessment summary',
        contributing_factors: [],
        confidence: 0.8,
        claims: [],
      },
      citations: [],
    },
  },
  'approval.requested': { ...base('approval.requested', 'inc_1'), payload: pendingApprovalFixture },
  'approval.decided': { ...base('approval.decided', 'inc_1'), payload: decidedApprovalFixture },
  'action.executed': { ...base('action.executed', 'inc_1'), payload: executedActionFixture },
  'action.verified': {
    ...base('action.verified', 'inc_1'),
    payload: {
      action_id: 'act_2',
      verification: { status: 'verified', expected: 'fixture: crew at hillview', observed: 'fixture: crew at hillview', failures: [], checked_sim_time: SIM },
    },
  },
  'replan.triggered': {
    ...base('replan.triggered', 'inc_1'),
    payload: { incident_id: 'inc_1', run_id: 'run_1', reason: 'fixture: crew route blocked' },
  },
  'alert.issued': {
    ...base('alert.issued', 'inc_1'),
    payload: { id: 'alert_1', zone_id: 'riverside', level: 'warning', message: 'fixture: alert message', issued_at: TS, issued_sim_time: SIM },
  },
  'scenario.event': {
    ...base('scenario.event'),
    payload: { name: 'excavation_depth', description: 'fixture: excavation reaches 4.5 m' },
  },
};

export const snapshotEventFixture: EventOf<'state.snapshot'> = eventsFixture['state.snapshot'];
