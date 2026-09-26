import { ApiError, type ApiClient, type SocketHandle, type SocketHandlers } from './client';
import type {
  Action,
  Approval,
  ApprovalDecision,
  ApprovalStatus,
  Chunk,
  City,
  Document,
  Event,
  EventType,
  Health,
  Incident,
  IncidentSummary,
  InjectEvent,
  LlmStatus,
  SimStatus,
} from './types';

async function request<T>(fetchImpl: typeof fetch, url: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!headers.has('content-type')) headers.set('content-type', 'application/json');
  const res = await fetchImpl(url, { ...init, headers });
  const text = await res.text();
  const body: unknown = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, body, `${init?.method ?? 'GET'} ${url} failed with ${String(res.status)}`);
  return body as T;
}

function defaultWsUrl(): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${proto}//${window.location.host}/ws`;
}

export class HttpApiClient implements ApiClient {
  readonly mode = 'http' as const;
  private readonly baseUrl: string;
  private readonly fetchImpl: typeof fetch;
  private readonly wsUrl: string | undefined;
  private readonly WebSocketImpl: typeof WebSocket | undefined;

  constructor(opts: { baseUrl?: string; fetchImpl?: typeof fetch; wsUrl?: string; WebSocketImpl?: typeof WebSocket } = {}) {
    this.baseUrl = opts.baseUrl ?? '/api';
    this.fetchImpl = opts.fetchImpl ?? ((input, init) => fetch(input, init));
    this.wsUrl = opts.wsUrl;
    this.WebSocketImpl = opts.WebSocketImpl;
  }

  private get<T>(path: string): Promise<T> {
    return request<T>(this.fetchImpl, `${this.baseUrl}${path}`);
  }

  private post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>(this.fetchImpl, `${this.baseUrl}${path}`, {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  }

  health(): Promise<Health> { return this.get('/health'); }
  llmStatus(): Promise<LlmStatus> { return this.get('/llm/status'); }
  city(): Promise<City> { return this.get('/city'); }

  events(q: { since?: string; type?: EventType; limit?: number } = {}): Promise<Event[]> {
    const params = new URLSearchParams();
    if (q.since !== undefined) params.set('since', q.since);
    if (q.type !== undefined) params.set('type', q.type);
    if (q.limit !== undefined) params.set('limit', String(q.limit));
    const qs = params.toString();
    return this.get(`/events${qs ? `?${qs}` : ''}`);
  }

  incidents(): Promise<IncidentSummary[]> { return this.get('/incidents'); }
  incident(id: string): Promise<Incident> { return this.get(`/incidents/${encodeURIComponent(id)}`); }

  approvals(status?: ApprovalStatus): Promise<Approval[]> {
    return this.get(status === undefined ? '/approvals' : `/approvals?status=${status}`);
  }

  decide(id: string, body: ApprovalDecision): Promise<Approval> {
    return this.post(`/approvals/${encodeURIComponent(id)}/decide`, body);
  }

  actions(): Promise<Action[]> { return this.get('/actions'); }
  action(id: string): Promise<Action> { return this.get(`/actions/${encodeURIComponent(id)}`); }
  document(docId: string): Promise<Document> { return this.get(`/documents/${encodeURIComponent(docId)}`); }
  chunk(chunkId: string): Promise<Chunk> { return this.get(`/chunks/${encodeURIComponent(chunkId)}`); }

  readonly simulation = {
    start: (body: { scenario: string; speed: number; seed?: number }): Promise<SimStatus> => this.post('/simulation/start', body),
    pause: (): Promise<SimStatus> => this.post('/simulation/pause'),
    resume: (): Promise<SimStatus> => this.post('/simulation/resume'),
    reset: (): Promise<SimStatus> => this.post('/simulation/reset'),
    setSpeed: (speed: number): Promise<SimStatus> => this.post('/simulation/speed', { speed }),
    inject: (body: InjectEvent): Promise<SimStatus> => this.post('/simulation/inject', body),
  };

  /** One raw socket. Reconnect is owned by LiveSocket (src/live/socket.ts). */
  openSocket(handlers: SocketHandlers): SocketHandle {
    const Impl = this.WebSocketImpl ?? WebSocket;
    const ws = new Impl(this.wsUrl ?? defaultWsUrl());
    ws.onopen = () => { handlers.onOpen(); };
    ws.onmessage = (ev: MessageEvent<string>) => {
      let parsed: unknown;
      try {
        parsed = JSON.parse(ev.data);
      } catch (err) {
        handlers.onError(err);
        return;
      }
      if (typeof parsed === 'object' && parsed !== null && (parsed as { type?: unknown }).type === 'heartbeat') return;
      handlers.onEvent(parsed as Event);
    };
    ws.onclose = (ev: CloseEvent) => { handlers.onClose(String(ev.code)); };
    ws.onerror = (ev) => { handlers.onError(ev); };
    return { close: () => { ws.close(); } };
  }
}
