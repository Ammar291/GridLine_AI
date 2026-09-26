import type { ApiClient, SocketHandle } from '@/api/client';
import type { Event } from '@/api/types';
import type { ConnectionStatus } from './types';

export interface LiveSocketOptions {
  client: ApiClient;
  onEvent: (e: Event) => void;
  onStatus: (s: ConnectionStatus) => void;
  backoffMs?: number[];
  setTimeoutImpl?: typeof setTimeout;
  clearTimeoutImpl?: typeof clearTimeout;
}

const DEFAULT_BACKOFF = [1000, 2000, 4000, 8000, 16000, 30000];

/** One live connection with exponential-backoff reconnect. Data already in the store is never cleared here. */
export class LiveSocket {
  private readonly opts: LiveSocketOptions;
  private readonly backoff: number[];
  private attempt = 0;
  private stopped = false;
  private handle: SocketHandle | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private generation = 0;

  constructor(opts: LiveSocketOptions) {
    this.opts = opts;
    this.backoff = opts.backoffMs ?? DEFAULT_BACKOFF;
  }

  start(): void {
    this.stopped = false;
    this.attempt = 0;
    this.connect();
  }

  /**
   * Reopen now to receive a fresh snapshot (the backend sends one per connection). Used after an engine reset, whose
   * new world is not otherwise sent. The connection status stays as it is; late frames of the old socket are dropped.
   */
  resync(): void {
    if (this.stopped) return;
    if (this.timer !== null) (this.opts.clearTimeoutImpl ?? clearTimeout)(this.timer);
    this.timer = null;
    this.generation++;
    this.handle?.close();
    this.handle = null;
    this.attempt = 0;
    this.connect(false);
  }

  stop(): void {
    this.stopped = true;
    if (this.timer !== null) (this.opts.clearTimeoutImpl ?? clearTimeout)(this.timer);
    this.timer = null;
    this.handle?.close();
    this.handle = null;
    this.opts.onStatus('closed');
  }

  private connect(announce = true): void {
    this.timer = null;
    if (this.stopped) return;
    const gen = ++this.generation;
    if (announce) this.opts.onStatus(this.attempt === 0 ? 'connecting' : 'reconnecting');
    this.handle = this.opts.client.openSocket({
      onOpen: () => {
        if (gen !== this.generation) return;
        this.attempt = 0;
        this.opts.onStatus('open');
      },
      onEvent: (e) => {
        if (gen === this.generation) this.opts.onEvent(e);
      },
      onClose: () => {
        if (gen === this.generation) this.scheduleReconnect();
      },
      onError: () => {
        /* onClose follows an error; reconnect is scheduled there */
      },
    });
  }

  private scheduleReconnect(): void {
    if (this.stopped || this.timer !== null) return;
    this.generation++; // ignore anything further from the dead socket
    this.opts.onStatus('reconnecting');
    const delay = this.backoff[Math.min(this.attempt, this.backoff.length - 1)] ?? 30000;
    this.attempt++;
    const set = this.opts.setTimeoutImpl ?? setTimeout;
    this.timer = set(() => { this.connect(); }, delay);
  }
}
