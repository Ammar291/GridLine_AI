import type { ApiMode } from '@/api/client';
import type { Action, Alert, Approval, Band, City, Event, Incident, SimStatus, WorldSnapshot, ZoneState } from '@/api/types';

export type ConnectionStatus = 'connecting' | 'open' | 'reconnecting' | 'closed';
export type RunnerState = SimStatus['state'];

export interface SimState {
  state: RunnerState;
  running: boolean;
  scenario: string | null;
  seed: number | null;
  speed: number;
  tick: number;
  simTime: string | null;
  stage: string | null;
}

/** The latest observation a sensor reported, already worded with its unit ("12.4 mm/h"). */
export interface SensorReading {
  value: number;
  text: string;
  simTime: string;
}

/** One sim time of a zone's timeline. Readings the zone has no sensor or detector for stay null. */
export interface TelemetryPoint {
  simTime: string;
  rain: number | null;
  saturation: number | null;
  landslide: number | null;
  flood: number | null;
  /** Standing water in cm (the simulation reports it where water ponds). */
  water: number | null;
  band: Band | null;
}

export type MilestoneKind =
  | 'band' | 'incident' | 'approval' | 'action' | 'verified' | 'replan' | 'alert' | 'scenario' | 'infrastructure';

export interface Milestone {
  id: string;
  kind: MilestoneKind;
  simTime: string | null;
  ts: string;
  label: string;
  zoneId?: string;
  incidentId?: string;
  /** Set on replan milestones: the run whose plan is being replaced. */
  runId?: string;
  band?: Band;
}

export interface LiveState {
  connection: ConnectionStatus;
  mode: ApiMode;
  hasSnapshot: boolean;
  sim: SimState;
  /** Static city from the snapshot (GET /api/city serves the same). */
  city: City | null;
  /** Live state: the snapshot's world, kept current by the observation, infrastructure and emergency events. */
  world: WorldSnapshot | null;
  readings: Record<string, SensorReading>;
  // PENDING (threat detector, agent, approvals, actions, alerts): only the events of later milestones fill these.
  zoneState: Record<string, ZoneState>;
  incidents: Record<string, Incident>;
  approvals: Record<string, Approval>;
  actions: Record<string, Action>;
  alerts: Alert[];
  /** Newest last, capped at FEED_CAP; a full feed drops its oldest tick or reading first. */
  feed: Event[];
  /** Per zone, capped at TELEMETRY_CAP. */
  telemetry: Record<string, TelemetryPoint[]>;
  milestones: Milestone[];
}

export const FEED_CAP = 500;
export const TELEMETRY_CAP = 720;
export const MILESTONE_CAP = 500;

export function initialSim(): SimState {
  return { state: 'idle', running: false, scenario: null, seed: null, speed: 1, tick: 0, simTime: null, stage: null };
}

export function initialLiveState(mode: ApiMode): LiveState {
  return {
    connection: 'connecting',
    mode,
    hasSnapshot: false,
    sim: initialSim(),
    city: null,
    world: null,
    readings: {},
    zoneState: {},
    incidents: {},
    approvals: {},
    actions: {},
    alerts: [],
    feed: [],
    telemetry: {},
    milestones: [],
  };
}
