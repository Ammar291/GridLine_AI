import {
  Area, CartesianGrid, ComposedChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis, type DotProps, type TooltipContentProps,
} from 'recharts';
import { fmtSimTime } from '@/live/format';
import { AXIS_STROKE, AXIS_TICK, CHART_MARGIN, GRID_STROKE, SERIES, Y_AXIS_WIDTH, isTimelineRow } from './chartTheme';
import { groupMarkers, type TimelineMarker, type TimelineRow } from './timelineData';
import { TimelineTooltip } from './TimelineTooltip';

interface WaterChartProps { rows: TimelineRow[]; markers: TimelineMarker[]; width?: number; height?: number }

const ACTIVE_DOT = { r: 4, stroke: 'var(--color-panel)', strokeWidth: 2 };
/** The axis never shrinks below this, so a few centimetres do not look like a flood. */
const MIN_TOP_CM = 30;

/** Standing water for a zone with no soil or detector readings (a flood plain): one series, one cm axis, milestones on top. */
export function WaterChart({ rows, markers, width, height }: WaterChartProps) {
  const top = Math.max(MIN_TOP_CM, ...rows.map((r) => r.water ?? 0)) * 1.1;
  const renderTooltip = ({ active, payload }: TooltipContentProps) => {
    const row: unknown = payload[0]?.payload;
    if (!active || !isTimelineRow(row)) return null;
    return <TimelineTooltip row={row} markers={markers.filter((m) => m.simTime === row.simTime)} />;
  };
  const chart = (
    <ComposedChart data={rows} syncId="risk" margin={CHART_MARGIN} width={width} height={height}>
      <CartesianGrid stroke={GRID_STROKE} vertical={false} />
      <XAxis dataKey="simTime" scale="band" tickFormatter={(v: string) => fmtSimTime(v)} tick={AXIS_TICK} stroke={AXIS_STROKE} tickLine={false}
        interval="preserveStartEnd" minTickGap={28} />
      <YAxis domain={[0, Math.ceil(top)]} tickFormatter={(v: number) => `${String(Math.round(v))} cm`} width={Y_AXIS_WIDTH}
        tick={AXIS_TICK} axisLine={false} tickLine={false} tickCount={4} />
      <Tooltip content={renderTooltip} cursor={{ stroke: AXIS_STROKE, strokeWidth: 1 }} isAnimationActive={false} />
      <Area type="linear" dataKey="water" name={SERIES.water.name} stroke={SERIES.water.color} fill={SERIES.water.color}
        fillOpacity={0.25} strokeWidth={2} dot={false} activeDot={ACTIVE_DOT} isAnimationActive={false} />
      {groupMarkers(markers).map((m) => (
        <ReferenceDot key={m.simTime} x={m.simTime} y={top * 0.97} r={4}
          shape={(p: DotProps) => (
            <g data-milestone-kind={m.kind}>
              <circle cx={p.cx} cy={p.cy} r={4} fill="var(--color-ink)" stroke="var(--color-panel)" strokeWidth={2} />
              <title>{m.labels.join('\n')}</title>
            </g>
          )} />
      ))}
    </ComposedChart>
  );
  return width !== undefined ? chart : <ResponsiveContainer width="100%" height="100%">{chart}</ResponsiveContainer>;
}
