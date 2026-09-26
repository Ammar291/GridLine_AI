import { describe, expect, it } from 'vitest';
import {
  activeThreats, cityStatus, defaultIncidentId, entityName, findOpenIncidentForZone, latestRun, preventiveActions,
  resources, riskZones, stepOutput, whatChanged, zoneName,
} from './derive';
import { fmtIndex, fmtNumber, fmtPct, fmtSimTime, fmtSimTimeSec, statusLabel, toolVerb } from './format';
import { applyEvent } from './applyEvent';
import { initialLiveState, type TelemetryPoint } from './types';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';
import { cityFixture, normalZoneState } from '@/test/fixtures/city';
import { incidentFixture, runFixture } from '@/test/fixtures/incident';
import { failedActionFixture } from '@/test/fixtures/action';

const snap = () => applyEvent(initialLiveState('mock'), snapshotEventFixture);

describe('format', () => {
  it('formats', () => {
    expect(fmtSimTime('2026-07-14T10:31:04')).toBe('10:31');
    expect(fmtSimTime(null)).toBe('—');
    expect(fmtSimTimeSec('2026-07-14T10:31:04')).toBe('10:31:04');
    expect(fmtPct(0.82)).toBe('82%');
    expect(fmtIndex(0.7149)).toBe('0.71');
    expect(fmtNumber(18500)).toBe('18,500');
    expect(toolVerb('halt_construction')).toBe('Halt construction');
    expect(toolVerb('schedule_inspection')).toBe('Schedule inspection');
    expect(toolVerb('unknown_tool')).toBe('unknown_tool');
    expect(statusLabel('en_route')).toBe('En route');
  });
});

describe('derive', () => {
  it('cityStatus returns the max band', () => {
    const s = applyEvent(snap(), eventsFixture['zone.state']);
    expect(cityStatus(s.zoneState)).toEqual({ band: 'warning', label: 'Warning' });
    expect(cityStatus({})).toEqual({ band: 'normal', label: 'Normal' });
  });
  it('resources counts crews, shelters and pumps', () => {
    expect(resources(snap().assets)).toEqual({
      crewsAvailable: 3, crewsTotal: 3, sheltersOpen: 0, shelterCapacityOpen: 0, pumpsAtDepot: 4, pumpsTotal: 4, roadsClosed: 0,
    });
    const after = applyEvent(snap(), eventsFixture['action.executed']);
    expect(resources(after.assets).crewsAvailable).toBe(2);
  });
  it('activeThreats, riskZones and preventiveActions', () => {
    const s = applyEvent(snap(), eventsFixture['zone.state']);
    expect(activeThreats(s.incidents)).toEqual([{ hazard: 'landslide', count: 1, maxBand: 'warning' }]);
    expect(riskZones(s.zoneState, s.city).map((r) => r.zone.id)).toEqual(['hillview']);
    const ghost = applyEvent(s, { ...eventsFixture['zone.state'], payload: { ...eventsFixture['zone.state'].payload, zone_id: 'ghost' } });
    expect(riskZones(ghost.zoneState, ghost.city).map((r) => r.zone.id)).toEqual(['hillview']);
    const withFailed = applyEvent(s, { ...eventsFixture['action.executed'], payload: failedActionFixture });
    expect(preventiveActions(withFailed.actions, withFailed.approvals)).toEqual({ pending: 3, executed: 2, verified: 1, failed: 1 });
  });
  it('defaultIncidentId picks the critical open one over a watch one', () => {
    const incidents = {
      a: { ...incidentFixture, id: 'a', band: 'watch' as const, opened_sim_time: '2026-07-14T08:00:00' },
      b: { ...incidentFixture, id: 'b', band: 'critical' as const, opened_sim_time: '2026-07-14T09:00:00' },
      c: { ...incidentFixture, id: 'c', band: 'critical' as const, status: 'closed' as const, opened_sim_time: '2026-07-14T07:00:00' },
    };
    expect(defaultIncidentId(incidents)).toBe('b');
    expect(defaultIncidentId({})).toBeNull();
  });
  it('latestRun and stepOutput', () => {
    expect(latestRun(incidentFixture)?.id).toBe('run_1');
    expect(latestRun(undefined)).toBeUndefined();
    expect(stepOutput(runFixture, 'assess')?.confidence).toBe(0.72);
    expect(stepOutput(undefined, 'assess')).toBeNull();
  });
  it('whatChanged lists band transition and reading delta', () => {
    const p = (landslide: number, band: TelemetryPoint['band'], simTime: string): TelemetryPoint => ({
      simTime, tick: 0, rain: 40, saturation: 0.6, landslide, flood: 0.05, band,
    });
    const w = whatChanged(incidentFixture, runFixture, [p(0.4, 'watch', '2026-07-14T10:00:00'), p(0.61, 'warning', '2026-07-14T10:05:00')], cityFixture);
    expect(w.trigger).toBe('band_change');
    expect(w.replanReason).toBeNull();
    expect(w.bandTransitions).toEqual(['Watch → Warning']);
    expect(w.readingDeltas).toEqual([{ label: 'Landslide index', from: '0.40', to: '0.61' }]);
  });
  it('names and incident lookup', () => {
    const s = snap();
    expect(zoneName(cityFixture, 'old_town')).toBe('Old Town');
    expect(zoneName(null, 'ghost')).toBe('ghost');
    expect(entityName(s.assets, 'crew', 'c3')).toBe('Rescue Team 03');
    expect(entityName(s.assets, 'road', 'b04')).toBe('Kalinadi Bridge B-04');
    expect(entityName(s.assets, 'pump_unit', 'p1')).toBe('p1');
    expect(findOpenIncidentForZone(s.incidents, 'hillview')).toBe('inc_1');
    expect(findOpenIncidentForZone(s.incidents, 'riverside')).toBeNull();
    expect(normalZoneState.band).toBe('normal');
  });
});
