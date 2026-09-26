// Backend city events -> live world, sensor readings, telemetry and milestones. Pure; one case per event type.
import type { EventOf, WorldSnapshot } from '@/api/types';
import { addMilestone, patch, upsertPoint } from './reduce';
import type { LiveState, SensorReading } from './types';

export type WorldEvent = EventOf<
  | 'weather.observation' | 'weather.forecast' | 'environment.soil' | 'environment.river' | 'environment.drainage'
  | 'environment.slope' | 'environment.water_accumulation' | 'infrastructure.road' | 'infrastructure.bridge'
  | 'infrastructure.drainage_obstruction' | 'infrastructure.construction' | 'infrastructure.failure'
  | 'emergency.rescue_team' | 'emergency.ambulance' | 'emergency.hospital' | 'emergency.shelter'
>;

const num = (v: number, digits = 1) => String(Number(v.toFixed(digits)));

function withWorld(state: LiveState, f: (w: WorldSnapshot) => WorldSnapshot): LiveState {
  return state.world ? { ...state, world: f(state.world) } : state;
}

function reading(state: LiveState, sensorId: string, value: number, text: string, simTime: string): LiveState {
  const r: SensorReading = { value, text, simTime };
  return { ...state, readings: { ...state.readings, [sensorId]: r } };
}

function nameOf(list: readonly { id: string; name: string }[] | undefined, id: string): string {
  return list?.find((x) => x.id === id)?.name ?? id;
}

export function applyWorldEvent(state: LiveState, e: WorldEvent): LiveState {
  const at = e.sim_time;
  const zoneId = e.location ?? undefined;
  switch (e.event_type) {
    case 'weather.observation': {
      const p = e.payload;
      if (p.rainfall_intensity_mm_h != null) {
        const rain = p.rainfall_intensity_mm_h;
        const next = withWorld(state, (w) => ({
          ...w,
          zones: zoneId ? patch(w.zones, zoneId, { rainfall_intensity_mm_h: rain, rain_24h_mm: p.cumulative_rainfall_24h_mm ?? 0 }) : w.zones,
        }));
        const withReading = reading(next, p.station_id, rain, `${num(rain)} mm/h`, at);
        return zoneId ? upsertPoint(withReading, zoneId, at, () => ({ rain })) : withReading;
      }
      if (p.wind_speed_kmh == null) return state;
      const wind = p.wind_speed_kmh;
      const next = withWorld(state, (w) => ({
        ...w,
        weather: { temperature_c: p.temperature_c ?? w.weather.temperature_c, wind_speed_kmh: wind, wind_direction_deg: p.wind_direction_deg ?? w.weather.wind_direction_deg },
      }));
      return reading(next, p.station_id, wind, `${num(wind)} km/h wind`, at);
    }
    case 'weather.forecast':
      return withWorld(state, (w) => ({ ...w, forecast: e.payload }));
    case 'environment.soil': {
      const p = e.payload;
      const next = reading(state, p.probe_id, p.saturation, `${String(Math.round(p.saturation * 100))}% saturated`, at);
      return zoneId ? upsertPoint(next, zoneId, at, (prev) => ({ saturation: Math.max(prev?.saturation ?? 0, p.saturation) })) : next;
    }
    case 'environment.river': {
      const p = e.payload;
      const next = withWorld(state, (w) => ({ ...w, rivers: patch(w.rivers, p.river_id, { level_m: p.level_m, trend: p.trend }) }));
      return reading(next, p.gauge_id, p.level_m, `${num(p.level_m, 2)} m, ${p.trend}`, at);
    }
    case 'environment.drainage': {
      const p = e.payload;
      const next = withWorld(state, (w) => ({
        ...w,
        channels: patch(w.channels, p.channel_id, {
          flow_m3s: p.flow_m3s, capacity_m3s: p.capacity_m3s, blocked_fraction: p.blocked_fraction, overflow_m3s: p.overflow_m3s,
        }),
      }));
      return reading(next, p.gauge_id, p.load_ratio, `${String(Math.round(p.load_ratio * 100))}% of capacity`, at);
    }
    case 'environment.slope': {
      const p = e.payload;
      return withWorld(state, (w) => ({
        ...w,
        slopes: patch(w.slopes, p.slope_id, {
          movement_rate_mm_h: p.movement_rate_mm_h, cumulative_movement_mm: p.cumulative_movement_mm, saturation: p.saturation,
        }),
      }));
    }
    case 'environment.water_accumulation': {
      const p = e.payload;
      const next = withWorld(state, (w) => ({ ...w, zones: patch(w.zones, p.zone_id, { water_depth_cm: p.depth_cm, water_trend: p.trend }) }));
      return upsertPoint(next, p.zone_id, at, () => ({ water: p.depth_cm }));
    }
    case 'infrastructure.road': {
      const p = e.payload;
      const next = withWorld(state, (w) => ({ ...w, roads: patch(w.roads, p.road_id, { status: p.status, reason: p.reason }) }));
      return addMilestone(next, e, { kind: 'infrastructure', label: `${nameOf(state.city?.roads, p.road_id)} ${p.status}`, zoneId });
    }
    case 'infrastructure.bridge': {
      const p = e.payload;
      const next = withWorld(state, (w) => ({ ...w, bridges: patch(w.bridges, p.bridge_id, { status: p.status, reason: p.reason }) }));
      return addMilestone(next, e, { kind: 'infrastructure', label: `${nameOf(state.city?.bridges, p.bridge_id)} ${p.status}`, zoneId });
    }
    case 'infrastructure.drainage_obstruction': {
      const p = e.payload;
      const next = withWorld(state, (w) => ({ ...w, channels: patch(w.channels, p.channel_id, { blocked_fraction: p.blocked_fraction }) }));
      const label = `${p.channel_id} ${String(Math.round(p.blocked_fraction * 100))}% blocked`;
      return addMilestone(next, e, { kind: 'infrastructure', label, zoneId });
    }
    case 'infrastructure.construction': {
      const p = e.payload;
      const next = withWorld(state, (w) => ({
        ...w,
        projects: patch(w.projects, p.project_id, { status: p.status, activity: p.activity, excavation_depth_m: p.excavation_depth_m }),
      }));
      if (p.status !== 'halted') return next;
      return addMilestone(next, e, { kind: 'infrastructure', label: `${nameOf(state.city?.projects, p.project_id)} halted`, zoneId });
    }
    case 'infrastructure.failure':
      return addMilestone(state, e, { kind: 'infrastructure', label: `Failure: ${e.payload.description}`, zoneId });
    case 'emergency.rescue_team': {
      const p = e.payload;
      return withWorld(state, (w) => ({
        ...w,
        crews: patch(w.crews, p.crew_id, { status: p.status, location_zone_id: p.location_zone_id, task: p.task }),
      }));
    }
    case 'emergency.ambulance': {
      const p = e.payload;
      return withWorld(state, (w) => ({ ...w, ambulances: patch(w.ambulances, p.ambulance_id, { status: p.status, location_zone_id: p.location_zone_id }) }));
    }
    case 'emergency.hospital': {
      const p = e.payload;
      return withWorld(state, (w) => ({ ...w, hospitals: patch(w.hospitals, p.hospital_id, { beds_occupied: p.beds_occupied, er_status: p.er_status }) }));
    }
    case 'emergency.shelter': {
      const p = e.payload;
      return withWorld(state, (w) => ({ ...w, shelters: patch(w.shelters, p.shelter_id, { status: p.status, occupancy: p.occupancy }) }));
    }
  }
}
