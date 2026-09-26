import { describe, expect, it, vi } from 'vitest';
import { HttpApiClient } from './http';
import type { ApiError } from './client';

function fakeFetch(status: number, body: unknown) {
  return vi.fn((_url: RequestInfo | URL, _init?: RequestInit) =>
    Promise.resolve(new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })));
}

describe('HttpApiClient', () => {
  it('GETs city from /api/city', async () => {
    const f = fakeFetch(200, { zones: [] });
    const c = new HttpApiClient({ fetchImpl: f as unknown as typeof fetch });
    await c.city();
    expect(f.mock.calls[0]?.[0]).toBe('/api/city');
  });
  it('builds event query string', async () => {
    const f = fakeFetch(200, []);
    const c = new HttpApiClient({ fetchImpl: f as unknown as typeof fetch });
    await c.events({ since: 'evt_9', type: 'zone.state', limit: 50 });
    expect(f.mock.calls[0]?.[0]).toBe('/api/events?since=evt_9&type=zone.state&limit=50');
  });
  it('POSTs decision body as JSON', async () => {
    const f = fakeFetch(200, { id: 'appr_1' });
    const c = new HttpApiClient({ fetchImpl: f as unknown as typeof fetch });
    await c.decide('appr_1', { decision: 'partial', approved_action_ids: ['act_1'], note: 'ok' });
    const [url, init] = f.mock.calls[0] ?? [];
    expect(url).toBe('/api/approvals/appr_1/decide');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual({ decision: 'partial', approved_action_ids: ['act_1'], note: 'ok' });
  });
  it('throws ApiError with status and body on non-2xx', async () => {
    const c = new HttpApiClient({ fetchImpl: fakeFetch(500, { detail: 'boom' }) as unknown as typeof fetch });
    await expect(c.city()).rejects.toMatchObject<Partial<ApiError>>({ status: 500, body: { detail: 'boom' } });
  });
  it('setSpeed posts to /api/simulation/speed', async () => {
    const f = fakeFetch(200, { running: true });
    const c = new HttpApiClient({ fetchImpl: f as unknown as typeof fetch });
    await c.simulation.setSpeed(4);
    expect(f.mock.calls[0]?.[0]).toBe('/api/simulation/speed');
  });
  it('socket forwards events and ignores heartbeats', () => {
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
    ws?.onmessage?.({ data: JSON.stringify({ type: 'heartbeat' }) });
    ws?.onmessage?.({ data: JSON.stringify({ id: 'e1', type: 'sim.tick', payload: {} }) });
    expect(onEvent).toHaveBeenCalledTimes(1);
    ws?.onclose?.({ code: 1006 });
    expect(onClose).toHaveBeenCalledWith('1006');
    h.close();
    expect(ws?.closed).toBe(true);
  });
});
