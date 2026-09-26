import type { Event } from '@/api/types';
import { applyEvent } from '@/live/applyEvent';
import { useLiveStore } from '@/live/liveStore';
import { initialLiveState } from '@/live/types';
import { useUiStore } from '@/ui/uiStore';
import { executedActionFixture } from './fixtures/action';
import { pendingApprovalFixture } from './fixtures/approval';
import { eventsFixture, snapshotEventFixture } from './fixtures/events';

/**
 * Resets both stores; seeds the live store with the snapshot fixture, the PENDING incident (opened), its pending
 * approval and its executed action (as tables, so their state changes are not replayed onto the world), then `extra`.
 */
export function seedLive(extra: Event[] = [], opts: { snapshot?: boolean } = {}): void {
  useUiStore.getState().reset();
  let s = initialLiveState('mock');
  if (opts.snapshot !== false) {
    s = applyEvent(s, snapshotEventFixture);
    s = applyEvent(s, eventsFixture['incident.opened']);
    s = {
      ...s,
      approvals: { [pendingApprovalFixture.id]: pendingApprovalFixture },
      actions: { [executedActionFixture.id]: executedActionFixture },
    };
  }
  for (const e of extra) s = applyEvent(s, e);
  useLiveStore.setState(s);
}
