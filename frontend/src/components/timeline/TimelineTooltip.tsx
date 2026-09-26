import { fmtSimTime } from '@/live/format';
import { SERIES, TOOLTIP_ORDER } from './chartTheme';
import type { TimelineMarker, TimelineRow } from './timelineData';

/**
 * One compact readout of the series with a value at the hovered sim time. Values lead in ink, names follow, a line key
 * carries identity. A series the zone has no reading for (no gauge, or no detector yet) is left out.
 */
export function TimelineTooltip({ row, markers }: { row: TimelineRow; markers: TimelineMarker[] }) {
  const values = TOOLTIP_ORDER.flatMap((key) => {
    const v = row[key];
    return v === null ? [] : [{ key, text: SERIES[key].format(v) }];
  });
  return (
    <div className="bg-raised border border-line rounded-[3px] px-2.5 py-1.5 text-[11px] leading-4">
      <p className="tnum text-ink-2 mb-0.5">Sim time {fmtSimTime(row.simTime)}</p>
      <ul className="grid grid-cols-2 gap-x-4">
        {values.map(({ key, text }) => (
          <li key={key} className="flex items-center gap-2">
            <span aria-hidden="true" className="inline-block w-3 h-0.5 rounded-full" style={{ background: SERIES[key].color }} />
            <span className="tnum text-ink font-medium">{text}</span>
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
