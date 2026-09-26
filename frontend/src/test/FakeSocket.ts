import type { ApiClient, SocketHandlers, SocketHandle } from '@/api/client';

/** Records every openSocket call so tests can drive onOpen/onEvent/onClose by hand. */
export class FakeSocketFactory {
  handlers: SocketHandlers[] = [];
  closed = 0;
  openSocket = (h: SocketHandlers): SocketHandle => {
    this.handlers.push(h);
    return { close: () => { this.closed++; } };
  };
  last(): SocketHandlers {
    const h = this.handlers.at(-1);
    if (!h) throw new Error('no socket');
    return h;
  }
  attach(client: ApiClient): ApiClient {
    return { ...client, openSocket: this.openSocket };
  }
}
