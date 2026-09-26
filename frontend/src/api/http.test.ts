import { describe, expect, it, vi } from 'vitest';
import { HttpApiClient } from './http';
import type { ApiError } from './client';

function fakeFetch(status: number, body: unknown) {
  return vi.fn((_url: RequestInfo | URL, _init?: RequestInit) =>
    Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })));
}
const client = (f: ReturnType<typeof fakeFetch>) => new HttpApiClient({ fetchImpl: f as unknown as typeof fetch });

describe('HttpApiClient', () => {
  it('GETs the city from /api/city', async () => {
    const f = fakeFetch(200, { zones: [] });
    await client(f).city();
    expect(f.mock.calls[0]?.[0]).toBe('/api/city');
  });
  it('GETs a chunk by its encoded citation id', async () => {
    const f = fakeFetch(200, { chunk_id: 'dmp-2024#s4.2' });
    await client(f).chunk('dmp-2024#s4.2');
    expect(f.mock.calls[0]?.[0]).toBe('/api/chunks/dmp-2024%23s4.2');
  });
  it('posts simulation controls with the backend bodies', async () => {
    const f = fakeFetch(200, { state: 'running' });
    const c = client(f);
    await c.simulation.start({ scenario: 'cascading_landslide_flood', speed: 4 });
    await c.simulation.setSpeed(10);
    await c.simulation.reset();
    const calls = f.mock.calls.map(([url, init]): unknown[] => [url, init?.method, init?.body === undefined ? undefined : (JSON.parse(init.body as string) as unknown)]);
    expect(calls).toEqual([
      ['/api/simulation/start', 'POST', { scenario: 'cascading_landslide_flood', speed: 4 }],
      ['/api/simulation/speed', 'POST', { speed: 10 }],
      ['/api/simulation/reset', 'POST', undefined],
    ]);
  });
  it('posts an inject request and answers the resulting events', async () => {
    const f = fakeFetch(200, [{ event_type: 'infrastructure.road' }]);
    const body = { event_type: 'infrastructure.road' as const, payload: { road_id: 'RD-01', status: 'blocked' }, source: 'operator:api' };
    const events = await client(f).simulation.inject(body);
    expect(f.mock.calls[0]?.[0]).toBe('/api/simulation/inject');
    expect(JSON.parse(f.mock.calls[0]?.[1]?.body as string)).toEqual(body);
    expect(events).toHaveLength(1);
  });
  it('bands() and simulation.trigger() call the backend', async () => {
    const f = fakeFetch(200, []);
    const c = client(f);
    await c.bands();
    expect(f.mock.calls[0]?.[0]).toBe('/api/detector/bands');
    await c.simulation.trigger({ trigger: 'flash_flood' });
    expect(f.mock.calls[1]?.[0]).toBe('/api/simulation/trigger');
    expect(JSON.parse(f.mock.calls[1]?.[1]?.body as string)).toEqual({ trigger: 'flash_flood' });
  });
  it('throws ApiError with status and body on non-2xx', async () => {
    await expect(client(fakeFetch(500, { detail: 'boom' })).city()).rejects.toMatchObject<Partial<ApiError>>({ status: 500, body: { detail: 'boom' } });
  });
  it('PENDING routes answer 501 without a request until the backend serves them', async () => {
    const f = fakeFetch(200, {});
    const c = client(f);
    for (const call of [
      () => c.llmStatus(), () => c.events(), () => c.incidents(), () => c.incident('i'), () => c.approvals(),
      () => c.decide('a', { decision: 'approve', approved_action_ids: [] }), () => c.actions(), () => c.action('a'), () => c.document('d'),
    ]) {
      await expect(call()).rejects.toMatchObject({ status: 501 });
    }
    expect(f).not.toHaveBeenCalled();
  });
  it('a socket closed while still connecting closes once open and delivers nothing', () => {
    class ConnectingWs {
      readyState = 0;
      onopen: (() => void) | null = null;
      onmessage: ((ev: { data: string }) => void) | null = null;
      onclose: unknown = null;
      onerror: unknown = null;
      closed = false;
      constructor(_url: string) { sockets.push(this); }
      close() { this.closed = true; }
    }
    const sockets: ConnectingWs[] = [];
    const onOpen = vi.fn();
    const onEvent = vi.fn();
    const h = new HttpApiClient({ wsUrl: 'ws://test/ws', WebSocketImpl: ConnectingWs as unknown as typeof WebSocket })
      .openSocket({ onOpen, onEvent, onClose: vi.fn(), onError: vi.fn() });
    h.close();
    const ws = sockets[0];
    expect(ws?.closed).toBe(false);
    expect(ws?.onmessage).toBeNull();
    ws?.onopen?.();
    expect(ws?.closed).toBe(true);
    expect(onOpen).not.toHaveBeenCalled();
  });

  it('socket forwards events and swallows heartbeats', () => {
    const sockets: FakeWs[] = [];
    class FakeWs {
      onopen: (() => void) | null = null;
      onmessage: ((ev: { data: string }) => void) | null = null;
      onclose: ((ev: { code: number }) => void) | null = null;
      onerror: ((ev: unknown) => void) | null = null;
      closed = false;
      url: string;
      constructor(url: string) { this.url = url; sockets.push(this); }
      close() { this.closed = true; }
    }
    const c = new HttpApiClient({ wsUrl: 'ws://test/ws', WebSocketImpl: FakeWs as unknown as typeof WebSocket });
    const onEvent = vi.fn();
    const onClose = vi.fn();
    const h = c.openSocket({ onOpen: vi.fn(), onEvent, onClose, onError: vi.fn() });
    const ws = sockets[0];
    expect(ws?.url).toBe('ws://test/ws');
    ws?.onmessage?.({ data: JSON.stringify({ event_id: 'evt-heartbeat', event_type: 'sim.heartbeat', payload: {} }) });
    ws?.onmessage?.({ data: JSON.stringify({ event_id: 'evt-000001', event_type: 'sim.tick', payload: {} }) });
    expect(onEvent).toHaveBeenCalledTimes(1);
    ws?.onclose?.({ code: 1006 });
    expect(onClose).toHaveBeenCalledWith('1006');
    h.close();
    expect(ws?.closed).toBe(true);
  });
});
