import { useMemo } from 'react';
import type { Alert, City, Incident, MapFeature, PumpDepot, WorldSnapshot, Zone, ZoneConditions, ZoneState } from '@/api/types';
import {
  liveAssets,
  type LiveAssets, type LiveBridge, type LiveChannel, type LiveCrew, type LiveHospital, type LiveProject, type LiveRoad,
  type LiveSensor, type LiveShelter,
} from '@/live/assets';
import { latestRun, stepOutput } from '@/live/derive';
import { useLiveStore } from '@/live/liveStore';

/** A zone with its live conditions (world) and, once the threat detector reports it, its band (PENDING). */
export interface MapZone { zone: Zone; conditions: ZoneConditions | null; state: ZoneState | null }
export interface Cascade { from: string; to: string }

/** City geometry with live state laid over it. Only entities the city knows are drawn. */
export interface MapData {
  zones: MapZone[];
  zoneById: ReadonlyMap<string, MapZone>;
  roads: LiveRoad[];
  bridges: LiveBridge[];
  channels: LiveChannel[];
  projects: LiveProject[];
  crews: LiveCrew[];
  shelters: LiveShelter[];
  hospitals: LiveHospital[];
  sensors: LiveSensor[];
  depot: PumpDepot;
  features: MapFeature[];
  /** Zones under an evacuate-level alert (PENDING: alerts). */
  evacuatedZoneIds: string[];
  /** Cascade arrows from the agent's latest cascade analysis (PENDING: agent). */
  cascades: Cascade[];
}

function cascades(incidents: Record<string, Incident>, known: ReadonlyMap<string, MapZone>): Cascade[] {
  const seen = new Set<string>();
  const out: Cascade[] = [];
  for (const incident of Object.values(incidents)) {
    if (incident.status !== 'open' || !known.has(incident.zone_id)) continue;
    for (const to of stepOutput(latestRun(incident), 'cascade')?.affected_zone_ids ?? []) {
      const key = `${incident.zone_id}>${to}`;
      if (to === incident.zone_id || !known.has(to) || seen.has(key)) continue;
      seen.add(key);
      out.push({ from: incident.zone_id, to });
    }
  }
  return out;
}

export function buildMapData(
  city: City, world: WorldSnapshot | null, zoneState: Record<string, ZoneState>, assets: LiveAssets, alerts: Alert[],
  incidents: Record<string, Incident>,
): MapData {
  const zones = city.zones.map((zone) => ({ zone, conditions: world?.zones[zone.id] ?? null, state: zoneState[zone.id] ?? null }));
  const zoneById = new Map(zones.map((z) => [z.zone.id, z]));
  const pick = <T,>(table: Record<string, T>): T[] => Object.values(table);
  return {
    zones,
    zoneById,
    roads: pick(assets.roads),
    bridges: pick(assets.bridges),
    channels: pick(assets.channels),
    projects: pick(assets.projects),
    crews: pick(assets.crews),
    shelters: pick(assets.shelters),
    hospitals: pick(assets.hospitals),
    sensors: pick(assets.sensors),
    depot: { ...city.pump_depot, units: assets.pumpUnits.length > 0 ? assets.pumpUnits : city.pump_depot.units },
    features: city.map_features,
    evacuatedZoneIds: [...new Set(alerts.filter((a) => a.level === 'evacuate' && zoneById.has(a.zone_id)).map((a) => a.zone_id))],
    cascades: cascades(incidents, zoneById),
  };
}

export function useMapData(city: City): MapData {
  const world = useLiveStore((s) => s.world);
  const zoneState = useLiveStore((s) => s.zoneState);
  const alerts = useLiveStore((s) => s.alerts);
  const incidents = useLiveStore((s) => s.incidents);
  const readings = useLiveStore((s) => s.readings);
  return useMemo(
    () => buildMapData(city, world, zoneState, liveAssets(city, world, readings), alerts, incidents),
    [city, world, zoneState, readings, alerts, incidents],
  );
}
