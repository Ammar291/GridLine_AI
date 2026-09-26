import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { EmptyState } from '@/components/ui/EmptyState';
import { Panel } from '@/components/ui/Panel';
import { AXIS_TICK, GRID_STROKE, SERIES, Y_AXIS_WIDTH } from '@/components/timeline/chartTheme';
import { fmtIst } from '@/live/liveWeather';
import { useLiveStore } from '@/live/liveStore';

interface Row { time: string; hour: string; mm: number; chance: number | null }

function ForecastTooltip({ row }: { row: Row }) {
  return (
    <div className="bg-raised border border-line rounded-[3px] px-2.5 py-1.5 text-[11px] leading-4">
      <p className="tnum text-ink-2 mb-0.5">{`Hour ending ${fmtIst(row.time)}`}</p>
      <p><span className="tnum text-ink font-medium">{`${String(row.mm)} mm`}</span> <span className="text-ink-2">precipitation</span></p>
      {row.chance !== null && <p><span className="tnum text-ink font-medium">{`${String(Math.round(row.chance * 100))}%`}</span> <span className="text-ink-2">chance</span></p>}
    </div>
  );
}

/** LIVE mode's timeline: Open-Meteo's hourly precipitation for the next 24 h. Single series, so no legend. */
export function LiveForecast() {
  const forecast = useLiveStore((s) => s.liveWeather.forecast);
  const rows: Row[] = (forecast?.hourly ?? []).map((h) => ({
    time: h.time, hour: fmtIst(h.time).slice(0, 5), mm: h.precipitation_mm, chance: h.probability,
  }));
  const body = rows.length === 0 || forecast === null
    ? <EmptyState title="The hourly forecast appears here once Open-Meteo answers." />
    : (
      <div className="flex flex-col h-full min-h-0 px-2 pt-1">
        <h3 className="px-1 text-[11px] leading-4 font-medium text-ink-2">
          {`Precipitation per hour (mm) · ${String(forecast.expected_total_mm)} mm expected, peak ${String(forecast.peak_intensity_mm_h)} mm/h`}
        </h3>
        <div className="flex-1 min-h-0">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
              <CartesianGrid stroke={GRID_STROKE} vertical={false} />
              <XAxis dataKey="hour" tick={AXIS_TICK} axisLine={false} tickLine={false} interval={3} />
              <YAxis width={Y_AXIS_WIDTH} tick={AXIS_TICK} axisLine={false} tickLine={false} tickCount={3} />
              <Tooltip
                cursor={{ fill: 'var(--color-raised)' }}
                isAnimationActive={false}
                content={({ active, payload }) => {
                  const row = payload[0]?.payload as Row | undefined;
                  return active && row ? <ForecastTooltip row={row} /> : null;
                }}
              />
              <Bar dataKey="mm" name="Precipitation" fill={SERIES.rain.color} radius={[4, 4, 0, 0]} maxBarSize={24} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    );
  return <Panel title="Precipitation forecast, next 24 h" testId="live-forecast">{body}</Panel>;
}
