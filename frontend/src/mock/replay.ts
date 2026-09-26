// Scripted primary-scenario simulation and detector events for mock mode (spec F1, section 8).
// This is scripted simulation, which CLAUDE.md permits: zone states come from fixed formulas, not from any model.
// It never emits agent, approval, action, verification or re-plan events: those would be fabricated AI output.
import type { Band, City, Event, EventOf, Hazard, Incident, ZoneState } from '@/api/types';

export interface ReplayStep { tick: number; events: Event[] }

export const REPLAY_START_SIM_TIME = '2026-07-14T06:00:00';
export const REPLAY_TICKS = 72;
const TICK_MINUTES = 5;

export const HILLVIEW_ZONE_ID = 'Z-HV';
export const RIVERSIDE_ZONE_ID = 'Z-RS';
export const MOCK_INCIDENT_ID = 'inc_mock_1';
const RAIN_SENSOR_ID = 'RG-02';
const SOIL_SENSOR_ID = 'SM-01';
const CHANNEL_SENSOR_ID = 'CL-D7';

export function simTimeAt(tick: number): string {
  const start = Date.parse(`${REPLAY_START_SIM_TIME}Z`);
  return new Date(start + tick * TICK_MINUTES * 60_000).toISOString().slice(0, 19);
}

const BAND_ORDER: readonly Band[] = ['normal', 'watch', 'warning', 'critical'];
const rank = (b: Band) => BAND_ORDER.indexOf(b);

/** Band for one hazard index against the city's thresholds. */
export function indexBand(bands: City['bands'], hazard: Hazard, value: number): Band {
  const t = bands[hazard];
  if (value >= t.critical) return 'critical';
  if (value >= t.warning) return 'warning';
  if (value >= t.watch) return 'watch';
  return 'normal';
}

function smoothstep(x: number): number {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  return x * x * (3 - 2 * x);
}

const r3 = (x: number) => Math.round(x * 1000) / 1000;

function rainAt(t: number): number {
  return Math.round(12 + 72 * smoothstep((t - 6) / 60));
}

interface Indices { saturation: number; landslide: number; flood: number }

function hillviewAt(t: number): Indices {
  return {
    saturation: Math.min(0.82, 0.42 + 0.4 * (t / 72) ** 1.2),
    landslide: 0.18 + 0.6 * (t / 72) ** 1.1,
    flood: 0.05,
  };
}

function riversideAt(t: number): Indices {
  return {
    saturation: 0.38 + 0.25 * (t / 72),
    landslide: 0.02,
    flood: 0.08 + 0.34 * smoothstep((t - 30) / 40),
  };
}

const SCENARIO_EVENTS: Record<number, { name: string; description: string }> = {
  30: { name: 'excavation_depth', description: 'Excavation at Hillview Terrace reaches 4.5 m' },
  50: { name: 'culvert_check', description: 'D-7 culvert running at 70% capacity' },
};

function zoneRain24h(city: City, zoneId: string): number {
  return city.zones.find((z) => z.id === zoneId)?.state.rain_24h_mm ?? 0;
}

