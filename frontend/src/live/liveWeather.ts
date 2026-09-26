// LIVE mode's slice of the store: the data mode, the latest Open-Meteo observation and forecast, and their wording.
import type { DataMode, EventOf } from '@/api/types';
import type { LiveState } from './types';

export function dataModeOf(state: Pick<LiveState, 'source'>): DataMode {
  return state.source?.mode ?? 'demo';
}

export function applyLiveWeather(state: LiveState, e: EventOf<'weather.observation' | 'weather.forecast'>): LiveState {
  if (e.event_type === 'weather.forecast') return { ...state, liveWeather: { ...state.liveWeather, forecast: e.payload } };
  const observation = { ...e.payload, severity: e.severity, observedAt: e.sim_time };
  return { ...state, liveWeather: { ...state.liveWeather, observation } };
}

/** IMD's 24-hour rainfall categories (mm), highest first. */
const IMD_24H: readonly [number, string][] = [
  [204.5, 'Extremely heavy'], [115.6, 'Very heavy'], [64.5, 'Heavy'], [15.6, 'Moderate'], [2.5, 'Light'], [0.1, 'Very light'],
];

export function imdCategory(mm24h: number): string {
  return IMD_24H.find(([min]) => mm24h >= min)?.[1] ?? 'No rain';
}

const POINTS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'] as const;

export function compass(deg: number): string {
  return POINTS[Math.round((((deg % 360) + 360) % 360) / 45) % 8] ?? 'N';
}

const IST = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kolkata', hour: '2-digit', minute: '2-digit', hour12: false });

/** 'HH:mm IST' (Kalyan-Dombivli local time) from an ISO timestamp, '—' when missing. */
export function fmtIst(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : `${IST.format(d)} IST`;
}
