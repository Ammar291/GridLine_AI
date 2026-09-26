import { describe, expect, it } from 'vitest';
import type { Event, EventOf } from '@/api/types';
import { eventsFixture as ev, snapshotEventFixture } from '@/test/fixtures/events';
import { liveAssets } from './assets';
import { applyEvent, applyEvents, isEngineReset } from './applyEvent';
import { FEED_CAP, initialLiveState, type LiveState } from './types';

const base = () => applyEvent(initialLiveState('mock'), snapshotEventFixture);
const opened = () => applyEvent(base(), ev['incident.opened']);
const assets = (s: LiveState) => liveAssets(s.city, s.world, s.readings);
const at = <T extends Event>(e: T, sim_time: string): T => ({ ...e, sim_time });

describe('applyEvent: DEMO controls', () => {
  it('a scenario.trigger is a city-wide timeline marker', () => {
    const s = applyEvent(base(), ev['scenario.trigger']);
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'scenario', label: 'Flash Flood', simTime: ev['scenario.trigger'].sim_time });
    expect(s.milestones.at(-1)?.zoneId).toBeUndefined();
  });

  it('an emergency.fire records the fire in the world and marks its zone', () => {
    const s = applyEvent(base(), ev['emergency.fire']);
    expect(s.world?.fires.riverside).toEqual({ site: 'fixture warehouse', exposed_zone_ids: ['riverside', 'old_town'], exposed_population: 80000 });
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'infrastructure', label: 'Fire: fixture warehouse', zoneId: 'riverside' });
  });

  it('weather.rainfall lands in the feed only', () => {
    const before = base();
    const s = applyEvent(before, ev['weather.rainfall']);
    expect(s.feed.at(-1)).toBe(ev['weather.rainfall']);
    expect(s.milestones).toEqual(before.milestones);
    expect(s.world).toEqual(before.world);
  });

  it('a zone.state without a band change is routine: a full feed drops it first', () => {
    const quiet = { ...ev['zone.state'], event_id: 'quiet', payload: { ...ev['zone.state'].payload, prev_band: 'warning' as const } };
    let s = applyEvent(applyEvent(base(), quiet), ev['zone.state']);
    for (let i = 0; s.feed.length < FEED_CAP; i++) s = applyEvent(s, { ...ev['infrastructure.road'], event_id: `r${String(i)}` });
    s = applyEvent(s, ev['infrastructure.bridge']);
    expect(s.feed.some((e) => e.event_id === 'quiet')).toBe(false);
    expect(s.feed.some((e) => e.event_id === ev['zone.state'].event_id)).toBe(true);
  });
});

