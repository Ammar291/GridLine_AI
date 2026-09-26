// Development scaffold (spec F1): serves the backend-built Nandipur city and replays scripted events in the backend's
// shapes. It never fabricates reasoning, approvals, actions or verification: those endpoints answer 501 or empty.
import { ApiError, type ApiClient, type SocketHandle, type SocketHandlers } from '@/api/client';
import type {
  Action, Approval, ApprovalDecision, Bands, Chunk, City, DataMode, Document, Event, EventOf, EventType, Health, Incident,
  IncidentSummary, InjectRequest, LlmStatus, SimStatus, SimulationStart, SimulationStatus, SourceStatus, TriggerRequest,
  WorkflowDecision, WorkflowRun, WorldSnapshot,
} from '@/api/types';
import { applyEvent } from '@/live/applyEvent';
import { initialLiveState, type LiveState } from '@/live/types';
import cityJson from './fixtures/nandipur.city.json';
import worldJson from './fixtures/nandipur.world.json';
import { MockSocket } from './MockSocket';
import { buildReplay, MOCK_BANDS, REPLAY_SCENARIO, REPLAY_SEED, REPLAY_TICKS, simTimeAt, type ReplayStep } from './replay';

/** Both fixtures are written by the backend (`npm run gen:contract`); never edit them by hand. */
export const nandipurCity = cityJson as City;
export const nandipurWorld = worldJson as WorldSnapshot;

const MOCK_DEMO_SOURCE: SourceStatus = {
  mode: 'demo', label: 'DEMO — Nandipur', city: 'Nandipur', provider: 'Synthetic simulation', latitude: null, longitude: null,
  poll_seconds: null, last_updated: null, last_error: null,
};

const notInMock = () => Promise.reject(new ApiError(501, { detail: 'Not available in mock mode' }, 'Not available in mock mode'));

export class MockApiClient implements ApiClient {
  readonly mode = 'mock' as const;
  private readonly cityModel: City;
  private readonly initialWorld: WorldSnapshot;
  private readonly tickMs: number;
  private readonly now: () => string;
  private readonly replay: ReplayStep[];
  private readonly sockets = new Set<MockSocket>();
  /** The mock's own view of what it has emitted, kept with the dashboard's reducer so snapshots stay current. */
  private live: LiveState;
  private tick = 0;
  private running = false;
  private speed = 1;
  private timer: ReturnType<typeof setInterval> | null = null;
  private seq = 0;

  constructor(opts: { city?: City; world?: WorldSnapshot; tickMs?: number; now?: () => string } = {}) {
    this.cityModel = structuredClone(opts.city ?? nandipurCity);
    this.initialWorld = structuredClone(opts.world ?? nandipurWorld);
    this.tickMs = opts.tickMs ?? 1000;
    this.now = opts.now ?? (() => new Date().toISOString());
    this.replay = buildReplay(this.cityModel);
    this.live = this.fresh();
  }

  // ---- REST ----
  health(): Promise<Health> { return Promise.resolve({ status: 'ok', version: 'mock' }); }
  city(): Promise<City> { return Promise.resolve(structuredClone(this.cityModel)); }
  chunk(_chunkId: string): Promise<Chunk> { return notInMock(); }

  readonly simulation = {
    start: (body: SimulationStart): Promise<SimulationStatus> => {
      if (body.scenario != null && body.scenario !== REPLAY_SCENARIO) {
        return Promise.reject(new ApiError(501, { detail: 'Only the primary scenario is scripted in mock mode' }));
      }
      if (body.speed != null) this.speed = body.speed;
      this.run();
      return Promise.resolve(this.announce());
    },
    pause: (): Promise<SimulationStatus> => {
      this.halt();
      return Promise.resolve(this.announce());
    },
    resume: (): Promise<SimulationStatus> => {
      this.run();
      return Promise.resolve(this.announce());
    },
    reset: (): Promise<SimulationStatus> => {
      this.halt();
      this.tick = 0;
      this.live = this.fresh();
      const stage = this.cityModel.scenarios.find((s) => s.name === REPLAY_SCENARIO)?.stages[0];
      if (stage) {
        this.emit(this.envelope('scenario.stage', {
          scenario: REPLAY_SCENARIO, stage_index: 0, stage: stage.name, description: stage.description, tick: 0,
        }));
      }
      return Promise.resolve(this.announce());
    },
    setSpeed: (speed: number): Promise<SimulationStatus> => {
      this.speed = speed;
      if (this.running) this.run();
      return Promise.resolve(this.announce());
    },
    inject: (_body: InjectRequest): Promise<Event[]> => notInMock(),
    trigger: (_body: TriggerRequest): Promise<Event[]> => notInMock(),
  };

  // Mock mode replays the Nandipur simulation only; LIVE data needs the backend (and the network).
  source(): Promise<SourceStatus> { return Promise.resolve({ ...MOCK_DEMO_SOURCE }); }
  setSource(mode: DataMode): Promise<SourceStatus> {
    return mode === 'demo' ? this.source() : Promise.reject(new ApiError(501, { detail: 'LIVE mode needs the backend' }, 'LIVE mode needs the backend'));
  }

  // ---- PENDING endpoints: what mock mode can honestly answer ----
  llmStatus(): Promise<LlmStatus> { return Promise.resolve({ provider: 'none', model: null }); }
  bands(): Promise<Bands> { return Promise.resolve(structuredClone(MOCK_BANDS)); }

