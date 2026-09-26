import { describe, expect, it } from 'vitest';
import type { Event, EventOf } from './types';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';
import { cityFixture } from '@/test/fixtures/city';
import { incidentFixture } from '@/test/fixtures/incident';

describe('generated contract', () => {
  it('event union discriminates on type', () => {
    const e = eventsFixture['zone.state'] as Event; // widen so the narrowing below is exercised
    if (e.type === 'zone.state') {
      const p: EventOf<'zone.state'>['payload'] = e.payload;
      expect(p.zone_id).toBe('hillview');
    } else { throw new Error('wrong type'); }
  });
  it('fixtures carry every event type', () => {
    expect(Object.keys(eventsFixture).sort()).toEqual([
      'action.executed','action.verified','agent.node.finished','agent.node.started','agent.run.finished','agent.run.started',
      'alert.issued','approval.decided','approval.requested','incident.closed','incident.opened','replan.triggered',
      'scenario.event','sensor.reading','sim.tick','state.snapshot','threat.detected','threat.escalated','zone.state'].sort());
    expect(snapshotEventFixture.type).toBe('state.snapshot');
  });
  it('city fixture has six zones and a run with ten steps', () => {
    expect(cityFixture.zones.map(z => z.id)).toEqual(['hillview','riverside','old_town','market_ward','station_road','lakeside']);
    expect(incidentFixture.runs[0]?.steps).toHaveLength(10);
  });
});
