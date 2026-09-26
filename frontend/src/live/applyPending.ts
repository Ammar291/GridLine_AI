// PENDING events (openapi.pending.yaml): threat detector, incidents and agent, approvals and actions, alerts.
// The backend does not emit these yet; mock mode replays the detector's. Pure; one case per event type.
import type {
  Action, AgentRun, AgentStep, Approval, BridgeState, CrewState, EventOf, Incident, ProjectState, RoadState, ShelterState,
  WorldSnapshot,
} from '@/api/types';
import { bandLabel } from '@/components/ui/bandLabel';
import { addMilestone, patch, upsertById, upsertPoint, zoneName } from './reduce';
import type { LiveState } from './types';

export type PendingEvent = EventOf<
  | 'zone.state' | 'threat.detected' | 'threat.escalated' | 'incident.opened' | 'incident.closed' | 'agent.run.started'
  | 'agent.run.finished' | 'agent.node.started' | 'agent.node.finished' | 'approval.requested' | 'approval.decided'
  | 'action.executed' | 'action.verified' | 'replan.triggered' | 'alert.issued'
>;

function applyZoneState(state: LiveState, event: EventOf<'zone.state'>): LiveState {
  const { zone_id: zoneId, prev_band: prevBand, ...zs } = event.payload;
  const withState = { ...state, zoneState: { ...state.zoneState, [zoneId]: zs } };
  const next = upsertPoint(withState, zoneId, event.sim_time, () => ({
    rain: zs.rain_intensity_mm_h, saturation: zs.saturation, landslide: zs.landslide_index, flood: zs.flood_index, band: zs.band,
  }));
  if (prevBand == null || prevBand === zs.band) return next;
  return addMilestone(next, event, { kind: 'band', label: `${zoneName(state.city, zoneId)}: ${bandLabel(zs.band)}`, zoneId, band: zs.band });
}

function applyThreat(state: LiveState, event: EventOf<'threat.detected'> | EventOf<'threat.escalated'>): LiveState {
  const p = event.payload;
  const incident = state.incidents[p.incident_id];
  const next =
    event.event_type === 'threat.escalated' && incident?.zone_id === p.zone_id
      ? { ...state, incidents: { ...state.incidents, [incident.id]: { ...incident, band: p.band } } }
      : state;
  const verb = event.event_type === 'threat.detected' ? 'Threat detected' : 'Threat escalated';
  return addMilestone(next, event, {
    kind: 'band', label: `${verb}: ${p.hazard} in ${zoneName(state.city, p.zone_id)} (${bandLabel(p.band)})`,
    zoneId: p.zone_id, incidentId: p.incident_id, band: p.band,
  });
}

function applyIncident(state: LiveState, event: EventOf<'incident.opened'> | EventOf<'incident.closed'>): LiveState {
  const p = event.payload;
  const prev = state.incidents[p.id];
  const merged: Incident = {
    ...p,
    runs: p.runs.length > 0 ? p.runs : (prev?.runs ?? []),
    approvals: p.approvals.length > 0 ? p.approvals : (prev?.approvals ?? []),
    actions: p.actions.length > 0 ? p.actions : (prev?.actions ?? []),
  };
  const verb = event.event_type === 'incident.opened' ? 'Incident opened' : 'Incident closed';
  return addMilestone({ ...state, incidents: { ...state.incidents, [p.id]: merged } }, event, {
    kind: 'incident', label: `${verb}: ${p.hazard} in ${zoneName(state.city, p.zone_id)}`, zoneId: p.zone_id, incidentId: p.id, band: p.band,
  });
}

function withIncident(state: LiveState, incidentId: string | null | undefined, f: (i: Incident) => Incident): LiveState {
  const incident = incidentId == null ? undefined : state.incidents[incidentId];
  if (!incident) return state;
  return { ...state, incidents: { ...state.incidents, [incident.id]: f(incident) } };
}

function upsertRun(state: LiveState, run: AgentRun): LiveState {
  return withIncident(state, run.incident_id, (i) => {
    const prev = i.runs.find((r) => r.id === run.id);
    const merged = { ...run, steps: run.steps.length > 0 ? run.steps : (prev?.steps ?? []) };
    return { ...i, runs: upsertById(i.runs, merged) };
  });
}

function findIncidentForRun(state: LiveState, runId: string, hinted: string | null | undefined): string | null {
  if (hinted != null && hinted in state.incidents) return hinted;
  const owner = Object.values(state.incidents).find((i) => i.runs.some((r) => r.id === runId));
  if (owner) return owner.id;
  const open = Object.values(state.incidents).filter((i) => i.status === 'open');
  return open.length === 1 && open[0] ? open[0].id : null;
}