describe('applyEvent: backend events', () => {
  it('the snapshot sets city, world and sim, and the dashboard derives live assets from them', () => {
    const s = base();
    expect(s.hasSnapshot).toBe(true);
    expect(s.city?.zones).toHaveLength(6);
    expect(s.world?.tick).toBe(12);
    expect(s.sim).toMatchObject({ state: 'running', scenario: 'hillside_landslide', tick: 12, speed: 1, stage: 'construction_and_rain' });
    expect(assets(s).crews.c3).toMatchObject({ name: 'Rescue Team 03', status: 'available', location_zone_id: 'market_ward' });
    expect(s.feed.at(-1)?.event_type).toBe('sim.snapshot');
  });

  it('a reconnect snapshot within the same run keeps the charts; a new run starts over', () => {
    let s = applyEvent(base(), ev['weather.observation']);
    s = applyEvent(s, snapshotEventFixture);
    expect(s.telemetry.hillview).toHaveLength(1);
    const fresh = { ...snapshotEventFixture, payload: { ...snapshotEventFixture.payload, status: { ...snapshotEventFixture.payload.status, tick: 0 } } };
    s = applyEvent(applyEvent(s, ev['sim.tick']), fresh);
    expect(s.telemetry).toEqual({});
    expect(s.readings).toEqual({});
  });

  it('sim.status and sim.tick keep the runner state, clock, speed and stage', () => {
    let s = applyEvent(base(), ev['sim.status']);
    expect(s.sim).toMatchObject({ state: 'paused', running: false, speed: 2, tick: 13, stage: 'intensifying_rain' });
    s = applyEvent(s, ev['sim.tick']);
    expect(s.sim).toMatchObject({ state: 'running', running: true, tick: 13, simTime: ev['sim.tick'].payload.sim_time });
    expect(s.world?.tick).toBe(13);
  });

  it('heartbeats are ignored entirely', () => {
    const before = base();
    expect(applyEvent(before, ev['sim.heartbeat'])).toBe(before);
  });

  it('a rain gauge updates its zone, its reading and the zone telemetry', () => {
    const s = applyEvent(base(), ev['weather.observation']);
    expect(s.world?.zones.hillview).toMatchObject({ rainfall_intensity_mm_h: 52.4, rain_24h_mm: 120 });
    expect(s.readings['RG-02']).toEqual({ value: 52.4, text: '52.4 mm/h', simTime: ev['weather.observation'].sim_time });
    expect(s.telemetry.hillview?.at(-1)).toMatchObject({ rain: 52.4, saturation: null, landslide: null, band: null });
  });

  it('soil probes in one tick merge into one point holding the wettest reading', () => {
    const wetter: EventOf<'environment.soil'> = { ...ev['environment.soil'], payload: { ...ev['environment.soil'].payload, probe_id: 'SM-02', saturation: 0.81 } };
    const s = applyEvents(base(), [ev['weather.observation'], ev['environment.soil'], wetter]);
    expect(s.telemetry.hillview).toHaveLength(1);
    expect(s.telemetry.hillview?.[0]).toMatchObject({ rain: 52.4, saturation: 0.81 });
    expect(s.readings['SM-01']?.text).toBe('74% saturated');
  });

  it('the next sim time starts a new telemetry point', () => {
    const later = at(ev['weather.observation'], '2026-07-14T10:36:04Z');
    const s = applyEvents(base(), [ev['weather.observation'], later]);
    expect(s.telemetry.hillview?.map((p) => p.simTime)).toEqual([ev['weather.observation'].sim_time, '2026-07-14T10:36:04Z']);
  });

  it('drainage, river, slope and standing water update the world', () => {
    const s = applyEvents(base(), [ev['environment.drainage'], ev['environment.river'], ev['environment.slope'], ev['environment.water_accumulation']]);
    expect(s.world?.channels.d7).toMatchObject({ flow_m3s: 10.2, capacity_m3s: 8.5, overflow_m3s: 1.7 });
    expect(s.readings['CL-D7']?.text).toBe('120% of capacity');
    expect(s.world?.rivers.kalinadi).toMatchObject({ level_m: 3.42, trend: 'rising' });
    expect(s.world?.slopes.sl_hv).toMatchObject({ cumulative_movement_mm: 34 });
    expect(s.world?.zones.riverside).toMatchObject({ water_depth_cm: 12.5, water_trend: 'rising' });
    expect(s.telemetry.riverside?.at(-1)).toMatchObject({ water: 12.5, rain: null });
  });

  it('infrastructure changes update the world and mark the timeline', () => {
    const s = applyEvents(base(), [
      ev['infrastructure.road'], ev['infrastructure.bridge'], ev['infrastructure.drainage_obstruction'], ev['infrastructure.construction'],
      ev['infrastructure.failure'],
    ]);
    const a = assets(s);
    expect(a.roads.hill_road).toMatchObject({ status: 'blocked', reason: 'fixture: debris' });
    expect(a.bridges.br_1?.status).toBe('closed');
    expect(a.channels.d7?.blocked_fraction).toBe(0.7);
    expect(a.projects.ht_phase2).toMatchObject({ status: 'halted', activity: 'halted', excavation_depth_m: 3.6 });
    expect(s.milestones.map((m) => m.label)).toEqual([
      'Hill Road blocked', 'Kalinadi Bridge closed', 'd7 70% blocked', 'Hillview Terrace Phase 2 halted', 'Failure: fixture: slope failed above D-7',
    ]);
    expect(s.milestones.every((m) => m.kind === 'infrastructure' && m.zoneId !== undefined)).toBe(true);
  });

  it('emergency events update crews, ambulances, hospitals and shelters', () => {
    const s = applyEvents(base(), [ev['emergency.rescue_team'], ev['emergency.ambulance'], ev['emergency.hospital'], ev['emergency.shelter']]);
    const a = assets(s);
    expect(a.crews.c1).toMatchObject({ status: 'on_site', location_zone_id: 'riverside', task: 'fixture: evacuation support' });
    expect(s.world?.ambulances.a1?.status).toBe('dispatched');
    expect(a.hospitals.h2).toMatchObject({ beds_occupied: 52, er_status: 'busy' });
    expect(a.shelters.s1).toMatchObject({ status: 'open', occupancy: 120 });
  });

  it('stage 0 means the engine was reset: readings, charts and pending state start over', () => {
    let s = applyEvents(opened(), [ev['weather.observation'], ev['zone.state']]);
    const reset: EventOf<'scenario.stage'> = { ...ev['scenario.stage'], payload: { ...ev['scenario.stage'].payload, stage_index: 0, stage: 'construction_and_rain' } };
    expect(isEngineReset(reset)).toBe(true);
    expect(isEngineReset(ev['scenario.stage'])).toBe(false);
    s = applyEvent(s, reset);
    expect(s).toMatchObject({ readings: {}, telemetry: {}, zoneState: {}, incidents: {} });
    expect(s.milestones).toHaveLength(1);
    expect(s.sim.stage).toBe('construction_and_rain');
  });

  it('a later stage is a city-wide milestone', () => {
    const s = applyEvent(base(), ev['scenario.stage']);
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'scenario', label: 'fixture: slope creep begins' });
    expect(s.milestones.at(-1)?.zoneId).toBeUndefined();
    expect(s.world?.stage_index).toBe(2);
  });

  it('feed is capped', () => {
    let s = base();
    for (let i = 0; i < FEED_CAP + 20; i++) s = applyEvent(s, { ...ev['sim.tick'], event_id: `t${String(i)}` });
    expect(s.feed).toHaveLength(FEED_CAP);
    expect(s.feed.at(-1)?.event_id).toBe(`t${String(FEED_CAP + 19)}`);
  });

  it('a full feed drops routine ticks and readings before city events', () => {
    let s = applyEvent(base(), ev['infrastructure.drainage_obstruction']);
    for (let i = 0; i < FEED_CAP + 20; i++) {
      const routine = i % 2 === 0 ? ev['sim.tick'] : ev['environment.soil'];
      s = applyEvent(s, { ...routine, event_id: `r${String(i)}` });
    }
    expect(s.feed).toHaveLength(FEED_CAP);
    expect(s.feed.map((e) => e.event_type).filter((t) => t !== 'sim.tick' && !t.startsWith('environment.'))).toEqual(['sim.snapshot', 'infrastructure.drainage_obstruction']);
    expect(s.feed.at(-1)?.event_id).toBe(`r${String(FEED_CAP + 19)}`);
  });

  it('an unknown event type is appended to the feed and otherwise ignored', () => {
    const weird = { ...ev['sim.tick'], event_type: 'future.thing' } as unknown as Event;
    const before = base();
    const s = applyEvent(before, weird);
    expect(s.feed.at(-1)?.event_type).toBe('future.thing');
    expect(s.world).toBe(before.world);
  });
});

