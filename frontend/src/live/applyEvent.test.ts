import { describe, expect, it } from 'vitest';
import { applyEvent } from './applyEvent';
import { initialLiveState, FEED_CAP } from './types';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';
import type { Event } from '@/api/types';

const base = () => applyEvent(initialLiveState('mock'), snapshotEventFixture);

describe('applyEvent', () => {
  it('snapshot replaces everything and sets hasSnapshot', () => {
    const s = base();
    expect(s.hasSnapshot).toBe(true);
    expect(Object.keys(s.zoneState)).toHaveLength(6);
    expect(Object.keys(s.incidents)).toEqual(['inc_1']);
    expect(Object.keys(s.approvals)).toEqual(['appr_1']);
    expect(s.assets.crews.c3?.status).toBe('available');
  });
  it('a later snapshot replaces, not merges (reconnect)', () => {
    let s = base();
    s = applyEvent(s, eventsFixture['approval.requested']);
    const snap: Event = { ...snapshotEventFixture, payload: { ...snapshotEventFixture.payload, approvals: [] } };
    s = applyEvent(s, snap);
    expect(Object.keys(s.approvals)).toEqual([]);
    expect(s.feed.at(-1)?.type).toBe('state.snapshot');
  });
  it('zone.state updates band and appends telemetry; band change adds a milestone', () => {
    const s = applyEvent(base(), eventsFixture['zone.state']);
    expect(s.zoneState.hillview?.band).toBe('warning');
    expect(s.telemetry.hillview?.at(-1)?.landslide).toBeCloseTo(0.61);
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'band', zoneId: 'hillview', band: 'warning' });
  });
  it('zone.state for an unknown zone is stored but does not throw', () => {
    const e: Event = { ...eventsFixture['zone.state'], payload: { ...eventsFixture['zone.state'].payload, zone_id: 'ghost' } };
    expect(() => applyEvent(base(), e)).not.toThrow();
  });
  it('agent.node.started then finished adds then replaces a step', () => {
    let s = applyEvent(base(), eventsFixture['agent.run.started']);
    s = applyEvent(s, eventsFixture['agent.node.started']);
    const run = () => s.incidents.inc_1?.runs.find(r => r.id === eventsFixture['agent.node.started'].payload.run_id);
    expect(run()?.steps.at(-1)?.status).toBe('running');
    s = applyEvent(s, eventsFixture['agent.node.finished']);
    const finished = eventsFixture['agent.node.finished'].payload;
    expect(run()?.steps.filter(st => st.id === finished.id)).toHaveLength(1);
    expect(run()?.steps.find(st => st.id === finished.id)?.status).toBe('finished');
  });
  it('agent.node.finished for an unknown run creates a stub run', () => {
    const e: Event = { ...eventsFixture['agent.node.finished'], payload: { ...eventsFixture['agent.node.finished'].payload, run_id: 'run_ghost' } };
    const s = applyEvent(base(), e);
    expect(s.incidents.inc_1?.runs.some(r => r.id === 'run_ghost')).toBe(true);
  });
  it('approval.requested and decided update both maps', () => {
    let s = applyEvent(base(), eventsFixture['approval.requested']);
    const id = eventsFixture['approval.requested'].payload.id;
    expect(s.approvals[id]?.status).toBe('pending');
    s = applyEvent(s, eventsFixture['approval.decided']);
    expect(s.approvals[id]?.status).toBe(eventsFixture['approval.decided'].payload.status);
    expect(s.incidents.inc_1?.approvals.find(a => a.id === id)?.status).toBe(eventsFixture['approval.decided'].payload.status);
  });
  it('action.executed applies state_changes to assets and adds a milestone', () => {
    const s = applyEvent(base(), eventsFixture['action.executed']);
    expect(s.assets.crews.c3?.status).toBe('dispatched');
    expect(s.milestones.at(-1)?.kind).toBe('action');
  });
  it('action.verified attaches verification', () => {
    let s = applyEvent(base(), eventsFixture['action.executed']);
    s = applyEvent(s, eventsFixture['action.verified']);
    const id = eventsFixture['action.verified'].payload.action_id;
    expect(s.actions[id]?.verification?.status).toBe(eventsFixture['action.verified'].payload.verification.status);
  });
  it('feed is capped', () => {
    let s = base();
    for (let i = 0; i < FEED_CAP + 20; i++) s = applyEvent(s, { ...eventsFixture['sim.tick'], id: `t${String(i)}` });
    expect(s.feed).toHaveLength(FEED_CAP);
    expect(s.feed.at(-1)?.id).toBe(`t${String(FEED_CAP + 19)}`);
  });
  it('unknown event type is appended to the feed and otherwise ignored', () => {
    const weird = { ...eventsFixture['sim.tick'], type: 'future.thing' } as unknown as Event;
    const before = base();
    const s = applyEvent(before, weird);
    expect(s.feed.at(-1)?.type).toBe('future.thing');
    expect(s.zoneState).toBe(before.zoneState);
  });
  it('threat.escalated raises the band of the incident it names', () => {
    const e: Event = { ...eventsFixture['threat.escalated'], payload: { ...eventsFixture['threat.escalated'].payload, band: 'critical' } };
    const s = applyEvent(base(), e);
    expect(s.incidents.inc_1?.band).toBe('critical');
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'band', incidentId: 'inc_1', band: 'critical' });
  });
  it('replan.triggered adds a replan milestone that names the run', () => {
    const s = applyEvent(base(), eventsFixture['replan.triggered']);
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'replan', incidentId: 'inc_1', runId: 'run_1' });
  });
  it('sensor.reading updates the sensor last value', () => {
    const s = applyEvent(base(), eventsFixture['sensor.reading']);
    expect(s.assets.sensors['RG-02']?.last_value).toBe(84);
  });
});

describe('useLiveStore', () => {
  it('dispatch runs the reducer and resetLive keeps the actions', async () => {
    const { useLiveStore } = await import('./liveStore');
    useLiveStore.getState().dispatch(snapshotEventFixture);
    expect(useLiveStore.getState().hasSnapshot).toBe(true);
    useLiveStore.getState().setConnection('reconnecting');
    expect(useLiveStore.getState().connection).toBe('reconnecting');
    useLiveStore.getState().resetLive();
    expect(useLiveStore.getState().hasSnapshot).toBe(false);
    expect(typeof useLiveStore.getState().dispatch).toBe('function');
  });
});
