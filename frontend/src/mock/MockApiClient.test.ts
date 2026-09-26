import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { MockApiClient } from './MockApiClient';
import type { Event } from '@/api/types';
import { ApiError } from '@/api/client';

describe('MockApiClient', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });
  function open(c: MockApiClient) {
    const events: Event[] = [];
    const h = c.openSocket({ onOpen: vi.fn(), onEvent: e => { events.push(e); }, onClose: vi.fn(), onError: vi.fn() });
    return { events, h };
  }
  it('sends state.snapshot first and nothing else until started', () => {
    const c = new MockApiClient({ tickMs: 1000 });
    const { events } = open(c);
    vi.advanceTimersByTime(5000);
    expect(events.map(e => e.type)).toEqual(['state.snapshot']);
  });
  it('replays ticks at tickMs/speed after start and pauses', async () => {
    const c = new MockApiClient({ tickMs: 1000 });
    const { events } = open(c);
    await c.simulation.start({ scenario: 'hillside_landslide', speed: 2 });
    vi.advanceTimersByTime(1500); // 3 ticks at 500ms
    expect(events.filter(e => e.type === 'sim.tick')).toHaveLength(3);
    await c.simulation.pause();
    vi.advanceTimersByTime(3000);
    expect(events.filter(e => e.type === 'sim.tick')).toHaveLength(3);
  });
  it('reset re-sends a fresh snapshot with tick 0', async () => {
    const c = new MockApiClient({ tickMs: 1000 });
    const { events } = open(c);
    await c.simulation.start({ scenario: 'hillside_landslide', speed: 1 });
    vi.advanceTimersByTime(2000);
    await c.simulation.reset();
    const snaps = events.filter(e => e.type === 'state.snapshot');
    expect(snaps).toHaveLength(2);
    const last = snaps[1];
    expect(last?.type === 'state.snapshot' && last.payload.sim.tick).toBe(0);
  });
  it('AI-only endpoints reject with 501 and llmStatus reports none', async () => {
    const c = new MockApiClient();
    await expect(c.decide('x', { decision: 'approve', approved_action_ids: [] })).rejects.toBeInstanceOf(ApiError);
    await expect(c.chunk('x')).rejects.toMatchObject({ status: 501 });
    expect(await c.llmStatus()).toEqual({ provider: 'none', model: null });
    expect(await c.approvals()).toEqual([]);
  });
  it('incidents() reflects the opened incident after replay reaches it', async () => {
    const c = new MockApiClient({ tickMs: 10 });
    open(c);
    await c.simulation.start({ scenario: 'hillside_landslide', speed: 1 });
    vi.advanceTimersByTime(10 * 72);
    const list = await c.incidents();
    expect(list).toHaveLength(1);
    expect(list[0]?.hazard).toBe('landslide');
  });
  it('closing a socket stops delivery to it', async () => {
    const c = new MockApiClient({ tickMs: 1000 });
    const { events, h } = open(c);
    await c.simulation.start({ scenario: 'hillside_landslide', speed: 1 });
    h.close();
    vi.advanceTimersByTime(3000);
    expect(events.map(e => e.type)).toEqual(['state.snapshot']);
  });
});
