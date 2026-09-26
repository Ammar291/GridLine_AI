import type { Bands, Hazard, Incident } from '@/api/types';
import { bandLabel } from '@/components/ui/bandLabel';
import { findOpenIncidentForZone } from '@/live/derive';
import { fmtIndex, fmtSimTime } from '@/live/format';
import type { Milestone, MilestoneKind, TelemetryPoint } from '@/live/types';

/** One chart row; a series the zone has no sensor or detector reading for is null (drawn as a gap). */
export interface TimelineRow {
  simTime: string; label: string; rain: number | null; saturation: number | null; landslide: number | null; flood: number | null;
  water: number | null;
}
export interface TimelineMarker { id: string; simTime: string; label: string; kind: MilestoneKind }
export interface ThresholdLine { band: 'watch' | 'warning' | 'critical'; value: number; label: string }

/** One row per sim time (the last reading wins), labelled HH:mm. */
export function buildRows(points: TelemetryPoint[]): TimelineRow[] {
  const rows: TimelineRow[] = [];
  for (const p of points) {
    const row = {
      simTime: p.simTime, label: fmtSimTime(p.simTime), rain: p.rain, saturation: p.saturation, landslide: p.landslide, flood: p.flood,
      water: p.water,
    };
    if (rows.at(-1)?.simTime === p.simTime) rows[rows.length - 1] = row;
    else rows.push(row);
  }
  return rows;
}

/**
 * Milestones for this zone, each placed on the first row at or after its sim time: the x axis is categorical, so a
 * marker can only sit on an existing reading (one after the last reading waits for the next). A milestone that names
 * a zone matches on that zone; one without a zone (approval, action, re-plan) matches through its incident's zone
 * when `incidents` is given; one with neither is city-wide.
 */
export function milestoneMarkers(
  milestones: Milestone[], zoneId: string, rows: TimelineRow[], incidents: Record<string, Incident> = {},
): TimelineMarker[] {
  const inZone = (m: Milestone) => {
    if (m.zoneId !== undefined) return m.zoneId === zoneId;
    if (m.incidentId !== undefined) return incidents[m.incidentId]?.zone_id === zoneId;
    return true; // city-wide (a scenario stage or a demo event): marked on every zone's chart
  };
  return milestones.flatMap((m) => {
    const at = m.simTime;
    if (at === null || !inZone(m)) return [];
    const row = rows.find((r) => r.simTime >= at);
    return row ? [{ id: m.id, simTime: row.simTime, label: m.label, kind: m.kind }] : [];
  });
}

/** One marker per sim time; the labels of every milestone at that time are kept, in order. */
export function groupMarkers(markers: TimelineMarker[]): { simTime: string; kind: MilestoneKind; labels: string[] }[] {
  const bySimTime = new Map<string, { simTime: string; kind: MilestoneKind; labels: string[] }>();
  for (const m of markers) {
    const group = bySimTime.get(m.simTime);
    if (group) group.labels.push(m.label);
    else bySimTime.set(m.simTime, { simTime: m.simTime, kind: m.kind, labels: [m.label] });
  }
  return [...bySimTime.values()];
}

export function thresholdLines(bands: Bands | undefined, hazard: Hazard): ThresholdLine[] {
  if (!bands) return [];
  const t = bands[hazard];
  return (['watch', 'warning', 'critical'] as const).map((band) => ({ band, value: t[band], label: `${bandLabel(band)} ${fmtIndex(t[band])}` }));
}

/** Whose thresholds to draw: the zone's open incident hazard, else whichever index leads at the latest reading. */
export function timelineHazard(zoneId: string, incidents: Record<string, Incident>, rows: TimelineRow[]): Hazard {
  const incidentId = findOpenIncidentForZone(incidents, zoneId);
  const incident = incidentId === null ? undefined : incidents[incidentId];
  if (incident) return incident.hazard;
  const last = rows.at(-1);
  return last && (last.flood ?? 0) > (last.landslide ?? 0) ? 'flood' : 'landslide';
}
