import { describe, expect, it } from 'vitest';
import { buildReplay, simTimeAt } from './replay';
import { nandipurCity } from './MockApiClient';

describe('replay', () => {
  const steps = buildReplay(nandipurCity);
  it('has 72 ticks starting at tick 1 with a sim.tick first in each', () => {
    expect(steps).toHaveLength(72);
    expect(steps[0]?.tick).toBe(1);
    expect(steps.every(s => s.events[0]?.type === 'sim.tick')).toBe(true);
  });
  it('is deterministic', () => { expect(JSON.stringify(buildReplay(nandipurCity))).toBe(JSON.stringify(steps)); });
  it('opens one incident when hillview enters watch and escalates through warning to critical', () => {
    const all = steps.flatMap(s => s.events);
    const opened = all.filter(e => e.type === 'incident.opened');
    expect(opened).toHaveLength(1);
    const bands = all.flatMap(e => (e.type === 'threat.escalated' ? [e.payload.band] : []));
    expect(bands).toEqual(['warning', 'critical']);
  });
  it('never emits agent, approval, action or verification events', () => {
    const all = steps.flatMap(s => s.events).map(e => e.type);
    expect(all.some(t => t.startsWith('agent.') || t.startsWith('approval.') || t.startsWith('action.') || t === 'replan.triggered')).toBe(false);
  });
  it('simTimeAt adds five minutes per tick', () => { expect(simTimeAt(12)).toBe('2026-07-14T07:00:00'); });
  it('uses zone and sensor ids that exist in the mock city', () => {
    const zoneIds = new Set(nandipurCity.zones.map(z => z.id));
    const sensorIds = new Set(nandipurCity.sensors.map(s => s.id));
    for (const e of steps.flatMap(s => s.events)) {
      if (e.type === 'zone.state') expect(zoneIds.has(e.payload.zone_id)).toBe(true);
      if (e.type === 'sensor.reading') expect(sensorIds.has(e.payload.sensor_id)).toBe(true);
    }
  });
});
