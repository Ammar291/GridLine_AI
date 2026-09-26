import type { ReactNode } from 'react';

/** A cited id (a chunk, KG edge, live reading or event), shown as recorded. */
export function Cites({ ids }: { ids: readonly string[] }) {
  if (ids.length === 0) return null;
  return (
    <span className="inline-flex flex-wrap gap-1 align-middle">
      {ids.map((id) => (
        <span key={id} title={id} data-testid="citation"
          className="inline-block max-w-[220px] truncate rounded-[3px] border border-line px-1 text-[11px] leading-4 text-ink-2 tnum">
          {id}
        </span>
      ))}
    </span>
  );
}

type Tone = 'ok' | 'warn' | 'bad' | 'muted';
const TONES: Record<Tone, string> = {
  ok: 'border-ok text-ok-text',
  warn: 'border-band-watch text-band-watch-text',
  bad: 'border-band-critical text-band-critical-text',
  muted: 'border-line text-ink-2',
};

/** A small outlined status word. The word always names the state, so colour is never the only carrier. */
export function Tag({ tone, children }: { tone: Tone; children: ReactNode }) {
  return <span className={`inline-block shrink-0 rounded-[3px] border px-1 text-[11px] leading-4 ${TONES[tone]}`}>{children}</span>;
}

/** Secondary facts under a body: provider, counts, durations. */
export function Meta({ children }: { children: ReactNode }) {
  return <p className="text-[11px] text-ink-3 tnum">{children}</p>;
}
