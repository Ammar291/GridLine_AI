import type { ApiMode } from '@/api/client';
import type {
  Action,
  Alert,
  Approval,
  Band,
  Channel,
  City,
  Crew,
  Event,
  Incident,
  LlmStatus,
  Project,
  PumpUnit,
  Road,
  Sensor,
  Shelter,
  ZoneState,
} from '@/api/types';

export type ConnectionStatus = 'connecting' | 'open' | 'reconnecting' | 'closed';

export interface TelemetryPoint {
  simTime: string;
  tick: number;
  rain: number;
  saturation: number;
  landslide: number;
  flood: number;
  band: Band;
}

export type MilestoneKind = 'band' | 'incident' | 'approval' | 'action' | 'verified' | 'replan' | 'alert' | 'scenario';

export interface Milestone {
  id: string;
  kind: MilestoneKind;
  simTime: string | null;
  ts: string;
  label: string;
  zoneId?: string;
  incidentId?: string;
  band?: Band;
}

export interface LiveAssets {
  crews: Record<string, Crew>;
  shelters: Record<string, Shelter>;
  roads: Record<string, Road>;
  channels: Record<string, Channel>;
  projects: Record<string, Project>;
  pumpUnits: PumpUnit[];
  sensors: Record<string, Sensor>;
}

export interface LiveState {
  connection: ConnectionStatus;
  mode: ApiMode;
  hasSnapshot: boolean;
  sim: { simTime: string | null; tick: number; running: boolean; speed: number; scenario: string | null };
  llm: LlmStatus | null;
  /** Static part of the city; live zone state is kept in zoneState. */
  city: City | null;
  zoneState: Record<string, ZoneState>;
  incidents: Record<string, Incident>;
  approvals: Record<string, Approval>;
  actions: Record<string, Action>;
  alerts: Alert[];
  assets: LiveAssets;
  /** Newest last, capped at FEED_CAP. */
  feed: Event[];
  /** Per zone, capped at TELEMETRY_CAP. */
  telemetry: Record<string, TelemetryPoint[]>;
  milestones: Milestone[];
}

export const FEED_CAP = 500;
export const TELEMETRY_CAP = 720;
export const MILESTONE_CAP = 500;

export function emptyAssets(): LiveAssets {
  return { crews: {}, shelters: {}, roads: {}, channels: {}, projects: {}, pumpUnits: [], sensors: {} };
}

export function initialLiveState(mode: ApiMode): LiveState {
  return {
    connection: 'connecting',
    mode,
    hasSnapshot: false,
    sim: { simTime: null, tick: 0, running: false, speed: 1, scenario: null },
    llm: null,
    city: null,
    zoneState: {},
    incidents: {},
    approvals: {},
    actions: {},
    alerts: [],
    assets: emptyAssets(),
    feed: [],
    telemetry: {},
    milestones: [],
  };
}
