// Pure reducer: (LiveState, Event) -> LiveState. One case per contract event type (spec section 5.3).
import type { Action, AgentRun, AgentStep, Approval, City, Event, EventOf, Incident, StateSnapshot } from '@/api/types';
import { bandLabel } from '@/components/ui/bandLabel';
import { FEED_CAP, MILESTONE_CAP, TELEMETRY_CAP, type LiveAssets, type LiveState, type Milestone } from './types';

function pushCapped<T>(list: readonly T[], item: T, cap: number): T[] {
  const next = [...list, item];
  return next.length > cap ? next.slice(next.length - cap) : next;
}

function byId<T extends { id: string }>(items: readonly T[]): Record<string, T> {
  const out: Record<string, T> = {};
  for (const it of items) out[it.id] = it;
  return out;
}

function upsertById<T extends { id: string }>(items: readonly T[], item: T): T[] {
  return items.some((x) => x.id === item.id) ? items.map((x) => (x.id === item.id ? item : x)) : [...items, item];
}

function zoneName(city: City | null, zoneId: string): string {
  return city?.zones.find((z) => z.id === zoneId)?.name ?? zoneId;
}

function addMilestone(state: LiveState, event: Event, m: Omit<Milestone, 'id' | 'ts' | 'simTime'>): LiveState {
  const milestone: Milestone = { id: event.id, ts: event.ts, simTime: event.sim_time, ...m };
  return { ...state, milestones: pushCapped(state.milestones, milestone, MILESTONE_CAP) };
}

function assetsFromCity(city: City): LiveAssets {
  return {
    crews: byId(city.crews),
    shelters: byId(city.shelters),
    roads: byId(city.roads),
    channels: byId(city.channels),
    projects: byId(city.projects),
    pumpUnits: city.pump_depot.units,
    sensors: byId(city.sensors),
  };
}

function applySnapshot(state: LiveState, p: StateSnapshot, event: Event): LiveState {
  const zoneState: LiveState['zoneState'] = {};
  for (const z of p.city.zones) zoneState[z.id] = z.state;
  const milestones: Milestone[] = p.incidents
    .filter((i) => i.status === 'open')
    .map((i) => ({
      id: `${event.id}:${i.id}`, kind: 'incident', ts: i.opened_at, simTime: i.opened_sim_time,
      label: `Incident opened: ${i.hazard} in ${zoneName(p.city, i.zone_id)}`, zoneId: i.zone_id, incidentId: i.id, band: i.band,
    }));
  return {
    ...state,
    hasSnapshot: true,
    sim: { simTime: p.sim.sim_time, tick: p.sim.tick, running: p.sim.running, speed: p.sim.speed, scenario: p.sim.scenario },
    llm: p.llm,
    city: p.city,
    zoneState,
    incidents: byId(p.incidents),
    approvals: byId(p.approvals),
    actions: byId(p.actions),
    alerts: p.alerts,
    assets: assetsFromCity(p.city),
    telemetry: {},
    milestones,
  };
}

function applyZoneState(state: LiveState, event: EventOf<'zone.state'>): LiveState {
  const { zone_id: zoneId, prev_band: prevBand, ...zs } = event.payload;
  const point = {
    simTime: event.sim_time ?? zs.updated_sim_time, tick: state.sim.tick, rain: zs.rain_intensity_mm_h,
    saturation: zs.saturation, landslide: zs.landslide_index, flood: zs.flood_index, band: zs.band,
  };
  const next: LiveState = {
    ...state,
    zoneState: { ...state.zoneState, [zoneId]: zs },
    telemetry: { ...state.telemetry, [zoneId]: pushCapped(state.telemetry[zoneId] ?? [], point, TELEMETRY_CAP) },
  };
  if (prevBand == null || prevBand === zs.band) return next;
  return addMilestone(next, event, { kind: 'band', label: `${zoneName(state.city, zoneId)}: ${bandLabel(zs.band)}`, zoneId, band: zs.band });
}

function applyThreat(state: LiveState, event: EventOf<'threat.detected'> | EventOf<'threat.escalated'>): LiveState {
  const p = event.payload;
  const incident = state.incidents[p.incident_id];
  const next =
    event.type === 'threat.escalated' && incident?.zone_id === p.zone_id
      ? { ...state, incidents: { ...state.incidents, [incident.id]: { ...incident, band: p.band } } }
      : state;
  const verb = event.type === 'threat.detected' ? 'Threat detected' : 'Threat escalated';
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
  const verb = event.type === 'incident.opened' ? 'Incident opened' : 'Incident closed';
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
  const label = event.type === 'approval.requested' ? 'Approval requested' : `Approval ${a.status}`;
  return addMilestone(next, event, { kind: 'approval', label, incidentId: a.incident_id });
}

