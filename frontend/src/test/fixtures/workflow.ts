// A live agent workflow run in the backend's agent.step shapes: one completed step per node, plus variants.
import type { WorkflowOutput, WorkflowRun, WorkflowStep } from '@/api/types';

export const RUN_ID = 'run_wf_1';
const T0 = '2026-09-26T10:31:04Z';
const T1 = '2026-09-26T10:31:05Z';

const OUTPUTS: WorkflowOutput[] = [
  {
    node: 'receive', event_id: 'evt_fail_1', hazard: 'landslide', failure_kind: 'landslide',
    asset: { table: 'slopes', id: 'SL-HV-1', name: 'Hillview upper slope' }, zone_id: 'Z-HV', zone_name: 'Hillview',
    description: 'fixture: slope failed above D-7', sim_time: '2026-07-14T10:31:04Z', citation_id: 'event:evt_fail_1',
  },
  {
    node: 'observe', headline: 'fixture: 3 critical signals around Hillview',
    signals: [
      { id: 'event:evt_rain', event_type: 'weather.observation', source: 'sensor:rg1', zone_id: 'Z-HV', severity: 'critical', summary: 'fixture: 84 mm/h rain' },
    ],
  },
  {
    node: 'query_graph', start: { table: 'slopes', id: 'SL-HV-1', name: 'Hillview upper slope' }, entity_count: 4, edge_count: 3,
    paths: [{
      nodes: [
        { table: 'projects', id: 'PR-HT2', name: 'Hillview Terrace Phase 2' },
        { table: 'slopes', id: 'SL-HV-1', name: 'Hillview upper slope' },
        { table: 'channels', id: 'D-7', name: 'Drain 7' },
        { table: 'zones', id: 'Z-RS', name: 'Riverside' },
      ],
      relations: ['on', 'blocks', 'drains_into'],
      citation_ids: ['kg:e1', 'kg:e2', 'kg:e3'],
    }],
  },
  {
    node: 'retrieve', queries: ['landslide response'],
    chunks: [{ chunk_id: 'dmp-4.2', document_id: 'dmp', document_title: 'Disaster Management Policy', section: '4.2 Slope failure', kind: 'policy', similarity: 0.83 }],
  },
  {
    node: 'reason', provider: 'ollama', model: 'llama3.1:8b', fallback_reason: null, duration_ms: 4200,
    summary: 'fixture: debris will block D-7 and flood Riverside',
    claims: [{ text: 'fixture: D-7 is blocked by debris', citation_ids: ['kg:e2', 'dmp-4.2'] }],
  },
  {
    node: 'assess', hazard: 'landslide', band: 'critical', confidence: 0.87, grounded: true, cited_count: 5, ungrounded_ids: [],
    affected_zone_ids: ['Z-HV', 'Z-RS'],
  },
  {
    node: 'recommend', provider: 'ollama', model: 'llama3.1:8b', fallback_reason: null, duration_ms: 3100, candidate_count: 4,
    actions: [{
      action_id: 'wa_1', candidate_id: 'cand_1', tool: 'halt_construction', input: { project_id: 'PR-HT2' },
      label: 'Halt Hillview Terrace Phase 2', rationale: 'fixture: excavation destabilises the slope', citation_ids: ['dmp-4.2'],
      requires_approval: true,
    }],
  },
  { node: 'approval_gate', approval_id: 'wap_1', action_ids: ['wa_1'], decision: 'approve', note: null, decided_at: T1 },
  {
    node: 'execute',
    results: [{ action_id: 'wa_1', tool: 'halt_construction', status: 'executed', message: 'fixture: PR-HT2 halted', affected_entities: ['PR-HT2'] }],
  },
  {
    node: 'verify', status: 'verified',
    per_action: [{
      action_id: 'wa_1', tool: 'halt_construction', status: 'verified',
      checks: [{ name: 'project status', passed: true, expected: 'halted', observed: 'halted' }],
    }],
  },
  {
    node: 'complete', outcome: 'completed',
    entities: [{ kind: 'project', id: 'PR-HT2', name: 'Hillview Terrace Phase 2', fields: { status: 'halted' } }],
  },
];

/** Every node done, in order. */
export const doneSteps: WorkflowStep[] = OUTPUTS.map((output, i) => ({
  run_id: RUN_ID, node: output.node, index: i + 1, status: 'done', started_at: T0, finished_at: T1, duration_ms: 1000, output, error: null,
}));

export function stepOf(node: WorkflowStep['node'], over: Partial<WorkflowStep> = {}): WorkflowStep {
  const found = doneSteps.find((s) => s.node === node);
  if (!found) throw new Error(`no fixture step ${node}`);
  return { ...found, ...over };
}

/** The run paused at the approval gate: receive … recommend done, the gate waiting with no decision. */
export const waitingSteps: WorkflowStep[] = [
  ...doneSteps.slice(0, 7),
  stepOf('approval_gate', {
    status: 'waiting', finished_at: null, duration_ms: null,
    output: { node: 'approval_gate', approval_id: 'wap_1', action_ids: ['wa_1'], decision: null, note: null, decided_at: null },
  }),
];

export const workflowRunFixture: WorkflowRun = {
  run_id: RUN_ID, trigger_event_id: 'evt_fail_1', hazard: 'landslide', zone_id: 'Z-HV', asset_id: 'SL-HV-1', provider: 'ollama',
  model: 'llama3.1:8b', started_at: T0, steps: waitingSteps,
};
