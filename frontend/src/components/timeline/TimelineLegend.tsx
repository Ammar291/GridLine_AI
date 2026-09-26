import type { Hazard } from '@/api/types';
import { statusLabel } from '@/live/format';
import { SERIES } from './chartTheme';

function LineKey({ color, dashed = false, wash = false }: { color: string; dashed?: boolean; wash?: boolean }) {
  return (
    <svg width={14} height={8} viewBox="0 0 14 8" aria-hidden="true" className="shrink-0">
      {wash && <rect x={0} y={4} width={14} height={4} fill={color} fillOpacity={0.25} />}
      <path d="M0 4 H14" stroke={color} strokeWidth={2} strokeDasharray={dashed ? '3 2' : undefined} />
    </svg>
  );
}

interface TimelineLegendProps {
  hazard: Hazard;
  /** The threat detector's indices are charted (PENDING until the detector lands). */
  indices?: boolean;
  thresholds?: boolean;
}

/** Legend for the index chart: always shown, text in ink, keys mirror the marks drawn. Also names whose thresholds are drawn. */
export function TimelineLegend({ hazard, indices = true, thresholds = true }: TimelineLegendProps) {
  const items = [
    ...(indices ? [
      { name: SERIES.landslide.name, key: <LineKey color={SERIES.landslide.color} /> },
      { name: SERIES.flood.name, key: <LineKey color={SERIES.flood.color} /> },
    ] : []),
    { name: SERIES.saturation.name, key: <LineKey color={SERIES.saturation.color} wash /> },
    ...(thresholds ? [{ name: `${statusLabel(hazard)} thresholds`, key: <LineKey color="var(--color-ink-3)" dashed /> }] : []),
  ];
  return (
    <ul aria-label="Legend" className="flex items-center gap-3 text-[11px] text-ink-2">
      {items.map((it) => (
        <li key={it.name} className="flex items-center gap-1.5 whitespace-nowrap">{it.key}<span>{it.name}</span></li>
      ))}
    </ul>
  );
}
