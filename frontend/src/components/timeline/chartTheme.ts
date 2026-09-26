// Shared chart anatomy so the two stacked charts line up on one x axis. Colours are the validated viz tokens only;
// band colours never colour a series (they appear only as threshold label text).
import { fmtIndex, fmtPct } from '@/live/format';
import type { TimelineRow } from './timelineData';

/** Right margin leaves room for the threshold labels; both charts share it so their plot areas align. */
export const CHART_MARGIN = { top: 6, right: 68, bottom: 0, left: 0 };
export const Y_AXIS_WIDTH = 40;
export const AXIS_TICK = { fill: 'var(--color-ink-2)', fontSize: 11 };
export const GRID_STROKE = 'var(--color-viz-grid)';
export const AXIS_STROKE = 'var(--color-viz-axis)';
/** Milestone markers ride along the top of the 0–1 index axis. */
export const MARKER_Y = 0.97;

export type SeriesKey = 'rain' | 'landslide' | 'flood' | 'saturation' | 'water';

export const SERIES: Record<SeriesKey, { name: string; color: string; format: (x: number) => string }> = {
  rain: { name: 'Rain intensity', color: 'var(--color-viz-rain)', format: (x) => `${String(Math.round(x))} mm/h` },
  landslide: { name: 'Landslide index', color: 'var(--color-viz-landslide)', format: fmtIndex },
  flood: { name: 'Flood index', color: 'var(--color-viz-flood)', format: fmtIndex },
  saturation: { name: 'Saturation', color: 'var(--color-viz-saturation)', format: fmtPct },
  water: { name: 'Standing water', color: 'var(--color-viz-flood)', format: (x) => `${String(Math.round(x))} cm` },
};

/** Tooltip reading order, two per row: the inputs (rain, saturation), then the indices they drive. */
export const TOOLTIP_ORDER: readonly SeriesKey[] = ['rain', 'saturation', 'landslide', 'flood', 'water'];

export function isTimelineRow(x: unknown): x is TimelineRow {
  return typeof x === 'object' && x !== null && 'simTime' in x && 'landslide' in x && 'rain' in x;
}
