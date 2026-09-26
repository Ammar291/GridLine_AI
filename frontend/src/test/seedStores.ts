import type { Event } from '@/api/types';
import { applyEvent } from '@/live/applyEvent';
import { useLiveStore } from '@/live/liveStore';
import { initialLiveState } from '@/live/types';
import { useUiStore } from '@/ui/uiStore';
import { snapshotEventFixture } from './fixtures/events';

/** Resets both stores; seeds the live store with the snapshot fixture plus any extra events. */
export function seedLive(extra: Event[] = [], opts: { snapshot?: boolean } = {}): void {
  useUiStore.getState().reset();
  let s = initialLiveState('mock');
  if (opts.snapshot !== false) s = applyEvent(s, snapshotEventFixture);
  for (const e of extra) s = applyEvent(s, e);
  useLiveStore.setState(s);
}
