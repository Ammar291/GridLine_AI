import {
  Area, CartesianGrid, ComposedChart, Line, ReferenceDot, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
  type DotProps, type TooltipContentProps,
} from 'recharts';
import { fmtSimTime } from '@/live/format';
import { AXIS_STROKE, AXIS_TICK, CHART_MARGIN, GRID_STROKE, MARKER_Y, SERIES, Y_AXIS_WIDTH, isTimelineRow } from './chartTheme';
import { groupMarkers, type ThresholdLine, type TimelineMarker, type TimelineRow } from './timelineData';
import { TimelineTooltip } from './TimelineTooltip';

interface IndexChartProps {
  rows: TimelineRow[];
  thresholds: ThresholdLine[];
  markers: TimelineMarker[];
  width?: number;
  height?: number;
}

const ACTIVE_DOT = { r: 4, stroke: 'var(--color-panel)', strokeWidth: 2 };

/** Landslide and flood indices as the emphasised lines, saturation as grey context with a 10% wash, one 0–1 axis. */
export function IndexChart({ rows, thresholds, markers, width, height }: IndexChartProps) {
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
      <YAxis domain={[0, 1]} ticks={[0, 0.25, 0.5, 0.75, 1]} tickFormatter={(v: number) => v.toFixed(2)} width={Y_AXIS_WIDTH}
        tick={AXIS_TICK} axisLine={false} tickLine={false} />
      {thresholds.map((t) => (
        <ReferenceLine key={t.band} y={t.value} stroke="var(--color-ink-3)" strokeDasharray="4 4"
          label={{ value: t.label, position: 'right', fill: `var(--color-band-${t.band}-text)`, fontSize: 10 }} />
      ))}
      <Tooltip content={renderTooltip} cursor={{ stroke: AXIS_STROKE, strokeWidth: 1 }} isAnimationActive={false} />
      <Area type="linear" dataKey="saturation" name={SERIES.saturation.name} stroke={SERIES.saturation.color} fill={SERIES.saturation.color}
        fillOpacity={0.1} strokeWidth={2} dot={false} activeDot={ACTIVE_DOT} isAnimationActive={false} />
      <Line type="linear" dataKey="landslide" name={SERIES.landslide.name} stroke={SERIES.landslide.color} strokeWidth={2}
        dot={false} activeDot={ACTIVE_DOT} isAnimationActive={false} />
      <Line type="linear" dataKey="flood" name={SERIES.flood.name} stroke={SERIES.flood.color} strokeWidth={2}
        dot={false} activeDot={ACTIVE_DOT} isAnimationActive={false} />
      {groupMarkers(markers).map((m) => (
        <ReferenceDot key={m.simTime} x={m.simTime} y={MARKER_Y} r={4}
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
