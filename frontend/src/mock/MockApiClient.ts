// Development scaffold (spec F1): serves the synthetic Nandipur city and replays scripted simulation/detector events.
// Every AI-only endpoint rejects with 501; the mock never fabricates reasoning, approvals, actions or verification.
import { ApiError, type ApiClient, type SocketHandle, type SocketHandlers } from '@/api/client';
import type {
  Action,
  Approval,
  ApprovalDecision,
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
} from '@/api/types';
import cityJson from './fixtures/nandipur.city.json';
import { MockSocket } from './MockSocket';
import { buildReplay, REPLAY_TICKS, simTimeAt, type ReplayStep } from './replay';

export const nandipurCity: City = cityJson as City;

const PRIMARY_SCENARIO = 'hillside_landslide';
const notInMock = () => Promise.reject(new ApiError(501, { detail: 'Not available in mock mode' }, 'Not available in mock mode'));

export class MockApiClient implements ApiClient {
  readonly mode = 'mock' as const;
  private readonly initialCity: City;
  private readonly tickMs: number;
  private readonly now: () => string;
  private readonly replay: ReplayStep[];
  private readonly sockets = new Set<MockSocket>();
  private cityState: City;
  private incidentList: Incident[] = [];
  private feed: Event[] = [];
  private tick = 0;
  private running = false;
  private speed = 1;
  private scenario: string | null = null;
  private timer: ReturnType<typeof setInterval> | null = null;
  private seq = 0;

  constructor(opts: { city?: City; tickMs?: number; now?: () => string } = {}) {
    this.initialCity = structuredClone(opts.city ?? nandipurCity);
    this.cityState = structuredClone(this.initialCity);
    this.tickMs = opts.tickMs ?? 1000;
    this.now = opts.now ?? (() => new Date().toISOString());
    this.replay = buildReplay(this.cityState);
  }

  // ---- REST ----
  health(): Promise<Health> { return Promise.resolve({ status: 'ok', version: 'mock' }); }
  llmStatus(): Promise<LlmStatus> { return Promise.resolve({ provider: 'none', model: null }); }
  city(): Promise<City> { return Promise.resolve(structuredClone(this.cityState)); }

  events(q: { since?: string; type?: EventType; limit?: number } = {}): Promise<Event[]> {
    let list = this.feed;
    if (q.since !== undefined) {
      const i = list.findIndex((e) => e.id === q.since);
      list = i >= 0 ? list.slice(i + 1) : list;
    }
    if (q.type !== undefined) list = list.filter((e) => e.type === q.type);
    if (q.limit !== undefined) list = list.slice(-q.limit);
    return Promise.resolve(structuredClone(list));
  }

  incidents(): Promise<IncidentSummary[]> {
    return Promise.resolve(
      this.incidentList.map((i) => ({
        id: i.id, zone_id: i.zone_id, hazard: i.hazard, band: i.band, status: i.status, opened_at: i.opened_at,
        opened_sim_time: i.opened_sim_time, closed_at: i.closed_at ?? null, run_count: i.runs.length, pending_approval_count: 0,
      })),
    );
  }

  incident(id: string): Promise<Incident> {
    const found = this.incidentList.find((i) => i.id === id);
    return found ? Promise.resolve(structuredClone(found)) : Promise.reject(new ApiError(404, { detail: 'Incident not found' }));
  }

  approvals(): Promise<Approval[]> { return Promise.resolve([]); }
  decide(_id: string, _body: ApprovalDecision): Promise<Approval> { return notInMock(); }
  actions(): Promise<Action[]> { return Promise.resolve([]); }
  action(_id: string): Promise<Action> { return Promise.reject(new ApiError(404, { detail: 'Action not found' })); }
  document(_docId: string): Promise<Document> { return notInMock(); }
  chunk(_chunkId: string): Promise<Chunk> { return notInMock(); }

