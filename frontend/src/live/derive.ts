// Pure selectors over live state. Arithmetic over what the backend sent; no inference (spec F6).
import type { AgentRun, Approval, Action, Band, City, Hazard, Incident, NodeName, StateChange, StepOutput, Zone, ZoneState } from '@/api/types';
import { bandLabel, bandRank, maxBand } from '@/components/ui/bandLabel';
import { fmtIndex, fmtPct } from './format';
import type { LiveAssets, TelemetryPoint } from './types';

export interface CityStatus { band: Band; label: string }

export function cityStatus(zoneState: Record<string, ZoneState>): CityStatus {
  const band = maxBand(Object.values(zoneState).map((z) => z.band));
  return { band, label: bandLabel(band) };
}

const openIncidents = (incidents: Record<string, Incident>) => Object.values(incidents).filter((i) => i.status === 'open');

export function activeThreats(incidents: Record<string, Incident>): { hazard: Hazard; count: number; maxBand: Band }[] {
  const by = new Map<Hazard, { hazard: Hazard; count: number; maxBand: Band }>();
  for (const i of openIncidents(incidents)) {
    const t = by.get(i.hazard) ?? { hazard: i.hazard, count: 0, maxBand: 'normal' as Band };
    by.set(i.hazard, { hazard: i.hazard, count: t.count + 1, maxBand: maxBand([t.maxBand, i.band]) });
  }
  return [...by.values()].sort((a, b) => bandRank(b.maxBand) - bandRank(a.maxBand));
}

/** Zones known to the city whose live band is watch or above, most severe first. */
export function riskZones(zoneState: Record<string, ZoneState>, city: City | null): { zone: Zone; state: ZoneState }[] {
  if (!city) return [];
  return city.zones
    .flatMap((zone) => {
      const state = zoneState[zone.id];
      return state && bandRank(state.band) >= bandRank('watch') ? [{ zone, state }] : [];
    })
    .sort((a, b) => bandRank(b.state.band) - bandRank(a.state.band));
}

export function preventiveActions(actions: Record<string, Action>, approvals: Record<string, Approval>) {
  const pending = Object.values(approvals)
    .filter((a) => a.status === 'pending')
    .reduce((n, a) => n + a.proposed_actions.length, 0);
  const list = Object.values(actions);
  return {
    pending,
    executed: list.filter((a) => a.status === 'executed').length,
    verified: list.filter((a) => a.verification?.status === 'verified').length,
    failed: list.filter((a) => a.status === 'failed' || a.verification?.status === 'failed').length,
  };
}

export function resources(assets: LiveAssets) {
  const crews = Object.values(assets.crews);
  const openShelters = Object.values(assets.shelters).filter((s) => s.status === 'open');
  return {
    crewsAvailable: crews.filter((c) => c.status === 'available').length,
    crewsTotal: crews.length,
    sheltersOpen: openShelters.length,
    shelterCapacityOpen: openShelters.reduce((n, s) => n + s.capacity, 0),
    pumpsAtDepot: assets.pumpUnits.filter((p) => p.status === 'at_depot').length,
    pumpsTotal: assets.pumpUnits.length,
    roadsClosed: Object.values(assets.roads).filter((r) => r.status === 'closed').length,
  };
}

function bySeverityThenAge(a: Incident, b: Incident): number {
  return bandRank(b.band) - bandRank(a.band) || a.opened_sim_time.localeCompare(b.opened_sim_time);
}

/** Open incident with the highest band, then the earliest opened. */
export function defaultIncidentId(incidents: Record<string, Incident>): string | null {
  return openIncidents(incidents).sort(bySeverityThenAge)[0]?.id ?? null;
}

export function findOpenIncidentForZone(incidents: Record<string, Incident>, zoneId: string): string | null {
  return openIncidents(incidents).filter((i) => i.zone_id === zoneId).sort(bySeverityThenAge)[0]?.id ?? null;
}

export function latestRun(incident: Incident | undefined): AgentRun | undefined {
  let latest: AgentRun | undefined;
  for (const r of incident?.runs ?? []) if (!latest || r.started_at >= latest.started_at) latest = r;
  return latest;
}

/** Output of the latest finished (or ungrounded) step for a node. */
export function stepOutput<N extends NodeName>(run: AgentRun | undefined, node: N): Extract<StepOutput, { node: N }> | null {
  const steps = run?.steps ?? [];
  for (let i = steps.length - 1; i >= 0; i--) {
    const s = steps[i];
    if (s?.node === node && (s.status === 'finished' || s.status === 'ungrounded') && s.output?.node === node) {
      return s.output as Extract<StepOutput, { node: N }>;
    }
  }
  return null;
}

export interface WhatChanged {
  trigger: string;
  replanReason: string | null;
  bandTransitions: string[];
  readingDeltas: { label: string; from: string; to: string }[];
}

const READINGS: { label: string; pick: (p: TelemetryPoint) => number; fmt: (x: number) => string }[] = [
  { label: 'Landslide index', pick: (p) => p.landslide, fmt: fmtIndex },
  { label: 'Flood index', pick: (p) => p.flood, fmt: fmtIndex },
  { label: 'Saturation', pick: (p) => p.saturation, fmt: fmtPct },
  { label: 'Rain intensity', pick: (p) => p.rain, fmt: (x) => `${String(Math.round(x))} mm/h` },
];

/** Band transitions and first-to-last reading deltas over the telemetry window the caller passes in. */
export function whatChanged(_incident: Incident, run: AgentRun, telemetry: TelemetryPoint[], _city: City | null): WhatChanged {
  const bandTransitions: string[] = [];
  for (let i = 1; i < telemetry.length; i++) {
    const prev = telemetry[i - 1];
    const cur = telemetry[i];
    if (prev && cur && prev.band !== cur.band) bandTransitions.push(`${bandLabel(prev.band)} → ${bandLabel(cur.band)}`);
  }
  const first = telemetry[0];
  const last = telemetry.at(-1);
  const readingDeltas =
    first && last
      ? READINGS.flatMap((r) => {
          const from = r.fmt(r.pick(first));
          const to = r.fmt(r.pick(last));
          return from === to ? [] : [{ label: r.label, from, to }];
        })
      : [];
  return { trigger: run.trigger, replanReason: run.replan_reason ?? null, bandTransitions, readingDeltas };
}

export function zoneName(city: City | null, zoneId: string): string {
  return city?.zones.find((z) => z.id === zoneId)?.name ?? zoneId;
}

export function entityName(assets: LiveAssets, entityType: StateChange['entity_type'], id: string): string {
  switch (entityType) {
    case 'crew': return assets.crews[id]?.name ?? id;
    case 'shelter': return assets.shelters[id]?.name ?? id;
    case 'road': return assets.roads[id]?.name ?? id;
    case 'project': return assets.projects[id]?.name ?? id;
    case 'channel': return assets.channels[id]?.name ?? id;
    default: return id;
  }
}
