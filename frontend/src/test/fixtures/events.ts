// One typed fixture per event type in the contract: the backend's events, then the PENDING events of later milestones.
import type { AgentRun, EventOf, EventType, Severity } from '@/api/types';
import { cityFixture, worldFixture } from './city';
import { incidentFixture } from './incident';
import { decidedApprovalFixture, pendingApprovalFixture } from './approval';
import { executedActionFixture } from './action';

export const TS = '2026-09-26T10:31:04Z';
export const SIM = '2026-07-14T10:31:04Z';

function base<T extends EventType>(event_type: T, m: { location?: string | null; incident?: string | null; severity?: Severity; source?: string } = {}) {
  return {
    event_id: `evt-${event_type}`, timestamp: TS, sim_time: SIM, source: m.source ?? 'simulation:engine', location: m.location ?? null,
    severity: m.severity ?? 'info', incident_id: m.incident ?? null, event_type,
  };
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

const inc = { incident: 'inc_1', location: 'hillview', source: 'detector' } as const;

export const eventsFixture: { [K in EventType]: EventOf<K> } = {
  // ---- backend ----
  'sim.snapshot': {
    ...base('sim.snapshot'),
    payload: {
      status: { state: 'running', running: true, scenario: 'hillside_landslide', seed: 42, speed: 1, tick: 12, sim_time: SIM, stage: 'construction_and_rain' },
      world: worldFixture,
      city: cityFixture,
    },
  },
  'sim.status': {
    ...base('sim.status'),
    payload: { state: 'paused', running: false, scenario: 'hillside_landslide', seed: 42, speed: 2, tick: 13, sim_time: SIM, stage: 'intensifying_rain' },
  },
  'sim.tick': {
    ...base('sim.tick'),
    payload: { tick: 13, sim_time: SIM, scenario: 'hillside_landslide', stage: 'construction_and_rain', speed: 1, running: true },
  },
  'sim.heartbeat': { ...base('sim.heartbeat'), payload: { tick: 13, sim_time: SIM } },
  'scenario.stage': {
    ...base('scenario.stage', { source: 'scenario:hillside_landslide' }),
    payload: { scenario: 'hillside_landslide', stage_index: 2, stage: 'slope_creep', description: 'fixture: slope creep begins', tick: 96 },
  },
  'weather.observation': {
    ...base('weather.observation', { location: 'hillview', severity: 'high', source: 'sensor:RG-02' }),
    payload: {
      station_id: 'RG-02', rainfall_intensity_mm_h: 52.4, cumulative_rainfall_24h_mm: 120, temperature_c: null, wind_speed_kmh: null,
      wind_direction_deg: null,
    },
  },
  'weather.forecast': {
    ...base('weather.forecast', { source: 'scenario:hillside_landslide', severity: 'moderate' }),
    payload: {
      issued_sim_time: SIM, horizon_h: 24, expected_total_mm: 180, peak_intensity_mm_h: 40, confidence: 0.85, summary: 'fixture: heavy rain warning',
    },
  },
  'environment.soil': {
    ...base('environment.soil', { location: 'hillview', severity: 'moderate', source: 'sensor:SM-01' }),
    payload: { probe_id: 'SM-01', slope_id: 'sl_hv', soil_moisture_pct: 33.3, saturation: 0.74 },
  },
  'environment.river': {
    ...base('environment.river', { location: 'old_town', source: 'sensor:RV-01' }),
    payload: { gauge_id: 'RV-01', river_id: 'kalinadi', level_m: 3.42, flood_stage_m: 4.2, warning_level_m: 5, danger_level_m: 5.5, trend: 'rising' },
  },
  'environment.drainage': {
    ...base('environment.drainage', { location: 'riverside', severity: 'critical', source: 'sensor:CL-D7' }),
    payload: { gauge_id: 'CL-D7', channel_id: 'd7', flow_m3s: 10.2, capacity_m3s: 8.5, load_ratio: 1.2, blocked_fraction: 0, overflow_m3s: 1.7 },
  },
  'environment.slope': {
    ...base('environment.slope', { location: 'hillview', severity: 'moderate' }),
    payload: { slope_id: 'sl_hv', movement_rate_mm_h: 2.4, cumulative_movement_mm: 34, saturation: 0.8 },
  },
  'environment.water_accumulation': {
    ...base('environment.water_accumulation', { location: 'riverside', severity: 'moderate' }),
    payload: { zone_id: 'riverside', depth_cm: 12.5, trend: 'rising' },
  },
  'infrastructure.road': {
    ...base('infrastructure.road', { location: 'hillview', severity: 'high', source: 'operator:api' }),
    payload: { road_id: 'hill_road', status: 'blocked', reason: 'fixture: debris', is_evacuation_route: false },
  },
  'infrastructure.bridge': {
    ...base('infrastructure.bridge', { location: 'old_town', severity: 'high' }),
    payload: { bridge_id: 'br_1', status: 'closed', reason: 'fixture: river at danger level' },
  },
  'infrastructure.drainage_obstruction': {
    ...base('infrastructure.drainage_obstruction', { location: 'hillview', severity: 'high' }),
    payload: { channel_id: 'd7', blocked_fraction: 0.7, cause: 'fixture: landslide debris' },
  },
  'infrastructure.construction': {
    ...base('infrastructure.construction', { location: 'hillview' }),
    payload: { project_id: 'ht_phase2', status: 'halted', activity: 'halted', excavation_depth_m: 3.6, planned_depth_m: 6 },
  },
  'infrastructure.failure': {
    ...base('infrastructure.failure', { location: 'hillview', severity: 'critical', source: 'scenario:cascading_landslide_flood' }),
    payload: { asset_id: 'sl_hv', asset_kind: 'slope', failure_kind: 'landslide', description: 'fixture: slope failed above D-7' },
  },
  'emergency.rescue_team': {
    ...base('emergency.rescue_team', { location: 'riverside', severity: 'low' }),
    payload: { crew_id: 'c1', status: 'on_site', location_zone_id: 'riverside', task: 'fixture: evacuation support' },
  },
  'emergency.ambulance': {
    ...base('emergency.ambulance', { location: 'hillview' }),
    payload: { ambulance_id: 'a1', status: 'dispatched', location_zone_id: 'hillview', hospital_id: 'h1', available_count: 0, total_count: 2 },
  },
  'emergency.hospital': {
    ...base('emergency.hospital', { location: 'riverside', severity: 'moderate' }),
    payload: { hospital_id: 'h2', beds_total: 60, beds_occupied: 52, beds_available: 8, er_status: 'busy' },
  },
  'emergency.shelter': {
    ...base('emergency.shelter', { location: 'market_ward' }),
    payload: { shelter_id: 's1', status: 'open', capacity: 400, occupancy: 120 },
  },
  // ---- PENDING (later milestones) ----
  'zone.state': {
    ...base('zone.state', { location: 'hillview', severity: 'high', source: 'detector' }),
    payload: {
      zone_id: 'hillview', prev_band: 'watch', band: 'warning', saturation: 0.71, rain_24h_mm: 120, rain_intensity_mm_h: 84,
      landslide_index: 0.61, flood_index: 0.05, updated_sim_time: SIM,
    },
  },
  'threat.detected': {
    ...base('threat.detected', inc),
    payload: { incident_id: 'inc_1', zone_id: 'hillview', hazard: 'landslide', band: 'watch', prev_band: 'normal', index: 0.36 },
  },
  'threat.escalated': {
    ...base('threat.escalated', inc),
    payload: { incident_id: 'inc_1', zone_id: 'hillview', hazard: 'landslide', band: 'warning', prev_band: 'watch', index: 0.61 },
  },
  'incident.opened': { ...base('incident.opened', inc), payload: incidentFixture },
  'incident.closed': {
    ...base('incident.closed', inc),
    payload: { ...incidentFixture, status: 'closed', closed_at: '2026-09-26T11:00:00Z' },
  },
  'agent.run.started': { ...base('agent.run.started', inc), payload: run2 },
  'agent.run.finished': {
    ...base('agent.run.finished', inc),
    payload: { ...run2, status: 'finished', finished_at: '2026-09-26T10:32:00Z' },
  },
  'agent.node.started': {
    ...base('agent.node.started', inc),
    payload: { run_id: 'run_2', incident_id: 'inc_1', node: 'assess', step_id: 'step_r2_assess' },
  },
  'agent.node.finished': {
    ...base('agent.node.finished', inc),
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
  'approval.requested': { ...base('approval.requested', inc), payload: pendingApprovalFixture },
  'approval.decided': { ...base('approval.decided', inc), payload: decidedApprovalFixture },
  'action.executed': { ...base('action.executed', inc), payload: executedActionFixture },
  'action.verified': {
    ...base('action.verified', inc),
    payload: {
      action_id: 'act_2',
      verification: { status: 'verified', expected: 'fixture: crew at hillview', observed: 'fixture: crew at hillview', failures: [], checked_sim_time: SIM },
    },
  },
  'replan.triggered': {
    ...base('replan.triggered', inc),
    payload: { incident_id: 'inc_1', run_id: 'run_1', reason: 'fixture: crew route blocked' },
  },
  'alert.issued': {
    ...base('alert.issued', { ...inc, location: 'riverside' }),
    payload: { id: 'alert_1', zone_id: 'riverside', level: 'warning', message: 'fixture: alert message', issued_at: TS, issued_sim_time: SIM },
  },
};

export const snapshotEventFixture: EventOf<'sim.snapshot'> = eventsFixture['sim.snapshot'];
