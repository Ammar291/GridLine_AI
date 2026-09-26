import { describe, expect, it } from 'vitest';
import { describeEvent, eventGroup } from './describeEvent';
import { eventsFixture } from '@/test/fixtures/events';
import { cityFixture } from '@/test/fixtures/city';
import type { Event } from '@/api/types';

describe('describeEvent', () => {
  it('describes every fixture event type in one non-empty line', () => {
    for (const e of Object.values(eventsFixture)) {
      const line = describeEvent(e, cityFixture);
      expect(line.length).toBeGreaterThan(3);
      expect(line.includes('\n')).toBe(false);
      expect(line.endsWith('.')).toBe(false);
    }
  });
  it('specific lines', () => {
    expect(describeEvent(eventsFixture['sensor.reading'], cityFixture)).toBe('Rainfall RG-02 (Hillview) 84 mm/h');
    expect(describeEvent(eventsFixture['zone.state'], cityFixture)).toBe('Hillview: landslide index 0.61, Watch → Warning');
    expect(describeEvent(eventsFixture['action.executed'], cityFixture)).toBe('Dispatch crew executed: Rescue Team 03 Available → Dispatched');
    expect(describeEvent(eventsFixture['incident.opened'], cityFixture)).toBe('Incident opened: landslide risk in Hillview (Warning)');
    expect(describeEvent(eventsFixture['approval.requested'], cityFixture)).toBe('Approval requested for 3 actions');
    expect(eventGroup('agent.node.finished')).toBe('agent');
  });
  it('lines for the remaining types', () => {
    const d = (e: Event) => describeEvent(e, cityFixture);
    expect(d(eventsFixture['state.snapshot'])).toBe('Connected: city state received');
    expect(d(eventsFixture['sim.tick'])).toBe('Tick 13 at 10:31');
    expect(d(eventsFixture['threat.detected'])).toBe('Threat detected: landslide risk in Hillview (Watch)');
    expect(d(eventsFixture['threat.escalated'])).toBe('Threat escalated: landslide in Hillview, Watch → Warning');
    expect(d(eventsFixture['incident.closed'])).toBe('Incident closed: landslide in Hillview');
    expect(d(eventsFixture['agent.run.started'])).toBe('Agent run started (band_change)');
    expect(d(eventsFixture['agent.run.finished'])).toBe('Agent run finished');
    expect(d(eventsFixture['agent.node.started'])).toBe('Assess threat started');
    expect(d(eventsFixture['agent.node.finished'])).toBe('Assess threat finished');
    expect(d(eventsFixture['approval.decided'])).toBe('Approval partial by operator');
    expect(d(eventsFixture['action.verified'])).toBe('Action act_2 verified');
    expect(d(eventsFixture['replan.triggered'])).toBe('Re-planning: fixture: crew route blocked');
    expect(d(eventsFixture['alert.issued'])).toBe('Alert (warning) for Riverside: fixture: alert message');
    expect(d(eventsFixture['scenario.event'])).toBe('fixture: excavation reaches 4.5 m');
    expect(d({ ...eventsFixture['sim.tick'], type: 'future.thing' } as unknown as Event)).toBe('future.thing');
  });
  it('flags ungrounded steps, synthetic decisions and re-plan runs; falls back to ids for unknown zones', () => {
    const finished = eventsFixture['agent.node.finished'];
    expect(describeEvent({ ...finished, payload: { ...finished.payload, status: 'ungrounded' } }, cityFixture)).toBe('Assess threat finished (ungrounded)');
    const decided = eventsFixture['approval.decided'];
    expect(describeEvent({ ...decided, payload: { ...decided.payload, status: 'approved', decided_by: null, synthetic: true } }, cityFixture)).toBe('Approval approved (auto)');
    const started = eventsFixture['agent.run.started'];
    expect(describeEvent({ ...started, payload: { ...started.payload, trigger: 'replan', replan_reason: 'fixture: blocked' } }, cityFixture)).toBe('Agent run started (replan), re-plan: fixture: blocked');
    const reading = eventsFixture['sensor.reading'];
    expect(describeEvent({ ...reading, payload: { ...reading.payload, zone_id: 'ghost' } }, null)).toBe('Rainfall RG-02 (ghost) 84 mm/h');
  });
  it('groups event types', () => {
    expect(eventGroup('sim.tick')).toBe('simulation');
    expect(eventGroup('state.snapshot')).toBe('simulation');
    expect(eventGroup('scenario.event')).toBe('simulation');
    expect(eventGroup('threat.detected')).toBe('threat');
    expect(eventGroup('incident.opened')).toBe('threat');
    expect(eventGroup('replan.triggered')).toBe('agent');
    expect(eventGroup('approval.decided')).toBe('approval');
    expect(eventGroup('action.verified')).toBe('action');
    expect(eventGroup('alert.issued')).toBe('alert');
    expect(eventGroup('something.else')).toBe('simulation');
  });
});
