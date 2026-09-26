import { useLayoutEffect, useMemo, useRef, useState } from 'react';

/** Distance from the bottom (px) that still counts as "at the bottom". */
const BOTTOM_SLACK_PX = 8;

/**
 * Keeps a scroll container pinned to its newest row unless the reader scrolled up.
 * While detached, `pending` counts rows added after the last row the reader had seen.
 * Rows are identified by key so the count survives the feed cap dropping old rows.
 */
export function useAutoScroll(keys: readonly string[]) {
  const ref = useRef<HTMLDivElement>(null);
  const [seenKey, setSeenKey] = useState<string | null>(null);
  const detached = seenKey !== null;
  const lastKey = keys.at(-1) ?? null;

  useLayoutEffect(() => {
    const el = ref.current;
    if (el && !detached) el.scrollTop = el.scrollHeight;
  }, [lastKey, detached]);

  const pending = useMemo(() => {
    if (seenKey === null) return 0;
    const i = keys.lastIndexOf(seenKey);
    return i === -1 ? keys.length : keys.length - 1 - i;
  }, [keys, seenKey]);

  const onScroll = () => {
    const el = ref.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < BOTTOM_SLACK_PX;
    if (atBottom && detached) setSeenKey(null);
    else if (!atBottom && !detached) setSeenKey(lastKey);
  };

  const jumpToLatest = () => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
    setSeenKey(null);
  };

  return { ref, pending, onScroll, jumpToLatest };
}
