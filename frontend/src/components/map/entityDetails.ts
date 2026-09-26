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
      const c = z.conditions;
      const s = z.state;
      return {
        title: z.zone.name, kindLabel: 'Zone', band: s?.band,
        items: [
          { label: 'Population', value: fmtNumber(z.zone.population) },
          { label: 'Slope', value: `${trim(z.zone.slope_deg)}°` },
          ...(c ? [
            { label: 'Saturation', value: fmtPct(c.saturation) },
            { label: 'Rain intensity', value: `${trim(c.rainfall_intensity_mm_h)} mm/h` },
            { label: 'Rain, 24 h', value: `${trim(c.rain_24h_mm)} mm` },
            { label: 'Standing water', value: `${trim(c.water_depth_cm)} cm` },
          ] : []),
          ...(s ? [
            { label: 'Landslide index', value: fmtIndex(s.landslide_index) },
            { label: 'Flood index', value: fmtIndex(s.flood_index) },
          ] : []),
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
          { label: 'Base', value: zone(c.base_zone_id) },
          { label: 'Task', value: c.task || 'None' },
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
          { label: 'Status', value: `${statusLabel(r.status)}${r.reason ? `: ${r.reason}` : ''}` },
          { label: 'Evacuation route', value: yesNo(r.is_evacuation_route) },
          { label: 'Only access', value: yesNo(r.is_only_access) },
          { label: 'Zones', value: r.zone_ids.map(zone).join(', ') || 'None' },
        ],
      };
    }
    case 'bridge': {
      const b = data.bridges.find((x) => x.id === ref.id);
      if (!b) return null;
      const road = data.roads.find((r) => r.id === b.road_id)?.name ?? b.road_id;
      const crosses = data.features.find((f) => f.id === b.crosses_id)?.label ?? data.channels.find((c) => c.id === b.crosses_id)?.name;
      return {
        title: b.name, kindLabel: 'Bridge',
        items: [
          { label: 'Status', value: `${statusLabel(b.status)}${b.reason ? `: ${b.reason}` : ''}` },
          { label: 'Carries', value: road },
          { label: 'Crosses', value: crosses ?? b.crosses_id },
          { label: 'Zone', value: zone(b.zone_id) },
        ],
      };
    }
    case 'channel': {
      const c = data.channels.find((x) => x.id === ref.id);
      if (!c) return null;
      return {
        title: c.name, kindLabel: 'Drainage channel',
        items: [
          { label: 'Flow', value: `${trim(c.flow_m3s)} of ${trim(c.capacity_m3s)} m³/s` },
          { label: 'Design capacity', value: `${trim(c.design_capacity_m3s)} m³/s` },
          { label: 'Blocked', value: `${fmtPct(c.blocked_fraction)}${c.blocked_fraction > BLOCKED_THRESHOLD ? ', over limit' : ''}` },
          { label: 'Overflow', value: `${trim(c.overflow_m3s)} m³/s` },
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
          { label: 'Status', value: `${statusLabel(p.status)}, ${p.activity}` },
          { label: 'Excavation', value: `${trim(p.excavation_depth_m)} of ${trim(p.planned_depth_m)} m` },
          { label: 'Permit', value: p.permit_number ?? 'None on file' },
          { label: 'Zone', value: zone(p.zone_id) },
        ],
      };
    }
    case 'hospital': {
      const h = data.hospitals.find((x) => x.id === ref.id);
      if (!h) return null;
      return {
        title: h.name, kindLabel: 'Hospital',
        items: [
          { label: 'Beds occupied', value: `${fmtNumber(h.beds_occupied)} of ${fmtNumber(h.beds_total)}` },
          { label: 'Emergency room', value: statusLabel(h.er_status) },
          { label: 'Zone', value: zone(h.zone_id) },
        ],
      };
    }
    case 'sensor': {
      const s = data.sensors.find((x) => x.id === ref.id);
      if (!s) return null;
      return {
        title: `${s.id} ${s.name}`, kindLabel: `${statusLabel(s.kind)} sensor`,
        items: [
          { label: 'Last reading', value: s.reading?.text ?? 'No reading yet' },
          { label: 'Zone', value: zone(s.zone_id) },
        ],
      };
    }
    case 'pump_depot': {
      const units = data.depot.units;
      const available = units.filter((p) => p.status === 'available');
      return {
        title: 'Pump depot', kindLabel: 'Mobile pumps',
        items: [
          { label: 'Available', value: `${String(available.length)} of ${String(units.length)}` },
          { label: 'Zone', value: zone(data.depot.zone_id) },
          { label: 'Capacity each', value: units[0] ? `${trim(units[0].capacity_m3s)} m³/s` : 'None' },
        ],
      };
    }
  }
}
