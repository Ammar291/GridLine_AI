import type { ReactNode } from 'react';
import type { Severity } from '@/api/types';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { Panel } from '@/components/ui/Panel';
import { compass, fmtIst, imdCategory } from '@/live/liveWeather';
import { useLiveStore } from '@/live/liveStore';

const num = (v: number, digits = 1) => String(Number(v.toFixed(digits)));
const BAND_TEXT: Partial<Record<Severity, string>> = {
  moderate: 'text-band-watch-text', high: 'text-band-warning-text', critical: 'text-band-critical-text',
};

function Reading({ label, value, note }: { label: string; value: string; note?: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 p-4 bg-page border border-line rounded-[3px]">
      <span className="text-[11px] uppercase tracking-wider text-ink-2">{label}</span>
      <span className="tnum text-[28px] leading-8 font-semibold text-ink">{value}</span>
      {note !== undefined && <span className="text-[12px] text-ink-2">{note}</span>}
    </div>
  );
}

/** LIVE mode's main panel (in place of the Nandipur map): the latest real Open-Meteo reading for the city. */
export function LiveConditions() {
  const source = useLiveStore((s) => s.source);
  const obs = useLiveStore((s) => s.liveWeather.observation);
  const forecast = useLiveStore((s) => s.liveWeather.forecast);
  const city = source?.city ?? 'Kalyan-Dombivli';

  let body;
  if (obs === null && source?.last_error) {
    body = <ErrorState message={`Live weather is unavailable: ${source.last_error}. No readings are shown until Open-Meteo answers.`} />;
  } else if (obs === null) {
    body = <LoadingState rows={3} label="Fetching live weather" />;
  } else {
    const day = obs.cumulative_rainfall_24h_mm ?? 0;
    const band = BAND_TEXT[obs.severity];
    body = (
      <div className="flex flex-col gap-3 p-3">
        {source?.last_error && (
          <p role="alert" className="text-[12px] text-band-warning-text">{`Last refresh failed (${source.last_error}); showing the reading from ${fmtIst(obs.observedAt)}.`}</p>
        )}
        <div className="grid grid-cols-2 gap-3">
          <Reading label="Rain, last hour" value={`${num(obs.rainfall_intensity_mm_h ?? 0)} mm/h`} />
          <Reading label="Rain, last 24 h" value={`${num(day)} mm`} note={`IMD: ${imdCategory(day)}`} />
          <Reading label="Temperature" value={obs.temperature_c == null ? '—' : `${num(obs.temperature_c)} °C`} />
          <Reading
            label="Wind"
            value={obs.wind_speed_kmh == null ? '—' : `${num(obs.wind_speed_kmh)} km/h`}
            note={obs.wind_direction_deg == null ? undefined : `from ${compass(obs.wind_direction_deg)} (${String(Math.round(obs.wind_direction_deg))}°)`}
          />
        </div>
        <p className="text-[12px] text-ink-2">
          Reading band: <span className={`font-medium ${band ?? 'text-ink'}`}>{obs.severity}</span>
          {forecast && <>{' · '}{forecast.summary}</>}
        </p>
        <p className="text-[11px] text-ink-3">
          {`Observed ${fmtIst(obs.observedAt)}. Source: Open-Meteo model analysis and forecast for the grid cell over ${city}`}
          {source?.latitude != null && source.longitude != null && ` (${num(source.latitude, 3)}° N, ${num(source.longitude, 3)}° E)`}
          . Not a physical rain gauge. Bands use IMD 24-hour rainfall categories.
        </p>
      </div>
    );
  }
  return <Panel title={`Live conditions — ${city}`} testId="live-conditions">{body}</Panel>;
}