function upsertStep(state: LiveState, hintedIncidentId: string | null | undefined, step: AgentStep, ts: string): LiveState {
  const incidentId = findIncidentForRun(state, step.run_id, hintedIncidentId);
  return withIncident(state, incidentId, (i) => {
    const run: AgentRun = i.runs.find((r) => r.id === step.run_id) ?? {
      id: step.run_id, incident_id: i.id, thread_id: i.id, trigger: 'unknown', status: 'running', started_at: ts, steps: [],
    };
    return { ...i, runs: upsertById(i.runs, { ...run, steps: upsertById(run.steps, step) }) };
  });
}

function upsertApproval(state: LiveState, event: EventOf<'approval.requested'> | EventOf<'approval.decided'>): LiveState {
  const a: Approval = event.payload;
  const next = withIncident({ ...state, approvals: { ...state.approvals, [a.id]: a } }, a.incident_id, (i) => ({
    ...i, approvals: upsertById(i.approvals, a),
  }));
  const label = event.event_type === 'approval.requested' ? 'Approval requested' : `Approval ${a.status}`;
  return addMilestone(next, event, { kind: 'approval', label, incidentId: a.incident_id });
}

/** Status changes an executed action reports are applied to the live world (other fields arrive as their own events). */
function applyStateChanges(world: WorldSnapshot, action: Action): WorldSnapshot {
  let w = world;
  for (const c of action.state_changes) {
    if (c.field !== 'status') continue;
    // The contract types `to` as a string; the world's status enums are narrower, so the value is taken as sent.
    switch (c.entity_type) {
      case 'crew': w = { ...w, crews: patch(w.crews, c.entity_id, { status: c.to as CrewState['status'] }) }; break;
      case 'shelter': w = { ...w, shelters: patch(w.shelters, c.entity_id, { status: c.to as ShelterState['status'] }) }; break;
      case 'road': w = { ...w, roads: patch(w.roads, c.entity_id, { status: c.to as RoadState['status'] }) }; break;
      case 'bridge': w = { ...w, bridges: patch(w.bridges, c.entity_id, { status: c.to as BridgeState['status'] }) }; break;
      case 'project': w = { ...w, projects: patch(w.projects, c.entity_id, { status: c.to as ProjectState['status'] }) }; break;
      default: break; // channel, pump unit and alert changes carry no live status here
    }
  }
  return w;
}

function upsertAction(state: LiveState, a: Action): LiveState {
  return withIncident({ ...state, actions: { ...state.actions, [a.id]: a } }, a.incident_id, (i) => ({ ...i, actions: upsertById(i.actions, a) }));
}

export function applyPendingEvent(state: LiveState, event: PendingEvent): LiveState {
  switch (event.event_type) {
    case 'zone.state':
      return applyZoneState(state, event);
    case 'threat.detected':
    case 'threat.escalated':
      return applyThreat(state, event);
    case 'incident.opened':
    case 'incident.closed':
      return applyIncident(state, event);
    case 'agent.run.started':
    case 'agent.run.finished':
      return upsertRun(state, event.payload);
    case 'agent.node.started': {
      const p = event.payload;
      const step: AgentStep = { id: p.step_id, run_id: p.run_id, node: p.node, status: 'running', started_at: event.timestamp, output: null, citations: [] };
      return upsertStep(state, p.incident_id, step, event.timestamp);
    }
    case 'agent.node.finished':
      return upsertStep(state, event.incident_id, event.payload, event.timestamp);
    case 'approval.requested':
    case 'approval.decided':
      return upsertApproval(state, event);
    case 'action.executed': {
      const a = event.payload;
      const world = state.world ? applyStateChanges(state.world, a) : null;
      const next = upsertAction({ ...state, world }, a);
      return addMilestone(next, event, { kind: 'action', label: `${a.tool} executed`, incidentId: a.incident_id });
    }
    case 'action.verified': {
      const { action_id: actionId, verification } = event.payload;
      const prev = state.actions[actionId];
      const next = prev ? upsertAction(state, { ...prev, verification }) : state;
      return addMilestone(next, event, {
        kind: 'verified', label: `${prev?.tool ?? actionId} ${verification.status.replace('_', ' ')}`,
        incidentId: prev?.incident_id ?? event.incident_id ?? undefined,
      });
    }
    case 'replan.triggered':
      return addMilestone(state, event, {
        kind: 'replan', label: `Re-plan: ${event.payload.reason}`, incidentId: event.payload.incident_id, runId: event.payload.run_id,
      });
    case 'alert.issued': {
      const al = event.payload;
      const next = { ...state, alerts: upsertById(state.alerts, al) };
      return addMilestone(next, event, {
        kind: 'alert', label: `Alert (${al.level}): ${zoneName(state.city, al.zone_id)}`, zoneId: al.zone_id, incidentId: event.incident_id ?? undefined,
      });
    }
  }
}