export function buildReplay(city: City): ReplayStep[] {
  const steps: ReplayStep[] = [];
  const prevBand: Record<string, Band> = {};
  for (const z of city.zones) prevBand[z.id] = z.state.band;
  const rain24: Record<string, number> = {
    [HILLVIEW_ZONE_ID]: zoneRain24h(city, HILLVIEW_ZONE_ID),
    [RIVERSIDE_ZONE_ID]: zoneRain24h(city, RIVERSIDE_ZONE_ID),
  };
  let incidentOpen = false;
  let riversideDetected = false;

  for (let tick = 1; tick <= REPLAY_TICKS; tick++) {
    const simTime = simTimeAt(tick);
    const events: Event[] = [];
    let n = 0;
    const base = () => ({ id: `evt_m_${String(tick)}_${String(n++)}`, ts: `${simTime}Z`, sim_time: simTime });
    const rain = rainAt(tick);
    const hv = hillviewAt(tick);
    const rs = riversideAt(tick);

    events.push({ ...base(), type: 'sim.tick', payload: { sim_time: simTime, tick, running: true, speed: 1 } });
    events.push({ ...base(), type: 'sensor.reading', payload: { sensor_id: RAIN_SENSOR_ID, kind: 'rain', zone_id: HILLVIEW_ZONE_ID, value: rain, unit: 'mm/h' } });
    events.push({ ...base(), type: 'sensor.reading', payload: { sensor_id: SOIL_SENSOR_ID, kind: 'soil', zone_id: HILLVIEW_ZONE_ID, value: Math.round(hv.saturation * 100), unit: '%' } });
    events.push({ ...base(), type: 'sensor.reading', payload: { sensor_id: CHANNEL_SENSOR_ID, kind: 'channel', zone_id: HILLVIEW_ZONE_ID, value: r3(0.6 + 1.4 * rs.flood), unit: 'm' } });

    const bandChanges: { zoneId: string; band: Band; prev: Band; hazard: Hazard; index: number }[] = [];
    for (const [zoneId, ix] of [[HILLVIEW_ZONE_ID, hv], [RIVERSIDE_ZONE_ID, rs]] as const) {
      rain24[zoneId] = (rain24[zoneId] ?? 0) + (rain * TICK_MINUTES) / 60;
      const lb = indexBand(city.bands, 'landslide', ix.landslide);
      const fb = indexBand(city.bands, 'flood', ix.flood);
      const hazard: Hazard = rank(lb) >= rank(fb) ? 'landslide' : 'flood';
      const band = hazard === 'landslide' ? lb : fb;
      const prev = prevBand[zoneId] ?? 'normal';
      const state: ZoneState = {
        saturation: r3(ix.saturation),
        rain_24h_mm: Math.round(rain24[zoneId] ?? 0),
        rain_intensity_mm_h: rain,
        landslide_index: r3(ix.landslide),
        flood_index: r3(ix.flood),
        band,
        updated_sim_time: simTime,
      };
      events.push({ ...base(), type: 'zone.state', payload: { ...state, zone_id: zoneId, ...(prev !== band ? { prev_band: prev } : {}) } });
      if (prev !== band) bandChanges.push({ zoneId, band, prev, hazard, index: r3(hazard === 'landslide' ? ix.landslide : ix.flood) });
      prevBand[zoneId] = band;
    }

    for (const c of bandChanges) {
      const threat = { incident_id: MOCK_INCIDENT_ID, zone_id: c.zoneId, hazard: c.hazard, band: c.band, prev_band: c.prev, index: c.index };
      if (c.zoneId === HILLVIEW_ZONE_ID && !incidentOpen && c.band !== 'normal') {
        incidentOpen = true;
        events.push({ ...base(), incident_id: MOCK_INCIDENT_ID, type: 'threat.detected', payload: threat });
        events.push({ ...base(), incident_id: MOCK_INCIDENT_ID, type: 'incident.opened', payload: openedIncident(simTime, c.band) });
      } else if (c.zoneId === HILLVIEW_ZONE_ID && rank(c.band) > rank(c.prev)) {
        events.push({ ...base(), incident_id: MOCK_INCIDENT_ID, type: 'threat.escalated', payload: threat });
      } else if (c.zoneId === RIVERSIDE_ZONE_ID && !riversideDetected && c.band !== 'normal') {
        // Riverside flood watch is reported as a detection only; the mock keeps one incident so the story stays
        // single-threaded (plan Task 5). It is scripted downstream of the Hillview incident in the primary scenario.
        riversideDetected = true;
        events.push({ ...base(), incident_id: MOCK_INCIDENT_ID, type: 'threat.detected', payload: threat });
      }
    }

    const scenario = SCENARIO_EVENTS[tick];
    if (scenario) events.push({ ...base(), type: 'scenario.event', payload: scenario });

    steps.push({ tick, events });
  }
  return steps;
}

function openedIncident(simTime: string, band: Band): EventOf<'incident.opened'>['payload'] {
  const incident: Incident = {
    id: MOCK_INCIDENT_ID,
    zone_id: HILLVIEW_ZONE_ID,
    hazard: 'landslide',
    band,
    status: 'open',
    opened_at: `${simTime}Z`,
    opened_sim_time: simTime,
    closed_at: null,
    runs: [],
    approvals: [],
    actions: [],
  };
  return incident;
}
