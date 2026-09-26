// Pure reducer: (LiveState, Event) -> LiveState over the backend's event contract, plus the pending events of later
// milestones (applyPending). Every event except the heartbeat also lands in the feed.
import type { Event, EventOf, SimStatus } from '@/api/types';
import { agentRunFromSnapshot, applyAgentStep } from './applyAgentStep';
import { applyPendingEvent } from './applyPending';
import { applyWorldEvent } from './applyWorld';
import { applyLiveWeather, dataModeOf } from './liveWeather';
import { eventGroup } from './describeEvent';
import { addMilestone } from './reduce';
import { FEED_CAP, type LiveState, type SimState } from './types';

/** The engine announces stage 0 only when it resets (Reset, a new scenario, or Start with a scenario). */
export function isEngineReset(e: Event): boolean {
  return e.event_type === 'scenario.stage' && e.payload.stage_index === 0;
}

/** A new run: readings, charts, milestones and everything derived from the old run start over. */
function startOver(state: LiveState): LiveState {
  return {
    ...state, readings: {}, telemetry: {}, milestones: [], zoneState: {}, incidents: {}, approvals: {}, actions: {}, alerts: [],
    liveWeather: { observation: null, forecast: null }, agentRun: null,
  };
}

function simFrom(s: SimStatus): SimState {
  return {
    state: s.state, running: s.running, scenario: s.scenario, seed: s.seed, speed: s.speed, tick: s.tick, simTime: s.sim_time, stage: s.stage,
  };
}

/** The first frame of every connection. A reconnect within the same run keeps the charts; a new run starts over. */
function applySnapshot(state: LiveState, e: EventOf<'sim.snapshot'>): LiveState {
  const { status, world, city } = e.payload;
  const source = e.payload.source ?? state.source;
  const sameMode = state.source === null || source === null || state.source.mode === source.mode;
  const sameRun = sameMode && state.hasSnapshot && state.sim.scenario === status.scenario && status.tick >= state.sim.tick;
  return {
    ...(sameRun ? state : startOver(state)), hasSnapshot: true, city, world, sim: simFrom(status), source,
    agentRun: agentRunFromSnapshot(e.payload.agent_run),
  };
}

/** A change of data source starts the feed and readings over: LIVE and DEMO describe different cities. */
function applySource(state: LiveState, e: EventOf<'source.status'>): LiveState {
  const switched = state.source !== null && state.source.mode !== e.payload.mode;
  return { ...(switched ? { ...startOver(state), feed: [e] } : state), source: e.payload };
}

/** Ticks, readings and a zone.state that keeps its band are routine: a full feed drops them first. */
const isRoutine = (e: Event) =>
  e.event_type === 'sim.tick' || eventGroup(e.event_type) === 'reading' ||
  (e.event_type === 'zone.state' && (e.payload.prev_band == null || e.payload.prev_band === e.payload.band));

/**
 * Append to the feed. Readings arrive about 20 per tick, so a full feed drops its oldest tick or reading first and
 * keeps stage changes, city changes and later-milestone events; only a feed with nothing routine drops its oldest.
 */
function pushFeed(feed: readonly Event[], event: Event): Event[] {
  if (feed.length < FEED_CAP) return [...feed, event];
  const drop = Math.max(0, feed.findIndex(isRoutine));
  return [...feed.slice(0, drop), ...feed.slice(drop + 1), event];
}

export function applyEvent(state: LiveState, event: Event): LiveState {
  if (event.event_type === 'sim.heartbeat') return state;
  const s: LiveState = { ...state, feed: pushFeed(state.feed, event) };
  switch (event.event_type) {
    case 'sim.snapshot':
      return applySnapshot(s, event);
    case 'sim.status':
      return { ...s, sim: simFrom(event.payload) };
    case 'sim.tick': {
      const p = event.payload;
      const world = s.world ? { ...s.world, tick: p.tick, sim_time: p.sim_time } : null;
      const sim: SimState = {
        ...s.sim, tick: p.tick, simTime: p.sim_time, speed: p.speed, running: p.running, stage: p.stage, scenario: p.scenario,
        state: p.running ? 'running' : s.sim.state,
      };
      return { ...s, world, sim };
    }
    case 'scenario.stage': {
      const p = event.payload;
      const base = p.stage_index === 0 ? startOver(s) : s;
      const world = base.world ? { ...base.world, stage_index: p.stage_index } : null;
      const next = { ...base, world, sim: { ...base.sim, stage: p.stage, scenario: p.scenario } };
      return addMilestone(next, event, { kind: 'scenario', label: p.description });
    }
    case 'scenario.trigger':
      return addMilestone(s, event, { kind: 'scenario', label: event.payload.label });
    case 'source.status':
      return applySource(s, event);
    case 'weather.observation':
    case 'weather.forecast':
      return dataModeOf(s) === 'live' ? applyLiveWeather(s, event) : applyWorldEvent(s, event);
    case 'environment.soil':
    case 'environment.river':
    case 'environment.drainage':
    case 'environment.slope':
    case 'environment.water_accumulation':
    case 'infrastructure.road':
    case 'infrastructure.bridge':
    case 'infrastructure.drainage_obstruction':
    case 'infrastructure.construction':
    case 'infrastructure.failure':
    case 'emergency.rescue_team':
    case 'emergency.ambulance':
    case 'emergency.hospital':
    case 'emergency.shelter':
    case 'weather.rainfall':
    case 'emergency.fire':
      return applyWorldEvent(s, event);
    case 'agent.step':
      return { ...s, agentRun: applyAgentStep(s.agentRun, event.payload) };
    case 'zone.state':
    case 'threat.detected':
    case 'threat.escalated':
    case 'incident.opened':
    case 'incident.closed':
    case 'agent.run.started':
    case 'agent.run.finished':
    case 'agent.node.started':
    case 'agent.node.finished':
    case 'approval.requested':
    case 'approval.decided':
    case 'action.executed':
    case 'action.verified':
    case 'replan.triggered':
    case 'alert.issued':
      return applyPendingEvent(s, event);
    default:
      return s; // an event type this build does not know: kept in the feed, otherwise ignored
  }
}

export function applyEvents(state: LiveState, events: readonly Event[]): LiveState {
  return events.reduce(applyEvent, state);
}
