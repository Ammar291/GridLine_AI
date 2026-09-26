import { describe, expect, it } from 'vitest';
import type { Event, EventOf } from './types';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';
import { cityFixture } from '@/test/fixtures/city';
import { incidentFixture } from '@/test/fixtures/incident';

describe('generated contract', () => {
  it('the event union discriminates on event_type, for backend and pending events alike', () => {
    const backend = eventsFixture['weather.observation'] as Event; // widen so the narrowing below is exercised
    if (backend.event_type !== 'weather.observation') throw new Error('wrong type');
    const p: EventOf<'weather.observation'>['payload'] = backend.payload;
    expect(p.station_id).toBe('RG-02');
    const pending = eventsFixture['zone.state'] as Event;
    if (pending.event_type !== 'zone.state') throw new Error('wrong type');
    expect(pending.payload.zone_id).toBe('hillview');
  });
  it('fixtures carry every event type of the contract', () => {
    expect(Object.keys(eventsFixture).sort()).toEqual([
      // backend (openapi.json)
      'emergency.ambulance', 'emergency.fire', 'emergency.hospital', 'emergency.rescue_team', 'emergency.shelter', 'environment.drainage',
      'environment.river', 'environment.slope', 'environment.soil', 'environment.water_accumulation', 'infrastructure.bridge',
      'infrastructure.construction', 'infrastructure.drainage_obstruction', 'infrastructure.failure', 'infrastructure.road',
      'scenario.stage', 'scenario.trigger', 'sim.heartbeat', 'sim.snapshot', 'sim.status', 'sim.tick', 'source.status', 'weather.forecast',
      'weather.observation', 'weather.rainfall', 'zone.state', 'agent.step',
      // pending (openapi.pending.yaml)
      'action.executed', 'action.verified', 'agent.node.finished', 'agent.node.started', 'agent.run.finished', 'agent.run.started',
      'alert.issued', 'approval.decided', 'approval.requested', 'incident.closed', 'incident.opened', 'replan.triggered',
      'threat.detected', 'threat.escalated',
    ].sort());
    expect(snapshotEventFixture.event_type).toBe('sim.snapshot');
  });
  it('city fixture has six zones and a run with ten steps', () => {
    expect(cityFixture.zones.map((z) => z.id)).toEqual(['hillview', 'riverside', 'old_town', 'market_ward', 'station_road', 'lakeside']);
    expect(incidentFixture.runs[0]?.steps).toHaveLength(10);
  });
});
