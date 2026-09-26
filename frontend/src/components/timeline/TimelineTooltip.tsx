import { fmtSimTime } from '@/live/format';
import { SERIES, TOOLTIP_ORDER } from './chartTheme';
import type { TimelineMarker, TimelineRow } from './timelineData';

/** One compact readout of every series at the hovered sim time. Values lead in ink, names follow, a line key carries identity. */
export function TimelineTooltip({ row, markers }: { row: TimelineRow; markers: TimelineMarker[] }) {
  return (
    <div className="bg-raised border border-line rounded-[3px] px-2.5 py-1.5 text-[11px] leading-4">
      <p className="tnum text-ink-2 mb-0.5">Sim time {fmtSimTime(row.simTime)}</p>
      <ul className="grid grid-cols-2 gap-x-4">
        {TOOLTIP_ORDER.map((key) => (
          <li key={key} className="flex items-center gap-2">
            <span aria-hidden="true" className="inline-block w-3 h-0.5 rounded-full" style={{ background: SERIES[key].color }} />
            <span className="tnum text-ink font-medium">{SERIES[key].format(row[key])}</span>
            <span className="text-ink-2">{SERIES[key].name}</span>
          </li>
        ))}
      </ul>
      {markers.length > 0 && (
        <ul className="mt-1 pt-1 border-t border-line flex flex-col text-ink max-w-72">
          {markers.map((m) => <li key={m.id}>{m.label}</li>)}
        </ul>
      )}
    </div>
  );
}
