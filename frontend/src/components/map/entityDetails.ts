import type { Band } from '@/api/types';
import { fmtIndex, fmtNumber, fmtPct, statusLabel } from '@/live/format';
import type { EntityRef } from '@/ui/uiStore';
import { BLOCKED_THRESHOLD } from './mapStyles';
import type { MapData } from './useMapData';

export interface EntityDetails {
  title: string;
  kindLabel: string;
  band?: Band;
  items: { label: string; value: string }[];
}

const yesNo = (b: boolean) => (b ? 'Yes' : 'No');
const trim = (x: number) => String(Number(x.toFixed(2)));

/** Fields the popover shows for the selected map entity; null when the entity is not in the city. */
export function entityDetails(ref: EntityRef, data: MapData): EntityDetails | null {
  const zone = (id: string | null | undefined) => (id == null ? 'None' : (data.zoneById.get(id)?.zone.name ?? id));
  switch (ref.kind) {
    case 'zone': {
      const z = data.zoneById.get(ref.id);
      if (!z) return null;
      const s = z.state;
      return {
        title: z.zone.name, kindLabel: 'Zone', band: s.band,
        items: [
          { label: 'Population', value: fmtNumber(z.zone.population) },
          { label: 'Slope', value: `${trim(z.zone.slope_deg)}°` },
          { label: 'Saturation', value: fmtPct(s.saturation) },
          { label: 'Rain intensity', value: `${trim(s.rain_intensity_mm_h)} mm/h` },
          { label: 'Landslide index', value: fmtIndex(s.landslide_index) },
          { label: 'Flood index', value: fmtIndex(s.flood_index) },
          { label: 'Soil', value: z.zone.soil_type },
        ],
      };
    }
    case 'crew': {
      const c = data.crews.find((x) => x.id === ref.id);
      if (!c) return null;
      return {
        title: c.name, kindLabel: 'Crew',
        items: [
          { label: 'Status', value: statusLabel(c.status) },
          { label: 'Location', value: zone(c.location_zone_id) },
          { label: 'Heading to', value: zone(c.target_zone_id) },
          { label: 'Task', value: c.task ?? 'None' },
        ],
      };
    }
    case 'shelter': {
      const s = data.shelters.find((x) => x.id === ref.id);
      if (!s) return null;
      return {
        title: s.name, kindLabel: 'Shelter',
        items: [
          { label: 'Status', value: statusLabel(s.status) },
          { label: 'Occupancy', value: `${fmtNumber(s.occupancy)} of ${fmtNumber(s.capacity)}` },
          { label: 'Zone', value: zone(s.zone_id) },
        ],
      };
    }
    case 'road': {
      const r = data.roads.find((x) => x.id === ref.id);
      if (!r) return null;
      return {
        title: r.name, kindLabel: 'Road',
        items: [
          { label: 'Status', value: statusLabel(r.status) },
          { label: 'Evacuation route', value: yesNo(r.is_evacuation_route) },
          { label: 'Bridge', value: yesNo(r.is_bridge) },
          { label: 'Zones', value: r.zone_ids.map(zone).join(', ') || 'None' },
        ],
      };
    }
    case 'channel': {
      const c = data.channels.find((x) => x.id === ref.id);
      if (!c) return null;
      return {
        title: c.name, kindLabel: 'Drainage channel',
        items: [
          { label: 'Capacity', value: `${trim(c.current_capacity_m3s)} of ${trim(c.design_capacity_m3s)} m³/s` },
          { label: 'Blocked', value: `${fmtPct(c.blocked_fraction)}${c.blocked_fraction > BLOCKED_THRESHOLD ? ', over limit' : ''}` },
          { label: 'Drains to', value: zone(c.downstream_zone_id) },
        ],
      };
    }
    case 'project': {
      const p = data.projects.find((x) => x.id === ref.id);
      if (!p) return null;
      return {
        title: p.name, kindLabel: 'Construction',
        items: [
          { label: 'Status', value: statusLabel(p.status) },
          { label: 'Excavation', value: `${trim(p.excavation_depth_m)} of ${trim(p.planned_depth_m)} m` },
          { label: 'Permit', value: p.permit_doc_id ?? 'None on file' },
          { label: 'Zone', value: zone(p.zone_id) },
        ],
      };
    }
    case 'hospital': {
      const h = data.hospitals.find((x) => x.id === ref.id);
      if (!h) return null;
      return { title: h.name, kindLabel: 'Hospital', items: [{ label: 'Beds', value: fmtNumber(h.beds) }, { label: 'Zone', value: zone(h.zone_id) }] };
    }
    case 'sensor': {
      const s = data.sensors.find((x) => x.id === ref.id);
      if (!s) return null;
      return {
        title: s.id, kindLabel: `${statusLabel(s.kind)} sensor`,
        items: [
          { label: 'Last reading', value: s.last_value == null ? 'No reading yet' : `${trim(s.last_value)} ${s.unit}` },
          { label: 'Zone', value: zone(s.zone_id) },
        ],
      };
    }
    case 'pump_depot': {
      const units = data.depot.units;
      const deployed = units.filter((p) => p.status === 'deployed');
      return {
        title: 'Pump depot', kindLabel: 'Pumps',
        items: [
          { label: 'At depot', value: `${String(units.length - deployed.length)} of ${String(units.length)}` },
          { label: 'Zone', value: zone(data.depot.zone_id) },
          { label: 'Deployed', value: deployed.map((p) => (p.channel_id ? `${p.id} on ${p.channel_id}` : p.id)).join(', ') || 'None' },
        ],
      };
    }
  }
}