function setStatus<T extends { status: string }>(table: Record<string, T>, id: string, to: string): Record<string, T> {
  const entity = table[id];
  return entity ? { ...table, [id]: { ...entity, status: to } } : table;
}

/** Only `status` changes are applied to live assets; other fields stay as the snapshot sent them. */
function applyStateChanges(assets: LiveAssets, action: Action): LiveAssets {
  let next = assets;
  for (const c of action.state_changes) {
    if (c.field !== 'status') continue;
    switch (c.entity_type) {
      case 'crew': next = { ...next, crews: setStatus(next.crews, c.entity_id, c.to) }; break;
      case 'shelter': next = { ...next, shelters: setStatus(next.shelters, c.entity_id, c.to) }; break;
      case 'road': next = { ...next, roads: setStatus(next.roads, c.entity_id, c.to) }; break;
      case 'project': next = { ...next, projects: setStatus(next.projects, c.entity_id, c.to) }; break;
      case 'pump_unit':
        next = { ...next, pumpUnits: next.pumpUnits.map((u) => (u.id === c.entity_id ? { ...u, status: c.to as typeof u.status } : u)) };
        break;
      default: break; // channel and alert changes carry no live status field
    }
  }
  return next;
}

function upsertAction(state: LiveState, a: Action): LiveState {
  return withIncident({ ...state, actions: { ...state.actions, [a.id]: a } }, a.incident_id, (i) => ({ ...i, actions: upsertById(i.actions, a) }));
}

export function applyEvent(state: LiveState, event: Event): LiveState {
  const withFeed: LiveState = { ...state, feed: pushCapped(state.feed, event, FEED_CAP) };
  switch (event.type) {
    case 'state.snapshot':
      return applySnapshot(withFeed, event.payload, event);
    case 'sim.tick': {
      const p = event.payload;
      return { ...withFeed, sim: { ...withFeed.sim, simTime: p.sim_time, tick: p.tick, running: p.running, speed: p.speed } };
    }
    case 'sensor.reading': {
      const p = event.payload;
      const sensor = withFeed.assets.sensors[p.sensor_id];
      if (!sensor) return withFeed;
      const updated = { ...sensor, last_value: p.value, last_sim_time: event.sim_time };
      return { ...withFeed, assets: { ...withFeed.assets, sensors: { ...withFeed.assets.sensors, [p.sensor_id]: updated } } };
    }
    case 'zone.state':
      return applyZoneState(withFeed, event);
    case 'threat.detected':
    case 'threat.escalated':
      return applyThreat(withFeed, event);
    case 'incident.opened':
    case 'incident.closed':
      return applyIncident(withFeed, event);
    case 'agent.run.started':
    case 'agent.run.finished':
      return upsertRun(withFeed, event.payload);
    case 'agent.node.started': {
      const p = event.payload;
      const step: AgentStep = { id: p.step_id, run_id: p.run_id, node: p.node, status: 'running', started_at: event.ts, output: null, citations: [] };
      return upsertStep(withFeed, p.incident_id, step, event.ts);
    }
    case 'agent.node.finished':
      return upsertStep(withFeed, event.incident_id, event.payload, event.ts);
    case 'approval.requested':
    case 'approval.decided':
      return upsertApproval(withFeed, event);
    case 'action.executed': {
      const a = event.payload;
      const next = upsertAction({ ...withFeed, assets: applyStateChanges(withFeed.assets, a) }, a);
      return addMilestone(next, event, { kind: 'action', label: `${a.tool} executed`, incidentId: a.incident_id });
    }
    case 'action.verified': {
      const { action_id: actionId, verification } = event.payload;
      const prev = withFeed.actions[actionId];
      const next = prev ? upsertAction(withFeed, { ...prev, verification }) : withFeed;
      return addMilestone(next, event, {
        kind: 'verified', label: `${prev?.tool ?? actionId} ${verification.status.replace('_', ' ')}`, incidentId: prev?.incident_id ?? event.incident_id ?? undefined,
      });
    }
    case 'replan.triggered':
      return addMilestone(withFeed, event, {
        kind: 'replan', label: `Re-plan: ${event.payload.reason}`, incidentId: event.payload.incident_id, runId: event.payload.run_id,
      });
    case 'alert.issued': {
      const al = event.payload;
      const next = { ...withFeed, alerts: upsertById(withFeed.alerts, al) };
      return addMilestone(next, event, {
        kind: 'alert', label: `Alert (${al.level}): ${zoneName(withFeed.city, al.zone_id)}`, zoneId: al.zone_id, incidentId: event.incident_id ?? undefined,
      });
    }
    case 'scenario.event':
      return addMilestone(withFeed, event, { kind: 'scenario', label: event.payload.description });
    default:
      return withFeed;
  }
}
