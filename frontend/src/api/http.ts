import { ApiError, type ApiClient, type SocketHandle, type SocketHandlers } from './client';
import type {
  Action,
  Approval,
  ApprovalDecision,
  ApprovalStatus,
  Bands,
  Chunk,
  City,
  DataMode,
  Document,
  Event,
  Health,
  Incident,
  IncidentSummary,
  InjectRequest,
  LlmStatus,
  SimulationStart,
  SimulationStatus,
  SourceStatus,
  TriggerRequest,
  WorkflowDecision,
  WorkflowRun,
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

/**
 * PENDING: the backend does not serve this route yet (openapi.pending.yaml). Answer 501 without a request so the
 * console stays clean and panels show their empty states. When the route lands, call this.get/this.post instead and
 * delete the route's overlay entry.
 */
function pending<T>(route: string): Promise<T> {
  return Promise.reject(new ApiError(501, { detail: `${route} is not served by the backend yet` }, `${route} is pending`));
}

/** WebSocket.CONNECTING, spelled out so injected test doubles need not define the constant. */
const CONNECTING = 0;

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
  city(): Promise<City> { return this.get('/city'); }
  chunk(chunkId: string): Promise<Chunk> { return this.get(`/chunks/${encodeURIComponent(chunkId)}`); }

  readonly simulation = {
    start: (body: SimulationStart): Promise<SimulationStatus> => this.post('/simulation/start', body),
    pause: (): Promise<SimulationStatus> => this.post('/simulation/pause'),
    resume: (): Promise<SimulationStatus> => this.post('/simulation/resume'),
    reset: (): Promise<SimulationStatus> => this.post('/simulation/reset'),
    setSpeed: (speed: number): Promise<SimulationStatus> => this.post('/simulation/speed', { speed }),
    inject: (body: InjectRequest): Promise<Event[]> => this.post('/simulation/inject', body),
    trigger: (body: TriggerRequest): Promise<Event[]> => this.post('/simulation/trigger', body),
  };

  source(): Promise<SourceStatus> { return this.get('/source'); }
  setSource(mode: DataMode): Promise<SourceStatus> { return this.post('/source', { mode }); }
  bands(): Promise<Bands> { return this.get('/detector/bands'); }
  decideRunApproval(runId: string, body: WorkflowDecision): Promise<WorkflowRun> {
    return this.post(`/agent/runs/${encodeURIComponent(runId)}/approval`, body);
  }

  // ---- PENDING routes (see pending()) ----
  llmStatus(): Promise<LlmStatus> { return pending('GET /api/llm/status'); }
  events(): Promise<Event[]> { return pending('GET /api/events'); }
  incidents(): Promise<IncidentSummary[]> { return pending('GET /api/incidents'); }
  incident(_id: string): Promise<Incident> { return pending('GET /api/incidents/{incident_id}'); }
  approvals(_status?: ApprovalStatus): Promise<Approval[]> { return pending('GET /api/approvals'); }
  decide(_id: string, _body: ApprovalDecision): Promise<Approval> { return pending('POST /api/approvals/{approval_id}/decide'); }
  actions(): Promise<Action[]> { return pending('GET /api/actions'); }
  action(_id: string): Promise<Action> { return pending('GET /api/actions/{action_id}'); }
  document(_docId: string): Promise<Document> { return pending('GET /api/documents/{doc_id}'); }

  /** One raw socket. Reconnect is owned by LiveSocket (src/live/socket.ts). Heartbeats are answered, never delivered. */
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
      if (typeof parsed === 'object' && parsed !== null && (parsed as { event_type?: unknown }).event_type === 'sim.heartbeat') return;
      handlers.onEvent(parsed as Event);
    };
    ws.onclose = (ev: CloseEvent) => { handlers.onClose(String(ev.code)); };
    ws.onerror = (ev) => { handlers.onError(ev); };
    return {
      close: () => {
        // Closing a socket that is still connecting makes the browser log an error (React StrictMode does this in dev);
        // let it open, deliver nothing, and close then.
        if (ws.readyState === CONNECTING) {
          ws.onmessage = null;
          ws.onopen = () => { ws.close(); };
        } else {
          ws.close();
        }
      },
    };
  }
}