describe('applyEvent: PENDING events of later milestones', () => {
  it('zone.state updates band and telemetry; a band change adds a milestone', () => {
    const s = applyEvent(base(), ev['zone.state']);
    expect(s.zoneState.hillview?.band).toBe('warning');
    expect(s.telemetry.hillview?.at(-1)).toMatchObject({ landslide: 0.61, band: 'warning' });
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'band', zoneId: 'hillview', band: 'warning' });
  });
  it('zone.state for an unknown zone is stored but does not throw', () => {
    const e: Event = { ...ev['zone.state'], payload: { ...ev['zone.state'].payload, zone_id: 'ghost' } };
    expect(() => applyEvent(base(), e)).not.toThrow();
  });
  it('agent.node.started then finished adds then replaces a step', () => {
    let s = applyEvents(opened(), [ev['agent.run.started'], ev['agent.node.started']]);
    const run = () => s.incidents.inc_1?.runs.find((r) => r.id === ev['agent.node.started'].payload.run_id);
    expect(run()?.steps.at(-1)?.status).toBe('running');
    s = applyEvent(s, ev['agent.node.finished']);
    const finished = ev['agent.node.finished'].payload;
    expect(run()?.steps.filter((st) => st.id === finished.id)).toHaveLength(1);
    expect(run()?.steps.find((st) => st.id === finished.id)?.status).toBe('finished');
  });
  it('agent.node.finished for an unknown run creates a stub run', () => {
    const e: Event = { ...ev['agent.node.finished'], payload: { ...ev['agent.node.finished'].payload, run_id: 'run_ghost' } };
    const s = applyEvent(opened(), e);
    expect(s.incidents.inc_1?.runs.some((r) => r.id === 'run_ghost')).toBe(true);
  });
  it('approval.requested and decided update both maps', () => {
    let s = applyEvent(opened(), ev['approval.requested']);
    const id = ev['approval.requested'].payload.id;
    expect(s.approvals[id]?.status).toBe('pending');
    s = applyEvent(s, ev['approval.decided']);
    expect(s.approvals[id]?.status).toBe(ev['approval.decided'].payload.status);
    expect(s.incidents.inc_1?.approvals.find((a) => a.id === id)?.status).toBe(ev['approval.decided'].payload.status);
  });
  it('action.executed applies its status changes to the world and adds a milestone', () => {
    const s = applyEvent(opened(), ev['action.executed']);
    expect(assets(s).crews.c3?.status).toBe('dispatched');
    expect(s.milestones.at(-1)?.kind).toBe('action');
  });
  it('action.verified attaches verification', () => {
    const s = applyEvents(opened(), [ev['action.executed'], ev['action.verified']]);
    const id = ev['action.verified'].payload.action_id;
    expect(s.actions[id]?.verification?.status).toBe(ev['action.verified'].payload.verification.status);
  });
  it('threat.escalated raises the band of the incident it names', () => {
    const e: Event = { ...ev['threat.escalated'], payload: { ...ev['threat.escalated'].payload, band: 'critical' } };
    const s = applyEvent(opened(), e);
    expect(s.incidents.inc_1?.band).toBe('critical');
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'band', incidentId: 'inc_1', band: 'critical' });
  });
  it('replan.triggered adds a replan milestone that names the run', () => {
    const s = applyEvent(opened(), ev['replan.triggered']);
    expect(s.milestones.at(-1)).toMatchObject({ kind: 'replan', incidentId: 'inc_1', runId: 'run_1' });
  });
});

describe('useLiveStore', () => {
  it('dispatch and dispatchMany run the reducer, resetLive keeps the actions', async () => {
    const { useLiveStore } = await import('./liveStore');
    useLiveStore.getState().dispatch(snapshotEventFixture);
    expect(useLiveStore.getState().hasSnapshot).toBe(true);
    useLiveStore.getState().dispatchMany([ev['sim.tick'], ev['weather.observation']]);
    expect(useLiveStore.getState().feed.slice(-2).map((e) => e.event_type)).toEqual(['sim.tick', 'weather.observation']);
    useLiveStore.getState().setConnection('reconnecting');
    expect(useLiveStore.getState().connection).toBe('reconnecting');
    useLiveStore.getState().resetLive();
    expect(useLiveStore.getState().hasSnapshot).toBe(false);
    expect(typeof useLiveStore.getState().dispatch).toBe('function');
  });
});
