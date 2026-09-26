import { describe, expect, it } from 'vitest';
import type { Incident } from '@/api/types';
import type { Milestone, TelemetryPoint } from '@/live/types';
import { incidentFixture } from '@/test/fixtures/incident';
import { cityFixture } from '@/test/fixtures/city';
import { buildRows, groupMarkers, milestoneMarkers, thresholdLines, timelineHazard } from './timelineData';

const point = (simTime: string, landslide: number, flood = 0.1): TelemetryPoint => ({
  simTime, tick: 0, rain: 40, saturation: 0.5, landslide, flood, band: 'normal',
});

const milestone = (id: string, simTime: string | null, m: Partial<Milestone> = {}): Milestone => ({
  id, kind: 'band', simTime, ts: '2026-09-26T10:00:00Z', label: `fixture: ${id}`, ...m,
});

describe('buildRows', () => {
  it('maps telemetry fields and labels HH:mm', () => {
    expect(buildRows([point('2026-07-14T10:05:00', 0.4)])).toEqual([
      { simTime: '2026-07-14T10:05:00', label: '10:05', rain: 40, saturation: 0.5, landslide: 0.4, flood: 0.1 },
    ]);
  });
  it('keeps the last reading when a sim time repeats', () => {
    const rows = buildRows([point('2026-07-14T10:00:00', 0.3), point('2026-07-14T10:00:00', 0.35), point('2026-07-14T10:05:00', 0.4)]);
    expect(rows.map((r) => r.landslide)).toEqual([0.35, 0.4]);
  });
});

describe('milestoneMarkers', () => {
  const rows = buildRows([point('2026-07-14T10:00:00', 0.3), point('2026-07-14T10:05:00', 0.4)]);
  const incidents: Record<string, Incident> = { inc_1: incidentFixture };

  it('keeps milestones for the zone whose sim time exists in the rows', () => {
    const markers = milestoneMarkers([
      milestone('m1', '2026-07-14T10:05:00', { zoneId: 'hillview' }),
      milestone('m2', '2026-07-14T10:05:00', { zoneId: 'riverside' }),
      milestone('m3', '2026-07-14T10:07:00', { zoneId: 'hillview' }),
      milestone('m4', null, { zoneId: 'hillview' }),
    ], 'hillview', rows);
    expect(markers).toEqual([{ id: 'm1', simTime: '2026-07-14T10:05:00', label: 'fixture: m1', kind: 'band' }]);
  });

  it("includes zone-less milestones of the zone's incidents when incidents are given", () => {
    const ms = [milestone('a1', '2026-07-14T10:00:00', { kind: 'approval', incidentId: 'inc_1' })];
    expect(milestoneMarkers(ms, 'hillview', rows, incidents).map((m) => m.id)).toEqual(['a1']);
    expect(milestoneMarkers(ms, 'riverside', rows, incidents)).toEqual([]);
    expect(milestoneMarkers(ms, 'hillview', rows)).toEqual([]);
  });

  it('a milestone that names another zone stays with that zone even when it carries this zone\'s incident', () => {
    const ms = [milestone('t1', '2026-07-14T10:00:00', { zoneId: 'riverside', incidentId: 'inc_1' })];
    expect(milestoneMarkers(ms, 'hillview', rows, incidents)).toEqual([]);
    expect(milestoneMarkers(ms, 'riverside', rows, incidents).map((m) => m.id)).toEqual(['t1']);
  });

  it('groups markers that share a sim time into one, keeping every label', () => {
    const t = '2026-07-14T10:05:00';
    expect(groupMarkers([
      { id: 'a', simTime: t, label: 'Hillview: Warning', kind: 'band' },
      { id: 'b', simTime: t, label: 'Threat escalated', kind: 'band' },
      { id: 'c', simTime: '2026-07-14T10:00:00', label: 'Approval requested', kind: 'approval' },
    ])).toEqual([
      { simTime: t, kind: 'band', labels: ['Hillview: Warning', 'Threat escalated'] },
      { simTime: '2026-07-14T10:00:00', kind: 'approval', labels: ['Approval requested'] },
    ]);
  });
});

describe('thresholds and hazard', () => {
  it('labels thresholds by band with two decimals', () => {
    expect(thresholdLines(cityFixture.bands, 'landslide').map((t) => t.label)).toEqual(['Watch 0.35', 'Warning 0.55', 'Critical 0.75']);
    expect(thresholdLines(cityFixture.bands, 'flood').map((t) => t.value)).toEqual([0.3, 0.5, 0.7]);
    expect(thresholdLines(undefined, 'flood')).toEqual([]);
  });
  it("uses the zone's open incident hazard, else the leading index, else landslide", () => {
    const incidents: Record<string, Incident> = { inc_1: incidentFixture };
    expect(timelineHazard('hillview', incidents, [])).toBe('landslide');
    expect(timelineHazard('riverside', incidents, buildRows([point('2026-07-14T10:00:00', 0.1, 0.4)]))).toBe('flood');
    expect(timelineHazard('riverside', {}, [])).toBe('landslide');
  });
});