  events(q: { since?: string; type?: EventType; limit?: number } = {}): Promise<Event[]> {
    let list = this.live.feed;
    if (q.since !== undefined) {
      const i = list.findIndex((e) => e.event_id === q.since);
      list = i >= 0 ? list.slice(i + 1) : list;
    }
    if (q.type !== undefined) list = list.filter((e) => e.event_type === q.type);
    if (q.limit !== undefined) list = list.slice(-q.limit);
    return Promise.resolve(structuredClone(list));
  }

  incidents(): Promise<IncidentSummary[]> {
    return Promise.resolve(
      Object.values(this.live.incidents).map((i) => ({
        id: i.id, zone_id: i.zone_id, hazard: i.hazard, band: i.band, status: i.status, opened_at: i.opened_at,
        opened_sim_time: i.opened_sim_time, closed_at: i.closed_at ?? null, run_count: i.runs.length, pending_approval_count: 0,
      })),
    );
  }

  incident(id: string): Promise<Incident> {
    const found = this.live.incidents[id];
    return found ? Promise.resolve(structuredClone(found)) : Promise.reject(new ApiError(404, { detail: 'Incident not found' }));
  }

  approvals(): Promise<Approval[]> { return Promise.resolve([]); }
  decideRunApproval(_runId: string, _body: WorkflowDecision): Promise<WorkflowRun> {
    return Promise.reject(new ApiError(501, { detail: 'The agent is not available in mock mode' }, 'The agent is not available in mock mode'));
  }
  decide(_id: string, _body: ApprovalDecision): Promise<Approval> { return notInMock(); }
  actions(): Promise<Action[]> { return Promise.resolve([]); }
  action(_id: string): Promise<Action> { return Promise.reject(new ApiError(404, { detail: 'Action not found' })); }
  document(_docId: string): Promise<Document> { return notInMock(); }

  // ---- socket ----
  openSocket(handlers: SocketHandlers): SocketHandle {
    const socket = new MockSocket(handlers, (s) => this.sockets.delete(s));
    this.sockets.add(socket);
    socket.open(this.snapshotEvent());
    return socket;
  }

  // ---- internals ----
  private fresh(): LiveState {
    return applyEvent(initialLiveState('mock'), {
      ...this.frame('evt-m-start'), event_type: 'sim.snapshot', payload: { status: this.simStatus(), world: this.initialWorld, city: this.cityModel },
    });
  }

  private stageName(): string {
    const stages = this.cityModel.scenarios.find((s) => s.name === REPLAY_SCENARIO)?.stages ?? [];
    return [...stages].reverse().find((s) => s.start_tick <= this.tick)?.name ?? '';
  }

  private simStatus(): SimStatus {
    const state = this.running ? 'running' : this.tick > 0 && this.tick < REPLAY_TICKS ? 'paused' : 'idle';
    return {
      state, running: this.running, scenario: REPLAY_SCENARIO, seed: REPLAY_SEED, speed: this.speed, tick: this.tick,
      sim_time: simTimeAt(this.tick), stage: this.stageName(),
    };
  }

  /** Publish the current status (as the backend does on every transition) and answer it as REST would. */
  private announce(): SimulationStatus {
    const s = this.simStatus();
    this.emit(this.envelope('sim.status', s));
    const stage = this.cityModel.scenarios.find((x) => x.name === REPLAY_SCENARIO)?.stages.find((x) => x.name === s.stage) ?? null;
    return { ...s, scenario: REPLAY_SCENARIO, stage, minutes_per_tick: 5, tick_seconds: this.tickMs / 1000 };
  }

  private run(): void {
    if (this.timer !== null) clearInterval(this.timer);
    if (this.tick >= REPLAY_TICKS) return;
    this.running = true;
    this.timer = setInterval(() => { this.tickOnce(); }, this.tickMs / this.speed);
  }

  private halt(): void {
    if (this.timer !== null) clearInterval(this.timer);
    this.timer = null;
    this.running = false;
  }

  private frame(eventId: string): Omit<EventOf<'sim.status'>, 'event_type' | 'payload'> {
    return {
      event_id: eventId, timestamp: this.now(), sim_time: simTimeAt(this.tick), source: 'simulation:engine', location: null,
      severity: 'info', incident_id: null,
    };
  }

  private envelope<T extends 'sim.status' | 'scenario.stage'>(type: T, payload: EventOf<T>['payload']): Event {
    return { ...this.frame(`evt-m-${String(++this.seq)}`), event_type: type, payload } as EventOf<T>;
  }

  private emit(e: Event): void {
    this.live = applyEvent(this.live, e);
    for (const s of this.sockets) s.deliver(e);
  }

  private tickOnce(): void {
    const step = this.replay[this.tick];
    if (!step) return;
    this.tick = step.tick;
    for (const raw of step.events) {
      const stamped = { ...raw, timestamp: this.now() };
      this.emit(stamped.event_type === 'sim.tick' ? { ...stamped, payload: { ...stamped.payload, speed: this.speed } } : stamped);
    }
    if (this.tick >= REPLAY_TICKS) {
      this.halt();
      this.announce();
    }
  }

  private snapshotEvent(): Event {
    return {
      ...this.frame('evt-snapshot'), event_type: 'sim.snapshot',
      payload: { status: this.simStatus(), world: this.live.world ?? this.initialWorld, city: structuredClone(this.cityModel) },
    };
  }
}
