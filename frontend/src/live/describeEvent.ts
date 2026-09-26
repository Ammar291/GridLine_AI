import type { City, Event } from '@/api/types';
import { bandLabel } from '@/components/ui/bandLabel';
import { sentenceLabel } from '@/components/workflow/labels';
import { NODE_LABELS, statusLabel, toolVerb } from './format';

export type EventGroup = 'simulation' | 'reading' | 'city' | 'threat' | 'agent' | 'approval' | 'action' | 'alert';

export function eventGroup(type: string): EventGroup {
  if (type.startsWith('weather.observation') || type.startsWith('environment.')) return 'reading';
  if (type.startsWith('infrastructure.') || type.startsWith('emergency.') || type === 'weather.forecast' || type === 'weather.rainfall') {
    return 'city';
  }
  if (type.startsWith('threat.') || type.startsWith('incident.') || type === 'zone.state') return 'threat';
  if (type.startsWith('agent.') || type === 'replan.triggered') return 'agent';
  if (type.startsWith('approval.')) return 'approval';
  if (type.startsWith('action.')) return 'action';
  if (type === 'alert.issued') return 'alert';
  return 'simulation';
}

const nameIn = (list: readonly { id: string; name: string }[] | undefined, id: string) => list?.find((x) => x.id === id)?.name;
const zoneName = (city: City | null, id: string | null | undefined) => (id == null ? 'the city' : (nameIn(city?.zones, id) ?? id));
const num = (v: number, digits = 1) => String(Number(v.toFixed(digits)));
const pct = (fraction: number) => `${String(Math.round(fraction * 100))}%`;
const withName = (id: string, name: string | undefined) => (name && name !== id ? `${id} ${name}` : id);
const reason = (text: string) => (text ? `: ${text}` : '');