  readonly simulation = {
    start: (body: { scenario: string; speed: number; seed?: number }): Promise<SimStatus> => {
      if (body.scenario !== PRIMARY_SCENARIO) {
        return Promise.reject(new ApiError(501, { detail: 'Only the primary scenario is scripted in mock mode' }));
      }
      this.scenario = body.scenario;
      this.speed = body.speed;
      this.run();
      return Promise.resolve(this.status());
    },
    pause: (): Promise<SimStatus> => {
      this.halt();
      return Promise.resolve(this.status());
    },
    resume: (): Promise<SimStatus> => {
      if (this.scenario !== null) this.run();
      return Promise.resolve(this.status());
    },
    reset: (): Promise<SimStatus> => {
      this.halt();
      this.cityState = structuredClone(this.initialCity);
      this.incidentList = [];
      this.feed = [];
      this.tick = 0;
      this.scenario = null;
      const snap = this.snapshotEvent();
      for (const s of this.sockets) s.deliver(snap);
      return Promise.resolve(this.status());
    },
    setSpeed: (speed: number): Promise<SimStatus> => {
      this.speed = speed;
      if (this.running) this.run();
      return Promise.resolve(this.status());
    },
    inject: (_body: InjectEvent): Promise<SimStatus> => notInMock(),
  };

  // ---- socket ----
  openSocket(handlers: SocketHandlers): SocketHandle {
    const socket = new MockSocket(handlers, (s) => this.sockets.delete(s));
    this.sockets.add(socket);
    socket.open(this.snapshotEvent());
    return socket;
  }

  // ---- internals ----
  private status(): SimStatus {
    return { scenario: this.scenario, running: this.running, speed: this.speed, sim_time: this.tick === 0 ? null : simTimeAt(this.tick), tick: this.tick };
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

  private stamp(e: Event): Event {
    return { ...e, ts: this.now() };
  }

  private emit(e: Event): void {
    this.feed.push(e);
    for (const s of this.sockets) s.deliver(e);
  }

  private tickOnce(): void {
    const step = this.replay[this.tick];
    if (!step) return;
    this.tick = step.tick;
    for (const raw of step.events) {
      const e = this.stamp(raw.type === 'sim.tick' ? { ...raw, payload: { ...raw.payload, speed: this.speed } } : raw);
      this.applyToCity(e);
      this.emit(e);
    }
    if (this.tick >= REPLAY_TICKS) {
      this.halt();
      const t = simTimeAt(this.tick);
      this.emit(this.stamp({ id: `evt_m_end_${String(this.seq++)}`, ts: '', sim_time: t, type: 'sim.tick', payload: { sim_time: t, tick: this.tick, running: false, speed: this.speed } }));
    }
  }

  /** Keep REST and later snapshots consistent with the replayed events. */
  private applyToCity(e: Event): void {
    if (e.type === 'zone.state') {
      const { zone_id: zoneId, prev_band: _prev, ...state } = e.payload;
      const zone = this.cityState.zones.find((z) => z.id === zoneId);
      if (zone) zone.state = state;
    } else if (e.type === 'sensor.reading') {
      const sensor = this.cityState.sensors.find((s) => s.id === e.payload.sensor_id);
      if (sensor) {
        sensor.last_value = e.payload.value;
        sensor.last_sim_time = e.sim_time;
      }
    } else if (e.type === 'incident.opened') {
      this.incidentList.push(structuredClone(e.payload));
    } else if (e.type === 'threat.escalated') {
      const incident = this.incidentList.find((i) => i.id === e.payload.incident_id && i.zone_id === e.payload.zone_id);
      if (incident) incident.band = e.payload.band;
    }
  }

  private snapshotEvent(): Event {
    const simTime = this.tick === 0 ? null : simTimeAt(this.tick);
    return {
      id: `evt_m_snapshot_${String(this.seq++)}`,
      ts: this.now(),
      sim_time: simTime,
      type: 'state.snapshot',
      payload: {
        city: structuredClone(this.cityState),
        sim: this.status(),
        llm: { provider: 'none', model: null },
        incidents: structuredClone(this.incidentList),
        approvals: [],
        actions: [],
        alerts: [],
      },
    };
  }
}
