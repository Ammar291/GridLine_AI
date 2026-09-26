import { Bar, CartesianGrid, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AXIS_TICK, CHART_MARGIN, GRID_STROKE, SERIES, Y_AXIS_WIDTH } from './chartTheme';
import type { TimelineRow } from './timelineData';

interface RainChartProps { rows: TimelineRow[]; width?: number; height?: number }

/** Single-series rain bars; no legend (the heading names it). Its hover syncs the index chart, which shows the readout. */
export function RainChart({ rows, width, height }: RainChartProps) {
  const chart = (
    <ComposedChart data={rows} syncId="risk" margin={CHART_MARGIN} width={width} height={height}>
      <CartesianGrid stroke={GRID_STROKE} vertical={false} />
      <XAxis dataKey="simTime" hide />
      <YAxis width={Y_AXIS_WIDTH} tick={AXIS_TICK} axisLine={false} tickLine={false} allowDecimals={false} tickCount={3} />
      <Tooltip content={() => null} cursor={{ fill: 'var(--color-raised)' }} isAnimationActive={false} />
      <Bar dataKey="rain" name={SERIES.rain.name} fill={SERIES.rain.color} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
    </ComposedChart>
  );
  return width !== undefined ? chart : <ResponsiveContainer width="100%" height="100%">{chart}</ResponsiveContainer>;
}
