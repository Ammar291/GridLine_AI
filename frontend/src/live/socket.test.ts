import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import type { EventOf } from '@/api/types';
import { LiveSocket } from './socket';
import { BATCH_MS, useLive } from './useLive';
import { useLiveStore } from './liveStore';
import type { ConnectionStatus } from './types';
import { FakeSocketFactory } from '@/test/FakeSocket';
import { fakeClient } from '@/test/fakeClient';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';

describe('LiveSocket', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  function setup() {
    const f = new FakeSocketFactory();
    const statuses: ConnectionStatus[] = [];
    const onEvent = vi.fn();
    const s = new LiveSocket({ client: f.attach(fakeClient()), onEvent, onStatus: (st) => { statuses.push(st); } });
    return { f, statuses, onEvent, s };
  }

  it('connects, opens and forwards events in order', () => {
    const { f, statuses, onEvent, s } = setup();
    s.start();
    expect(statuses).toEqual(['connecting']);
    expect(f.handlers).toHaveLength(1);
    f.last().onOpen();
    expect(statuses.at(-1)).toBe('open');
    f.last().onEvent(snapshotEventFixture);
    f.last().onEvent(eventsFixture['sim.tick']);
    expect(onEvent.mock.calls.map((c) => (c[0] as { event_type: string }).event_type)).toEqual(['sim.snapshot', 'sim.tick']);
  });

  it('reconnects with backoff after close', () => {
    const { f, statuses, s } = setup();
    s.start();
    f.last().onOpen();
    f.last().onClose('1006');
    expect(statuses.at(-1)).toBe('reconnecting');
    vi.advanceTimersByTime(999);
    expect(f.handlers).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(f.handlers).toHaveLength(2);
    f.last().onClose('1006');
    vi.advanceTimersByTime(1999);
    expect(f.handlers).toHaveLength(2);
    vi.advanceTimersByTime(1);
    expect(f.handlers).toHaveLength(3);
    f.last().onOpen();
    expect(statuses.at(-1)).toBe('open');
    f.last().onClose('1006');
    vi.advanceTimersByTime(1000);
    expect(f.handlers).toHaveLength(4); // backoff resets after a successful open
  });

  it('a close reported twice schedules one reconnect', () => {
    const { f, s } = setup();
    s.start();
    f.last().onError(new Error('boom'));
    f.last().onClose('1006');
    f.last().onClose('1006');
    vi.advanceTimersByTime(5000);
    expect(f.handlers).toHaveLength(2); // the initial socket plus exactly one reconnect
  });

  it('resync reopens at once without announcing a reconnect and drops the old socket', () => {
    const { f, statuses, onEvent, s } = setup();
    s.start();
    f.last().onOpen();
    const old = f.last();
    s.resync();
    expect(f.handlers).toHaveLength(2);
    expect(f.closed).toBe(1);
    expect(statuses).toEqual(['connecting', 'open']);
    old.onEvent(eventsFixture['sim.tick']);
    old.onClose('1000');
    vi.advanceTimersByTime(60_000);
    expect(onEvent).not.toHaveBeenCalled();
    expect(f.handlers).toHaveLength(2);
  });

  it('stop closes and prevents further opens', () => {
    const { f, statuses, s } = setup();
    s.start();
    f.last().onOpen();
    f.last().onClose('1006');
    s.stop();
    expect(statuses.at(-1)).toBe('closed');
    vi.advanceTimersByTime(60_000);
    expect(f.handlers).toHaveLength(1);
    expect(f.closed).toBe(1);
  });
});

describe('useLive', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  function mount() {
    useLiveStore.getState().resetLive();
    const f = new FakeSocketFactory();
    const hook = renderHook(() => { useLive(f.attach(fakeClient())); });
    return { f, ...hook };
  }

  it('wires the socket to the store in batches and keeps data while reconnecting', () => {
    const { f, unmount } = mount();
    expect(useLiveStore.getState().connection).toBe('connecting');
    expect(useLiveStore.getState().mode).toBe('mock');
    act(() => {
      f.last().onOpen();
      f.last().onEvent(snapshotEventFixture);
      f.last().onEvent(eventsFixture['incident.opened']);
    });
    expect(useLiveStore.getState().hasSnapshot).toBe(false); // still batching
    act(() => { vi.advanceTimersByTime(BATCH_MS); });
    expect(useLiveStore.getState().connection).toBe('open');
    act(() => { f.last().onClose('1006'); });
    const s = useLiveStore.getState();
    expect(s.connection).toBe('reconnecting');
    expect(s.hasSnapshot).toBe(true);
    expect(Object.keys(s.incidents)).toEqual(['inc_1']);
    expect(s.feed).toHaveLength(2);
    unmount();
    expect(useLiveStore.getState().connection).toBe('closed');
  });

  it('an engine reset (stage 0) reopens the socket for a fresh snapshot', () => {
    const { f, unmount } = mount();
    const reset: EventOf<'scenario.stage'> = {
      ...eventsFixture['scenario.stage'], payload: { ...eventsFixture['scenario.stage'].payload, stage_index: 0 },
    };
    act(() => {
      f.last().onOpen();
      f.last().onEvent(snapshotEventFixture);
      f.last().onEvent(eventsFixture['scenario.stage']);
    });
    expect(f.handlers).toHaveLength(1);
    act(() => { f.last().onEvent(reset); });
    expect(f.handlers).toHaveLength(2);
    act(() => { vi.advanceTimersByTime(BATCH_MS); });
    expect(useLiveStore.getState().connection).toBe('open');
    unmount();
  });
});
