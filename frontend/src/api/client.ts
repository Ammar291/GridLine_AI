import type {
  Action,
  Approval,
  ApprovalDecision,
  ApprovalStatus,
  Bands,
  Chunk,
  City,
  Document,
  Event,
  EventType,
  Health,
  Incident,
  IncidentSummary,
  InjectRequest,
  LlmStatus,
  SimulationStart,
  SimulationStatus,
} from './types';

export interface SocketHandlers {
  onOpen: () => void;
  onEvent: (e: Event) => void;
  onClose: (reason: string) => void;
  onError: (err: unknown) => void;
}
export interface SocketHandle {
  close: () => void;
}
export type ApiMode = 'http' | 'mock';

export interface ApiClient {
  readonly mode: ApiMode;
  health(): Promise<Health>;
  city(): Promise<City>;
  chunk(chunkId: string): Promise<Chunk>;
  simulation: {
    start(body: SimulationStart): Promise<SimulationStatus>;
    pause(): Promise<SimulationStatus>;
    resume(): Promise<SimulationStatus>;
    reset(): Promise<SimulationStatus>;
    setSpeed(speed: number): Promise<SimulationStatus>;
    inject(body: InjectRequest): Promise<Event[]>;
  };
  openSocket(handlers: SocketHandlers): SocketHandle;
  // PENDING (openapi.pending.yaml): later milestones. HttpApiClient answers these with 501 until the backend serves them.
  llmStatus(): Promise<LlmStatus>;
  bands(): Promise<Bands>;
  events(q?: { since?: string; type?: EventType; limit?: number }): Promise<Event[]>;
  incidents(): Promise<IncidentSummary[]>;
  incident(id: string): Promise<Incident>;
  approvals(status?: ApprovalStatus): Promise<Approval[]>;
  decide(id: string, body: ApprovalDecision): Promise<Approval>;
  actions(): Promise<Action[]>;
  action(id: string): Promise<Action>;
  document(docId: string): Promise<Document>;
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  constructor(status: number, body: unknown, message?: string) {
    super(message ?? `Request failed with ${String(status)}`);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/** 'mock' only when VITE_API_MODE is exactly 'mock'; anything else is 'http'. */
export function readApiMode(env: { VITE_API_MODE?: string } = import.meta.env): ApiMode {
  return env.VITE_API_MODE === 'mock' ? 'mock' : 'http';
}