/** One deterministic human-readable line per event, no trailing period. */
export function describeEvent(e: Event, city: City | null): string {
  switch (e.event_type) {
    case 'sim.snapshot':
      return 'Connected: city state received';
    case 'sim.heartbeat':
      return 'Heartbeat';
    case 'sim.tick':
      return `Tick ${String(e.payload.tick)} at ${e.payload.sim_time.slice(11, 16)}`;
    case 'sim.status': {
      const p = e.payload;
      return `Simulation ${p.state}: ${p.scenario.replace(/_/g, ' ')}, ${String(p.speed)}×, tick ${String(p.tick)}`;
    }
    case 'source.status': {
      const p = e.payload;
      return p.last_error ? `${p.label}: refresh failed (${p.last_error})` : `Data source: ${p.label} (${p.provider})`;
    }
    case 'scenario.trigger':
      return `Demo event: ${e.payload.label}`;
    case 'scenario.stage':
      return `Stage ${String(e.payload.stage_index + 1)}: ${e.payload.description}`;
    case 'weather.observation': {
      const p = e.payload;
      const where = `${p.station_id} (${zoneName(city, e.location)})`;
      if (p.rainfall_intensity_mm_h != null) {
        const day = p.cumulative_rainfall_24h_mm == null ? '' : `, ${num(p.cumulative_rainfall_24h_mm, 0)} mm in 24 h`;
        return `Rainfall ${where} ${num(p.rainfall_intensity_mm_h)} mm/h${day}`;
      }
      const temp = p.temperature_c == null ? '' : `, ${num(p.temperature_c)} °C`;
      return `Weather ${where} wind ${num(p.wind_speed_kmh ?? 0)} km/h${temp}`;
    }
    case 'weather.forecast':
      return `Forecast: ${e.payload.summary} (peak ${num(e.payload.peak_intensity_mm_h)} mm/h)`;
    case 'weather.rainfall': {
      const p = e.payload;
      const where = p.zone_ids.length === 0 ? 'the whole city' : p.zone_ids.map((id) => zoneName(city, id)).join(', ');
      return `Rain ${num(p.intensity_mm_h)} mm/h for ${num(p.duration_h)} h over ${where}${reason(p.description)}`;
    }
    case 'emergency.fire': {
      const p = e.payload;
      const people = p.exposed_population.toLocaleString('en-US');
      return `Fire at ${p.site} in ${zoneName(city, p.zone_id)}: ${people} people exposed in ${String(p.exposed_zone_ids.length)} zones`;
    }
    case 'environment.soil':
      return `Soil moisture ${e.payload.probe_id} (${zoneName(city, e.location)}) ${pct(e.payload.saturation)} saturated`;
    case 'environment.river': {
      const p = e.payload;
      const river = city?.map_features.find((f) => f.id === p.river_id)?.label ?? p.river_id;
      return `River level ${p.gauge_id} (${river}) ${num(p.level_m, 2)} m, ${p.trend}`;
    }
    case 'environment.drainage': {
      const p = e.payload;
      const overflow = p.overflow_m3s > 0 ? `, overflowing ${num(p.overflow_m3s)} m³/s` : '';
      return `Drain ${p.channel_id}: ${num(p.flow_m3s)} of ${num(p.capacity_m3s)} m³/s (${pct(p.load_ratio)})${overflow}`;
    }
    case 'environment.slope': {
      const p = e.payload;
      return `Slope ${withName(p.slope_id, nameIn(city?.slopes, p.slope_id))} moving ${num(p.movement_rate_mm_h)} mm/h, ${num(p.cumulative_movement_mm, 0)} mm total`;
    }
    case 'environment.water_accumulation':
      return `Standing water in ${zoneName(city, e.payload.zone_id)} ${num(e.payload.depth_cm)} cm, ${e.payload.trend}`;
    case 'infrastructure.road':
      return `${nameIn(city?.roads, e.payload.road_id) ?? e.payload.road_id} ${e.payload.status}${reason(e.payload.reason)}`;
    case 'infrastructure.bridge':
      return `${nameIn(city?.bridges, e.payload.bridge_id) ?? e.payload.bridge_id} ${e.payload.status}${reason(e.payload.reason)}`;
    case 'infrastructure.drainage_obstruction':
      return `Drain ${e.payload.channel_id} ${pct(e.payload.blocked_fraction)} blocked${reason(e.payload.cause)}`;
    case 'infrastructure.construction': {
      const p = e.payload;
      const name = nameIn(city?.projects, p.project_id) ?? p.project_id;
      return `${name} ${p.activity}, ${num(p.excavation_depth_m)} of ${num(p.planned_depth_m)} m dug`;
    }
    case 'infrastructure.failure':
      return `${statusLabel(e.payload.failure_kind)} at ${e.payload.asset_id}: ${e.payload.description}`;
    case 'emergency.rescue_team': {
      const p = e.payload;
      const crew = withName(p.crew_id, nameIn(city?.crews, p.crew_id));
      return `${crew} ${statusLabel(p.status).toLowerCase()} in ${zoneName(city, p.location_zone_id)}${reason(p.task)}`;
    }
    case 'emergency.ambulance': {
      const p = e.payload;
      return `Ambulance ${p.ambulance_id} ${p.status} in ${zoneName(city, p.location_zone_id)} (${String(p.available_count)} of ${String(p.total_count)} available)`;
    }
    case 'emergency.hospital': {
      const p = e.payload;
      const name = nameIn(city?.hospitals, p.hospital_id) ?? p.hospital_id;
      return `${name}: ${String(p.beds_occupied)} of ${String(p.beds_total)} beds occupied, ER ${p.er_status}`;
    }
    case 'emergency.shelter': {
      const p = e.payload;
      const name = nameIn(city?.shelters, p.shelter_id) ?? p.shelter_id;
      return `${name} ${p.status}: ${String(p.occupancy)} of ${String(p.capacity)} places used`;
    }
    // ---- PENDING events (later milestones) ----
    case 'zone.state': {
      const p = e.payload;
      const zone = zoneName(city, p.zone_id);
      if (p.prev_band == null || p.prev_band === p.band) {
        return `${zone}: landslide index ${p.landslide_index.toFixed(2)}, flood index ${p.flood_index.toFixed(2)}`;
      }
      const landslideLeads = p.landslide_index >= p.flood_index;
      const index = landslideLeads ? p.landslide_index : p.flood_index;
      return `${zone}: ${landslideLeads ? 'landslide' : 'flood'} index ${index.toFixed(2)}, ${bandLabel(p.prev_band)} → ${bandLabel(p.band)}`;
    }
    case 'threat.detected':
      return `Threat detected: ${e.payload.hazard} risk in ${zoneName(city, e.payload.zone_id)} (${bandLabel(e.payload.band)})`;
    case 'threat.escalated': {
      const p = e.payload;
      const from = p.prev_band == null ? '' : `${bandLabel(p.prev_band)} → `;
      return `Threat escalated: ${p.hazard} in ${zoneName(city, p.zone_id)}, ${from}${bandLabel(p.band)}`;
    }
    case 'incident.opened':
      return `Incident opened: ${e.payload.hazard} risk in ${zoneName(city, e.payload.zone_id)} (${bandLabel(e.payload.band)})`;
    case 'incident.closed':
      return `Incident closed: ${e.payload.hazard} in ${zoneName(city, e.payload.zone_id)}`;
    case 'agent.run.started': {
      const p = e.payload;
      return `Agent run started (${p.trigger})${p.replan_reason ? `, re-plan: ${p.replan_reason}` : ''}`;
    }
    case 'agent.run.finished':
      return `Agent run ${statusLabel(e.payload.status).toLowerCase()}`;
    case 'agent.node.started':
      return `${NODE_LABELS[e.payload.node]} started`;
    case 'agent.node.finished':
      return `${NODE_LABELS[e.payload.node]} finished${e.payload.status === 'ungrounded' ? ' (ungrounded)' : ''}`;
    case 'approval.requested': {
      const n = e.payload.proposed_actions.length;
      return `Approval requested for ${String(n)} ${n === 1 ? 'action' : 'actions'}`;
    }
    case 'approval.decided': {
      const p = e.payload;
      return `Approval ${p.status}${p.decided_by ? ` by ${p.decided_by}` : ''}${p.synthetic ? ' (auto)' : ''}`;
    }
    case 'action.executed': {
      const first = e.payload.state_changes[0];
      const change = first ? `: ${first.entity_name} ${statusLabel(first.from)} → ${statusLabel(first.to)}` : '';
      return `${toolVerb(e.payload.tool)} executed${change}`;
    }
    case 'action.verified':
      return `Action ${e.payload.action_id} ${statusLabel(e.payload.verification.status).toLowerCase()}`;
    case 'replan.triggered':
      return `Re-planning: ${e.payload.reason}`;
    case 'agent.step': {
      const p = e.payload;
      return `Agent: ${sentenceLabel(p.node)} ${p.status}${p.error ? ` (${p.error})` : ''}`;
    }
    case 'alert.issued':
      return `Alert (${e.payload.level}) for ${zoneName(city, e.payload.zone_id)}: ${e.payload.message}`;
    default:
      return (e as { event_type: string }).event_type;
  }
}
