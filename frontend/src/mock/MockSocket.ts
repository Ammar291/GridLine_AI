import type { SocketHandle, SocketHandlers } from '@/api/client';
import type { Event } from '@/api/types';

/** In-memory socket handed out by MockApiClient. The client's replay timer pushes events through deliver(). */
export class MockSocket implements SocketHandle {
  private closed = false;
  private readonly handlers: SocketHandlers;
  private readonly onDetach: (s: MockSocket) => void;

  constructor(handlers: SocketHandlers, onDetach: (s: MockSocket) => void) {
    this.handlers = handlers;
    this.onDetach = onDetach;
  }

  open(snapshot: Event): void {
    this.handlers.onOpen();
    this.deliver(snapshot);
  }

  deliver(e: Event): void {
    if (!this.closed) this.handlers.onEvent(e);
  }

  close(): void {
    if (this.closed) return;
    this.closed = true;
    this.onDetach(this);
  }
}
