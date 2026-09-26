import type { DataMode, SourceStatus } from '@/api/types';
import { useSetDataMode } from '@/api/queries';
import { dataModeOf, fmtIst } from '@/live/liveWeather';
import { useLiveStore } from '@/live/liveStore';

const MODES: readonly DataMode[] = ['live', 'demo'];
const FALLBACK_LABEL: Record<DataMode, string> = { live: 'LIVE — Kalyan-Dombivli', demo: 'DEMO — Nandipur' };

function detail(source: SourceStatus | null): string {
  if (source?.mode !== 'live') return 'Synthetic city: every place, sensor and event is invented';
  const every = source.poll_seconds ? `, refreshes every ${String(Math.round(source.poll_seconds / 60))} min` : '';
  if (source.last_updated) return `Open-Meteo model weather, updated ${fmtIst(source.last_updated)}${every}`;
  if (source.last_error) return `Open-Meteo unreachable, retrying${every}`;
  return 'Fetching Open-Meteo weather…';
}

/** Always visible: which city and data source the whole dashboard is showing, and the switch between them. */
export function DataModeBar() {
  const source = useLiveStore((s) => s.source);
  const apiMode = useLiveStore((s) => s.mode);
  const setMode = useSetDataMode();
  const mode = dataModeOf({ source });
  const live = mode === 'live';

  return (
    <div className="flex items-center gap-4 h-10 px-4 bg-panel border-b border-line">
      <span data-testid="data-mode-label" className={`condensed flex items-center gap-2 text-[15px] font-semibold tracking-wide ${live ? 'text-accent-strong' : 'text-ink'}`}>
        <span aria-hidden="true" className={`inline-block size-2.5 rounded-full ${live ? 'bg-accent animate-pulse' : 'bg-ink-3'}`} />
        {source?.label ?? FALLBACK_LABEL[mode]}
      </span>
      <span className="text-[12px] text-ink-2 truncate">{detail(source)}</span>
      {setMode.isError && <span role="alert" className="text-[12px] text-band-critical-text">{`Switch failed: ${setMode.error.message}`}</span>}
      <div role="radiogroup" aria-label="Data mode" className="ml-auto inline-flex shrink-0 gap-0.5 rounded-[4px] border border-line-strong bg-page p-0.5">
        {MODES.map((m) => {
          const unavailable = m === 'live' && apiMode === 'mock';
          return (
            <button
              key={m}
              type="button"
              role="radio"
              aria-checked={mode === m}
              disabled={setMode.isPending || unavailable}
              title={unavailable ? 'LIVE mode needs the backend' : undefined}
              onClick={() => { if (mode !== m) setMode.mutate(m); }}
              className={`h-7 w-16 rounded-[3px] text-[12px] font-semibold tracking-wider disabled:opacity-50 ${
                mode === m ? (m === 'live' ? 'bg-accent text-page' : 'bg-line-strong text-ink') : 'text-ink-2 hover:text-ink'
              }`}
            >
              {m.toUpperCase()}
            </button>
          );
        })}
      </div>
    </div>
  );
}
