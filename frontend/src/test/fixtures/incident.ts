// Typed test fixture. All free text is visibly synthetic ("fixture: ..."); it is not plausible reasoning.
import type { AgentRun, AgentStep, Citation, Incident, NodeName, ProposedAction, StepOutput } from '@/api/types';

export const chunkCitation: Citation = { id: 'dmp-2024#s4.2', kind: 'chunk', label: 'Disaster Management Policy §4.2' };
export const sensorCitation: Citation = { id: 'sensor:RG-02@2026-07-14T10:30:00', kind: 'sensor', label: 'RG-02 rain gauge' };

export const proposedActionsFixture: ProposedAction[] = [
  {
    action_id: 'act_1',
    tool: 'halt_construction',
    input: { project_id: 'ht_phase2' },
    rationale: 'fixture: rationale one',
    expected_effect: 'fixture: effect one',
    citation_ids: ['dmp-2024#s4.2'],
    requires_approval: true,
  },
  {
    action_id: 'act_2',
    tool: 'dispatch_crew',
    input: { crew_id: 'c3', zone_id: 'hillview', task: 'fixture: slope watch' },
    rationale: 'fixture: rationale two',
    expected_effect: 'fixture: effect two',
    citation_ids: ['sensor:RG-02@2026-07-14T10:30:00'],
    requires_approval: true,
  },
  {
    action_id: 'act_3',
    tool: 'schedule_inspection',
    input: { asset_id: 'd7', priority: 'high' },
    rationale: 'fixture: rationale three',
    expected_effect: 'fixture: effect three',
    citation_ids: ['dmp-2024#s4.2'],
    requires_approval: false,
  },
];

const outputs: Record<NodeName, StepOutput> = {
  observe: {
    node: 'observe',
    zone_id: 'hillview',
    sim_time: '2026-07-14T10:30:00',
    readings: { rain_intensity_mm_h: 84, rain_24h_mm: 120, saturation: 0.71, landslide_index: 0.61, flood_index: 0.05, band: 'warning' },
    project: { id: 'ht_phase2', name: 'Hillview Terrace Phase 2', status: 'active', excavation_depth_m: 3.5, planned_depth_m: 6 },
    channel: { id: 'd7', name: 'D-7 Kalinadi drain', current_capacity_m3s: 8.5, design_capacity_m3s: 12, blocked_fraction: 0 },
    crews: [{ id: 'c3', name: 'Rescue Team 03', status: 'available', location_zone_id: 'market_ward' }],
    open_roads: ['hill_road', 'riverside_bypass', 'b04'],
    closed_roads: [],
    downstream_zone_ids: ['riverside'],
  },
  retrieve: {
    node: 'retrieve',
    chunks: [
      { chunk_id: 'dmp-2024#s4.2', document_id: 'dmp-2024', document_title: 'Disaster Management Policy', section_id: 's4.2', section: 'Rainfall thresholds', kind: 'policy', similarity: 0.82 },
      { chunk_id: 'permit-ht-2026-014#s3', document_id: 'permit-ht-2026-014', document_title: 'Hillview Terrace permit', section_id: 's3', section: 'Conditions', kind: 'permit', similarity: 0.74 },
    ],
  },
  assess: {
    node: 'assess',
    hazard: 'landslide',
    summary: 'fixture: assessment summary',
    contributing_factors: [
      { factor: 'fixture: factor one', value: 'fixture: 0.71', citation_ids: ['sensor:RG-02@2026-07-14T10:30:00'] },
      { factor: 'fixture: factor two', value: 'fixture: 3.5 m', citation_ids: ['dmp-2024#s4.2'] },
    ],
    confidence: 0.72,
    claims: [
      { text: 'fixture: claim one', citation_ids: ['dmp-2024#s4.2'] },
      { text: 'fixture: claim two', citation_ids: ['sensor:RG-02@2026-07-14T10:30:00'] },
    ],
  },
  predict: {
    node: 'predict',
    probability_band: 'high',
    time_horizon: 'fixture: 6 to 12 hours',
    onset_sim_time: '2026-07-14T18:00:00',
    what_would_change_it: ['fixture: rain stops'],
    claims: [{ text: 'fixture: prediction claim', citation_ids: ['dmp-2024#s4.2'] }],
  },
  cascade: {
    node: 'cascade',
    chain: [{ cause: 'fixture: hillview slope failure', effect: 'fixture: d7 blocked, riverside floods', affected_asset_ids: ['d7'], citation_ids: ['dmp-2024#s4.2'] }],
    affected_zone_ids: ['riverside'],
    claims: [{ text: 'fixture: cascade claim', citation_ids: ['dmp-2024#s4.2'] }],
  },
  recommend: { node: 'recommend', actions: proposedActionsFixture },
  approval_gate: { node: 'approval_gate', approval_id: 'appr_1', auto_approved_action_ids: ['act_3'], pending_action_ids: ['act_1', 'act_2'] },
  execute: { node: 'execute', action_ids: ['act_3'] },
  verify: {
    node: 'verify',
    status: 'verified',
    per_action: [{ action_id: 'act_3', status: 'verified', expected: 'fixture: inspection scheduled', observed: 'fixture: inspection scheduled', failures: [] }],
  },
  replan: { node: 'replan', reason: 'fixture: none' },
};

const NODES: NodeName[] = ['observe', 'retrieve', 'assess', 'predict', 'cascade', 'recommend', 'approval_gate', 'execute', 'verify', 'replan'];

const steps: AgentStep[] = NODES.map((node, i) => ({
  id: `step_${node}`,
  run_id: 'run_1',
  node,
  status: 'finished',
  started_at: `2026-09-26T10:31:${String(10 + i * 2).padStart(2, '0')}Z`,
  finished_at: `2026-09-26T10:31:${String(11 + i * 2).padStart(2, '0')}Z`,
  duration_ms: 900,
  output: outputs[node],
  citations: node === 'assess' ? [chunkCitation, sensorCitation] : [],
}));

export const incidentFixture: Incident = {
  id: 'inc_1',
  zone_id: 'hillview',
  hazard: 'landslide',
  band: 'warning',
  status: 'open',
  opened_at: '2026-09-26T10:31:00Z',
  opened_sim_time: '2026-07-14T10:30:00',
  closed_at: null,
  runs: [
    {
      id: 'run_1',
      incident_id: 'inc_1',
      thread_id: 'inc_1',
      trigger: 'band_change',
      replan_reason: null,
      status: 'finished',
      started_at: '2026-09-26T10:31:05Z',
      finished_at: '2026-09-26T10:31:40Z',
      steps,
    },
  ],
  approvals: [],
  actions: [],
};

// eslint-disable-next-line @typescript-eslint/no-non-null-assertion -- fixture is statically non-empty
export const runFixture: AgentRun = incidentFixture.runs[0]!;
// eslint-disable-next-line @typescript-eslint/no-non-null-assertion -- fixture is statically non-empty
export const assessStepFixture: AgentStep = runFixture.steps.find((s) => s.node === 'assess')!;
