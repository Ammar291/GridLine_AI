import { useMemo } from 'react';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { Panel } from '@/components/ui/Panel';
import { eventGroup } from '@/live/describeEvent';
import { useLiveStore } from '@/live/liveStore';
import { useUiStore } from '@/ui/uiStore';
import { EventRow } from './EventRow';
import { FEED_FILTERS, FEED_MOTION_CSS, type FeedFilter } from './eventGroups';
import { FeedFilters } from './FeedFilters';
import { useAutoScroll } from './useAutoScroll';

/** Event ids restart at every engine reset, so the wall timestamp is part of the key. */
const rowKey = (e: { event_id: string; timestamp: string }) => `${e.event_id}@${e.timestamp}`;

/** Live event stream, newest at the bottom. Keeps its rows through reconnects (only an empty feed shows a state). */
export function EventFeed() {
  const feed = useLiveStore((s) => s.feed);
  const city = useLiveStore((s) => s.city);
  const connection = useLiveStore((s) => s.connection);
  const filter = useUiStore((s) => s.feedFilter);
  const setFeedFilter = useUiStore((s) => s.setFeedFilter);
  const selectIncident = useUiStore((s) => s.selectIncident);

  const rows = useMemo(() => (filter === 'all' ? feed : feed.filter((e) => eventGroup(e.event_type) === filter)), [feed, filter]);
  const keys = useMemo(() => rows.map(rowKey), [rows]);
  const { ref, pending, onScroll, jumpToLatest } = useAutoScroll(keys);

  const onFilter = (f: FeedFilter) => {
    setFeedFilter(f);
    jumpToLatest();
  };

  let body;
  if (feed.length === 0) {
    if (connection === 'connecting') body = <LoadingState rows={4} label="Connecting to the live stream" />;
    else if (connection === 'open') body = <EmptyState title="Events appear here as the city runs." />;
    else body = <ErrorState message="No live connection. Retrying automatically." />;
  } else if (rows.length === 0) {
    const noun = FEED_FILTERS.find((f) => f.value === filter)?.noun ?? '';
    body = <EmptyState title={`No ${noun} events yet.`} />;
  } else {
    body = (
      <div className="relative h-full">
        <div ref={ref} onScroll={onScroll} data-testid="event-feed-scroll" className="h-full overflow-auto py-1">
          <ul role="log" aria-live="polite" aria-label="Live events" className="flex flex-col gap-px">
            {rows.map((e) => (
              <EventRow key={rowKey(e)} event={e} city={city} onSelectIncident={selectIncident} />
            ))}
          </ul>
        </div>
        {pending > 0 && (
          <Button variant="primary" size="sm" onClick={jumpToLatest} className="absolute bottom-2 left-1/2 -translate-x-1/2">
            {`New events (${String(pending)})`}
          </Button>
        )}
      </div>
    );
  }

  return (
    <Panel title="Live events" count={rows.length} actions={<FeedFilters value={filter} onChange={onFilter} />} testId="event-feed">
      <style href="gl-feed-motion" precedence="default">{FEED_MOTION_CSS}</style>
      {body}
    </Panel>
  );
}
