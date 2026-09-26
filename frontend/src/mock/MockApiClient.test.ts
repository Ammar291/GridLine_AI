import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { MockApiClient, nandipurCity, nandipurWorld } from './MockApiClient';
import type { Event } from '@/api/types';
import { ApiError } from '@/api/client';

describe('MockApiClient', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });
  function open(c: MockApiClient) {
    const events: Event[] = [];
    const h = c.openSocket({ onOpen: vi.fn(), onEvent: (e) => { events.push(e); }, onClose: vi.fn(), onError: vi.fn() });
    return { events, h };
  }
  const types = (events: Event[]) => events.map((e) => e.event_type);

  it('serves the backend-built city and world fixtures', () => {
    expect(nandipurCity.zones.map((z) => z.id)).toContain('Z-HV');
    expect(Object.keys(nandipurWorld.zones)).toEqual(nandipurCity.zones.map((z) => z.id));
  });
  it('sends sim.snapshot first (status, world, city) and nothing else until started', () => {
    const c = new MockApiClient({ tickMs: 1000 });
    const { events } = open(c);
    vi.advanceTimersByTime(5000);
    expect(types(events)).toEqual(['sim.snapshot']);
    const snap = events[0];
    expect(snap?.event_type === 'sim.snapshot' && snap.payload.status).toMatchObject({ state: 'idle', tick: 0, scenario: 'hillside_landslide' });
    expect(snap?.event_type === 'sim.snapshot' && snap.payload.city.zones).toHaveLength(nandipurCity.zones.length);
  });
  it('announces transitions with sim.status and replays ticks at tickMs/speed until paused', async () => {
    const c = new MockApiClient({ tickMs: 1000 });
    const { events } = open(c);
    const status = await c.simulation.start({ speed: 2 });
    expect(status).toMatchObject({ state: 'running', speed: 2, scenario: 'hillside_landslide' });
    vi.advanceTimersByTime(1500); // 3 ticks at 500ms
    expect(events.filter((e) => e.event_type === 'sim.tick')).toHaveLength(3);
    await c.simulation.pause();
    vi.advanceTimersByTime(3000);
    expect(events.filter((e) => e.event_type === 'sim.tick')).toHaveLength(3);
    const statuses = events.flatMap((e) => (e.event_type === 'sim.status' ? [e.payload.state] : []));
    expect(statuses).toEqual(['running', 'paused']);
  });
  it('a later snapshot carries the world as replayed so far', async () => {
    const c = new MockApiClient({ tickMs: 1000 });
    open(c);
    await c.simulation.start({ speed: 1 });
    vi.advanceTimersByTime(3000);
    const { events } = open(c);
    const snap = events[0];
    expect(snap?.event_type === 'sim.snapshot' && snap.payload.status.tick).toBe(3);
    expect(snap?.event_type === 'sim.snapshot' && snap.payload.world.zones['Z-HV']?.rainfall_intensity_mm_h).toBeGreaterThan(0);
  });
  it('reset announces stage 0 (the dashboard then resyncs) and a new socket gets a tick-0 snapshot', async () => {
    const c = new MockApiClient({ tickMs: 1000 });
    const { events } = open(c);
    await c.simulation.start({ speed: 1 });
    vi.advanceTimersByTime(2000);
    await c.simulation.reset();
    const tail = events.slice(-2);
    expect(tail.map((e) => e.event_type)).toEqual(['scenario.stage', 'sim.status']);
    expect(tail[0]?.event_type === 'scenario.stage' && tail[0].payload.stage_index).toBe(0);
    const again = open(c).events[0];
    expect(again?.event_type === 'sim.snapshot' && again.payload.status.tick).toBe(0);
  });
  it('only the scripted scenario starts; inject and AI-only endpoints reject with 501', async () => {
    const c = new MockApiClient();
    await expect(c.simulation.start({ scenario: 'flash_flood', speed: 1 })).rejects.toMatchObject({ status: 501 });
    await expect(c.simulation.inject({ event_type: 'infrastructure.road', payload: {}, source: 'operator:api' })).rejects.toMatchObject({ status: 501 });
    await expect(c.decide('x', { decision: 'approve', approved_action_ids: [] })).rejects.toBeInstanceOf(ApiError);
    await expect(c.chunk('x')).rejects.toMatchObject({ status: 501 });
    expect(await c.llmStatus()).toEqual({ provider: 'none', model: null });
    expect((await c.bands()).landslide.warning).toBe(0.55);
    expect(await c.approvals()).toEqual([]);
  });
  it('incidents() reflects the opened incident after the replay reaches it', async () => {
    const c = new MockApiClient({ tickMs: 10 });
    open(c);
    await c.simulation.start({ speed: 1 });
    vi.advanceTimersByTime(10 * 72);
    const list = await c.incidents();
    expect(list).toHaveLength(1);
    expect(list[0]?.hazard).toBe('landslide');
  });
  it('closing a socket stops delivery to it', async () => {
    const c = new MockApiClient({ tickMs: 1000 });
    const { events, h } = open(c);
    h.close();
    await c.simulation.start({ speed: 1 });
    vi.advanceTimersByTime(3000);
    expect(types(events)).toEqual(['sim.snapshot']);
  });
});
