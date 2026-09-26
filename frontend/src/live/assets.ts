// The city's assets as they are now: each static entity from the city merged with its live state from the world.
// Pure; memoise at the call site (useLiveAssets). Entities the world does not know keep their static defaults.
import type {
  Bridge, BridgeState, Channel, ChannelState, City, Crew, CrewState, Hospital, HospitalState, Project, ProjectState,
  PumpUnit, Road, RoadState, Sensor, Shelter, ShelterState, WorldSnapshot,
} from '@/api/types';
import type { SensorReading } from './types';

export type LiveRoad = Road & RoadState;
export type LiveBridge = Bridge & BridgeState;
export type LiveChannel = Channel & Required<ChannelState>;
export type LiveProject = Project & Required<ProjectState>;
export type LiveCrew = Crew & Required<CrewState>;
export type LiveShelter = Shelter & ShelterState;
export type LiveHospital = Hospital & Required<HospitalState>;
export type LiveSensor = Sensor & { reading: SensorReading | null };

export interface LiveAssets {
  roads: Record<string, LiveRoad>;
  bridges: Record<string, LiveBridge>;
  channels: Record<string, LiveChannel>;
  projects: Record<string, LiveProject>;
  crews: Record<string, LiveCrew>;
  shelters: Record<string, LiveShelter>;
  hospitals: Record<string, LiveHospital>;
  sensors: Record<string, LiveSensor>;
  pumpUnits: PumpUnit[];
}

export function emptyAssets(): LiveAssets {
  return { roads: {}, bridges: {}, channels: {}, projects: {}, crews: {}, shelters: {}, hospitals: {}, sensors: {}, pumpUnits: [] };
}

function byId<T extends { id: string }, L>(items: readonly T[], merge: (item: T) => L): Record<string, L> {
  const out: Record<string, L> = {};
  for (const it of items) out[it.id] = merge(it);
  return out;
}

export function liveAssets(city: City | null, world: WorldSnapshot | null, readings: Record<string, SensorReading>): LiveAssets {
  if (!city) return emptyAssets();
  const w = world;
  return {
    roads: byId(city.roads, (r) => ({ ...r, status: 'open', reason: '', ...w?.roads[r.id] })),
    bridges: byId(city.bridges, (b) => ({ ...b, status: 'open', reason: '', ...w?.bridges[b.id] })),
    channels: byId(city.channels, (c) => {
      const s = w?.channels[c.id];
      return {
        ...c,
        blocked_fraction: s?.blocked_fraction ?? 0,
        capacity_m3s: s?.capacity_m3s ?? c.current_capacity_m3s,
        extra_capacity_m3s: s?.extra_capacity_m3s ?? 0,
        gate_closed: s?.gate_closed ?? false,
        flow_m3s: s?.flow_m3s ?? 0,
        overflow_m3s: s?.overflow_m3s ?? 0,
      };
    }),
    projects: byId(city.projects, (p) => {
      const s = w?.projects[p.id];
      return { ...p, status: s?.status ?? 'active', activity: s?.activity ?? 'idle', excavation_depth_m: s?.excavation_depth_m ?? 0 };
    }),
    crews: byId(city.crews, (c) => {
      const s = w?.crews[c.id];
      return { ...c, status: s?.status ?? 'available', location_zone_id: s?.location_zone_id ?? c.base_zone_id, task: s?.task ?? '' };
    }),
    shelters: byId(city.shelters, (s) => ({ ...s, status: 'closed', occupancy: 0, ...w?.shelters[s.id] })),
    hospitals: byId(city.hospitals, (h) => {
      const s = w?.hospitals[h.id];
      return { ...h, beds_occupied: s?.beds_occupied ?? 0, er_status: s?.er_status ?? 'normal' };
    }),
    sensors: byId(city.sensors, (s) => ({ ...s, reading: readings[s.id] ?? null })),
    pumpUnits: city.pump_depot.units,
  };
}
