import { describe, expect, it } from 'vitest';
import { buildReplay, simTimeAt } from './replay';
import { nandipurCity } from './MockApiClient';

describe('replay', () => {
  const steps = buildReplay(nandipurCity);
  const all = steps.flatMap((s) => s.events);

  it('has 72 ticks starting at tick 1, each ending with sim.tick as the backend does', () => {
    expect(steps).toHaveLength(72);
    expect(steps[0]?.tick).toBe(1);
    expect(steps.every((s) => s.events.at(-1)?.event_type === 'sim.tick')).toBe(true);
  });
  it('is deterministic', () => { expect(JSON.stringify(buildReplay(nandipurCity))).toBe(JSON.stringify(steps)); });
  it('uses the backend envelope on every event', () => {
    for (const e of all) {
      expect(Object.keys(e).sort()).toEqual(
        ['event_id', 'event_type', 'incident_id', 'location', 'payload', 'severity', 'sim_time', 'source', 'timestamp'],
      );
    }
    expect(new Set(all.map((e) => e.event_id)).size).toBe(all.length);
  });
  it('enters the scenario stage the city lists at its start tick', () => {
    const stages = all.flatMap((e) => (e.event_type === 'scenario.stage' ? [e.payload] : []));
    expect(stages.map((s) => s.stage)).toEqual(['intensifying_rain']);
    expect(stages[0]?.tick).toBe(nandipurCity.scenarios.find((s) => s.name === 'hillside_landslide')?.stages[1]?.start_tick);
  });
  it('rain gauges report rising rain and soil probes rising saturation', () => {
    const rg02 = all.flatMap((e) => (e.event_type === 'weather.observation' && e.payload.station_id === 'RG-02' ? [e.payload.rainfall_intensity_mm_h ?? 0] : []));
    expect(rg02).toHaveLength(72);
    expect(rg02.at(-1)).toBeGreaterThan(rg02[0] ?? 0);
    const sm01 = all.flatMap((e) => (e.event_type === 'environment.soil' && e.payload.probe_id === 'SM-01' ? [e.payload.saturation] : []));
    expect(sm01.at(-1)).toBeGreaterThan(sm01[0] ?? 1);
  });
  it('PENDING detector: opens one incident when Hillview enters watch and escalates through warning to critical', () => {
    expect(all.filter((e) => e.event_type === 'incident.opened')).toHaveLength(1);
    const bands = all.flatMap((e) => (e.event_type === 'threat.escalated' ? [e.payload.band] : []));
    expect(bands).toEqual(['warning', 'critical']);
  });
  it('never emits agent, approval, action or verification events', () => {
    const types = all.map((e) => e.event_type);
    expect(types.some((t) => t.startsWith('agent.') || t.startsWith('approval.') || t.startsWith('action.') || t === 'replan.triggered')).toBe(false);
  });
  it('simTimeAt adds five minutes per tick in the backend format', () => { expect(simTimeAt(12)).toBe('2026-07-14T07:00:00Z'); });
  it('uses zone and sensor ids that exist in the backend-built city', () => {
    const zoneIds = new Set(nandipurCity.zones.map((z) => z.id));
    const sensorIds = new Set(nandipurCity.sensors.map((s) => s.id));
    for (const e of all) {
      if (e.location !== null) expect(zoneIds.has(e.location)).toBe(true);
      if (e.event_type === 'zone.state') expect(zoneIds.has(e.payload.zone_id)).toBe(true);
      if (e.event_type === 'weather.observation') expect(sensorIds.has(e.payload.station_id)).toBe(true);
      if (e.event_type === 'environment.soil') expect(sensorIds.has(e.payload.probe_id)).toBe(true);
    }
  });
});
