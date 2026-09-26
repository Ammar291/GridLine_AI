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
  llmStatus(): Promise<LlmStatus>;
  city(): Promise<City>;
  events(q?: { since?: string; type?: EventType; limit?: number }): Promise<Event[]>;
  incidents(): Promise<IncidentSummary[]>;
  incident(id: string): Promise<Incident>;
  approvals(status?: ApprovalStatus): Promise<Approval[]>;
  decide(id: string, body: ApprovalDecision): Promise<Approval>;
  actions(): Promise<Action[]>;
  action(id: string): Promise<Action>;
  document(docId: string): Promise<Document>;
  chunk(chunkId: string): Promise<Chunk>;
  simulation: {
    start(body: { scenario: string; speed: number; seed?: number }): Promise<SimStatus>;
    pause(): Promise<SimStatus>;
    resume(): Promise<SimStatus>;
    reset(): Promise<SimStatus>;
    setSpeed(speed: number): Promise<SimStatus>;
    inject(body: InjectEvent): Promise<SimStatus>;
  };
  openSocket(handlers: SocketHandlers): SocketHandle;
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
