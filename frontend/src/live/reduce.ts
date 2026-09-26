// Small pure helpers shared by the event reducers.
import type { City, Event } from '@/api/types';
import { MILESTONE_CAP, TELEMETRY_CAP, type LiveState, type Milestone, type TelemetryPoint } from './types';

export function pushCapped<T>(list: readonly T[], item: T, cap: number): T[] {
  const next = [...list, item];
  return next.length > cap ? next.slice(next.length - cap) : next;
}

export function byId<T extends { id: string }>(items: readonly T[]): Record<string, T> {
  const out: Record<string, T> = {};
  for (const it of items) out[it.id] = it;
  return out;
}

export function upsertById<T extends { id: string }>(items: readonly T[], item: T): T[] {
  return items.some((x) => x.id === item.id) ? items.map((x) => (x.id === item.id ? item : x)) : [...items, item];
}

/** Merge `update` into `table[id]`; ids the table does not hold are ignored. */
export function patch<T extends object>(table: Record<string, T>, id: string, update: Partial<T>): Record<string, T> {
  const current = table[id];
  return current ? { ...table, [id]: { ...current, ...update } } : table;
}

export function zoneName(city: City | null, zoneId: string | null | undefined): string {
  if (zoneId == null) return 'the city';
  return city?.zones.find((z) => z.id === zoneId)?.name ?? zoneId;
}

export function addMilestone(state: LiveState, event: Event, m: Omit<Milestone, 'id' | 'ts' | 'simTime'>): LiveState {
  const milestone: Milestone = { id: event.event_id, ts: event.timestamp, simTime: event.sim_time, ...m };
  return { ...state, milestones: pushCapped(state.milestones, milestone, MILESTONE_CAP) };
}

const EMPTY_POINT = { rain: null, saturation: null, landslide: null, flood: null, water: null, band: null } as const;

/** Merge readings into the zone's point for this sim time (one point per sim time), or start the next point. */
export function upsertPoint(
  state: LiveState, zoneId: string, simTime: string, update: (prev: TelemetryPoint | null) => Partial<TelemetryPoint>,
): LiveState {
  const points = state.telemetry[zoneId] ?? [];
  const last = points.at(-1);
  const same = last?.simTime === simTime ? last : null;
  const point: TelemetryPoint = { ...EMPTY_POINT, ...same, simTime, ...update(same) };
  const next = same ? [...points.slice(0, -1), point] : pushCapped(points, point, TELEMETRY_CAP);
  return { ...state, telemetry: { ...state.telemetry, [zoneId]: next } };
}
