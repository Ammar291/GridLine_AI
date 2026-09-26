import { describe, expect, it } from 'vitest';
import type { EventOf, SourceStatus } from '@/api/types';
import { eventsFixture as ev, snapshotEventFixture } from '@/test/fixtures/events';
import { applyEvent } from './applyEvent';
import { compass, dataModeOf, imdCategory } from './liveWeather';
import { initialLiveState } from './types';

const LIVE: SourceStatus = {
  mode: 'live', label: 'LIVE — Kalyan-Dombivli', city: 'Kalyan-Dombivli', provider: 'Open-Meteo', latitude: 19.235, longitude: 73.13,
  poll_seconds: 300, last_updated: '2026-09-26T10:31:00Z', last_error: null,
};
const DEMO: SourceStatus = {
  mode: 'demo', label: 'DEMO — Nandipur', city: 'Nandipur', provider: 'Synthetic simulation', latitude: null, longitude: null,
  poll_seconds: null, last_updated: null, last_error: null,
};

export const sourceEvent = (payload: SourceStatus): EventOf<'source.status'> => ({
  event_id: `src-${payload.mode}`, timestamp: '2026-09-26T10:31:00Z', sim_time: '2026-09-26T10:31:00Z', event_type: 'source.status',
  source: 'source:manager', location: null, severity: 'info', incident_id: null, payload,
});

const liveObservation: EventOf<'weather.observation'> = {
  ...ev['weather.observation'], event_id: 'live-1', source: 'open-meteo:forecast-api', location: 'kalyan-dombivli', severity: 'info',
  sim_time: '2026-09-26T10:30:00Z',
  payload: {
    station_id: 'OM-KDMC', rainfall_intensity_mm_h: 0, cumulative_rainfall_24h_mm: 0.8, temperature_c: 30.3, wind_speed_kmh: 13.1,
    wind_direction_deg: 262,
  },
};

describe('data mode in the live store', () => {
  it('defaults to demo and follows the snapshot and source.status events', () => {
    let s = applyEvent(initialLiveState('http'), snapshotEventFixture);
    expect(dataModeOf(s)).toBe('demo');
    s = applyEvent(s, sourceEvent(LIVE));
    expect(dataModeOf(s)).toBe('live');
    expect(s.source?.label).toBe('LIVE — Kalyan-Dombivli');
  });

  it('switching mode clears the other city\'s feed and readings', () => {
    let s = applyEvent(applyEvent(initialLiveState('http'), snapshotEventFixture), sourceEvent(DEMO));
    s = applyEvent(s, ev['weather.observation']);
    expect(s.telemetry.hillview).toHaveLength(1);
    s = applyEvent(s, sourceEvent(LIVE));
    expect(s.telemetry).toEqual({});
    expect(s.feed.map((e) => e.event_type)).toEqual(['source.status']);
  });

  it('in live mode weather events fill the live conditions, not the Nandipur world', () => {
    let s = applyEvent(applyEvent(initialLiveState('http'), snapshotEventFixture), sourceEvent(LIVE));
    const zonesBefore = s.world?.zones;
    s = applyEvent(s, liveObservation);
    s = applyEvent(s, { ...ev['weather.forecast'], source: 'open-meteo:forecast-api' });
    expect(s.liveWeather.observation).toMatchObject({ station_id: 'OM-KDMC', cumulative_rainfall_24h_mm: 0.8, observedAt: '2026-09-26T10:30:00Z' });
    expect(s.liveWeather.forecast?.summary).toBe('fixture: heavy rain warning');
    expect(s.world?.zones).toBe(zonesBefore);
    expect(s.telemetry).toEqual({});
  });
});

describe('helpers', () => {
  it('names the IMD 24-hour rainfall category', () => {
    expect(imdCategory(0)).toBe('No rain');
    expect(imdCategory(0.8)).toBe('Very light');
    expect(imdCategory(20)).toBe('Moderate');
    expect(imdCategory(64.5)).toBe('Heavy');
    expect(imdCategory(150)).toBe('Very heavy');
    expect(imdCategory(210)).toBe('Extremely heavy');
  });

  it('turns a wind direction into a compass point', () => {
    expect(compass(0)).toBe('N');
    expect(compass(262)).toBe('W');
    expect(compass(135)).toBe('SE');
  });
});
