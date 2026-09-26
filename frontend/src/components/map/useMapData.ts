import { useMemo } from 'react';
import type { Alert, Channel, City, Crew, Incident, Project, PumpDepot, Road, Sensor, Shelter, Zone, ZoneState } from '@/api/types';
import { latestRun, stepOutput } from '@/live/derive';
import { useLiveStore } from '@/live/liveStore';
import type { LiveAssets } from '@/live/types';

export interface MapZone { zone: Zone; state: ZoneState }
export interface Cascade { from: string; to: string }

/** City geometry with live state laid over it. Only entities the city knows are drawn (unknown ids are dropped). */
export interface MapData {
  zones: MapZone[];
  zoneById: ReadonlyMap<string, MapZone>;
  roads: Road[];
  channels: Channel[];
  projects: Project[];
  crews: Crew[];
  shelters: Shelter[];
  sensors: Sensor[];
  depot: PumpDepot;
  hospitals: City['hospitals'];
  features: City['map_features'];
  /** Zones under an evacuate-level alert. */
  evacuatedZoneIds: string[];
  cascades: Cascade[];
}

const live = <T extends { id: string }>(items: readonly T[], table: Record<string, T>): T[] => items.map((it) => table[it.id] ?? it);

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
  city: City, zoneState: Record<string, ZoneState>, assets: LiveAssets, alerts: Alert[], incidents: Record<string, Incident>,
): MapData {
  const zones = city.zones.map((zone) => ({ zone, state: zoneState[zone.id] ?? zone.state }));
  const zoneById = new Map(zones.map((z) => [z.zone.id, z]));
  return {
    zones,
    zoneById,
    roads: live(city.roads, assets.roads),
    channels: live(city.channels, assets.channels),
    projects: live(city.projects, assets.projects),
    crews: live(city.crews, assets.crews),
    shelters: live(city.shelters, assets.shelters),
    sensors: live(city.sensors, assets.sensors),
    depot: { ...city.pump_depot, units: assets.pumpUnits.length > 0 ? assets.pumpUnits : city.pump_depot.units },
    hospitals: city.hospitals,
    features: city.map_features,
    evacuatedZoneIds: [...new Set(alerts.filter((a) => a.level === 'evacuate' && zoneById.has(a.zone_id)).map((a) => a.zone_id))],
    cascades: cascades(incidents, zoneById),
  };
}

export function useMapData(city: City): MapData {
  const zoneState = useLiveStore((s) => s.zoneState);
  const assets = useLiveStore((s) => s.assets);
  const alerts = useLiveStore((s) => s.alerts);
  const incidents = useLiveStore((s) => s.incidents);
  return useMemo(() => buildMapData(city, zoneState, assets, alerts, incidents), [city, zoneState, assets, alerts, incidents]);
}
