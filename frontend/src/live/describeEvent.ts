import type { City, Event } from '@/api/types';
import { bandLabel } from '@/components/ui/bandLabel';
import { NODE_LABELS, statusLabel, toolVerb } from './format';

export type EventGroup = 'simulation' | 'threat' | 'agent' | 'approval' | 'action' | 'alert';

export function eventGroup(type: string): EventGroup {
  if (type.startsWith('threat.') || type.startsWith('incident.')) return 'threat';
  if (type.startsWith('agent.') || type === 'replan.triggered') return 'agent';
  if (type.startsWith('approval.')) return 'approval';
  if (type.startsWith('action.')) return 'action';
  if (type === 'alert.issued') return 'alert';
  return 'simulation';
}

function zoneName(city: City | null, zoneId: string): string {
  return city?.zones.find((z) => z.id === zoneId)?.name ?? zoneId;
}

const num = (v: number) => String(Number(v.toFixed(2)));

/** One deterministic human-readable line per event, no trailing period. */
export function describeEvent(e: Event, city: City | null): string {
  switch (e.type) {
    case 'state.snapshot':
      return 'Connected: city state received';
    case 'sim.tick':
      return `Tick ${String(e.payload.tick)} at ${e.payload.sim_time.slice(11, 16)}`;
    case 'sensor.reading': {
      const p = e.payload;
      const where = `${p.sensor_id} (${zoneName(city, p.zone_id)})`;
      if (p.kind === 'rain') return `Rainfall ${where} ${num(p.value)} mm/h`;
      if (p.kind === 'soil') return `Soil moisture ${where} ${num(p.value)}%`;
      return `Channel level ${where} ${num(p.value)} m`;
    }
    case 'zone.state': {
      const p = e.payload;
      const zone = zoneName(city, p.zone_id);
      if (p.prev_band == null || p.prev_band === p.band) {
        return `${zone}: landslide index ${p.landslide_index.toFixed(2)}, flood index ${p.flood_index.toFixed(2)}`;
      }
      const landslideLeads = p.landslide_index >= p.flood_index;
      const hazard = landslideLeads ? 'landslide' : 'flood';
      const index = landslideLeads ? p.landslide_index : p.flood_index;
      return `${zone}: ${hazard} index ${index.toFixed(2)}, ${bandLabel(p.prev_band)} → ${bandLabel(p.band)}`;
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
    case 'alert.issued':
      return `Alert (${e.payload.level}) for ${zoneName(city, e.payload.zone_id)}: ${e.payload.message}`;
    case 'scenario.event':
      return e.payload.description;
    default:
      return (e as { type: string }).type;
  }
}
