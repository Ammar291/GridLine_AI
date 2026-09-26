// Scripted primary-scenario events for mock mode (spec F1, section 8), in the backend's event shapes.
// Observations come from fixed formulas (scripted simulation, which CLAUDE.md permits). The threat detector's
// zone.state / threat / incident events are PENDING backend events, scripted the same way so the detector-driven
// panels can be exercised. It never emits agent, approval, action, verification or re-plan events: those would be
// fabricated AI output.
import type { Band, Bands, City, Event, EventOf, EventType, Hazard, Incident, Severity, ZoneState } from '@/api/types';

export interface ReplayStep { tick: number; events: Event[] }

export const REPLAY_SCENARIO = 'hillside_landslide';
export const REPLAY_SEED = 42;
export const REPLAY_START_SIM_TIME = '2026-07-14T06:00:00Z';
export const REPLAY_TICKS = 72;
export const TICK_MINUTES = 5;

export const HILLVIEW_ZONE_ID = 'Z-HV';
export const RIVERSIDE_ZONE_ID = 'Z-RS';
export const MOCK_INCIDENT_ID = 'inc_mock_1';
const PROJECT_ID = 'PR-HT2';
const DRAIN_GAUGE_ID = 'CL-D7';
const DETECTOR_SOURCE = 'mock:detector';

/** PENDING (threat detector): index band thresholds. The mock scripts its own until GET /api/detector/bands lands. */
export const MOCK_BANDS: Bands = {
  landslide: { watch: 0.35, warning: 0.55, critical: 0.75 },
  flood: { watch: 0.3, warning: 0.5, critical: 0.7 },
};

export function simTimeAt(tick: number): string {
  const start = Date.parse(REPLAY_START_SIM_TIME);
  return new Date(start + tick * TICK_MINUTES * 60_000).toISOString().replace('.000Z', 'Z');
}

const BAND_ORDER: readonly Band[] = ['normal', 'watch', 'warning', 'critical'];
const rank = (b: Band) => BAND_ORDER.indexOf(b);
const BAND_SEVERITY: Record<Band, Severity> = { normal: 'info', watch: 'moderate', warning: 'high', critical: 'critical' };

/** Band for one hazard index against the thresholds. */
export function indexBand(bands: Bands, hazard: Hazard, value: number): Band {
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

const r2 = (x: number) => Math.round(x * 100) / 100;
const r3 = (x: number) => Math.round(x * 1000) / 1000;
const rainAt = (t: number) => r2(12 + 72 * smoothstep((t - 6) / 60));
const rainSeverity = (mmH: number): Severity => (mmH >= 50 ? 'high' : mmH >= 30 ? 'moderate' : mmH >= 10 ? 'low' : 'info');
const soilSeverity = (sat: number): Severity => (sat >= 0.85 ? 'high' : sat >= 0.7 ? 'moderate' : sat >= 0.5 ? 'low' : 'info');

interface Indices { saturation: number; landslide: number; flood: number }
const hillviewAt = (t: number): Indices => ({
  saturation: Math.min(0.82, 0.42 + 0.4 * (t / 72) ** 1.2), landslide: 0.18 + 0.6 * (t / 72) ** 1.1, flood: 0.05,
});
const riversideAt = (t: number): Indices => ({
  saturation: 0.38 + 0.25 * (t / 72), landslide: 0.02, flood: 0.08 + 0.34 * smoothstep((t - 30) / 40),
});

interface Meta { source: string; location: string | null; severity: Severity; incidentId?: string }

export function buildReplay(city: City): ReplayStep[] {
  const steps: ReplayStep[] = [];
  const scenario = city.scenarios.find((s) => s.name === REPLAY_SCENARIO);
  const gauges = city.sensors.filter((s) => s.kind === 'rain_gauge');
  const probes = city.sensors.filter((s) => s.kind === 'soil_moisture');
  const prevBand: Record<string, Band> = { [HILLVIEW_ZONE_ID]: 'normal', [RIVERSIDE_ZONE_ID]: 'normal' };
  const rain24: Record<string, number> = {};
  let incidentOpen = false;
  let riversideDetected = false;

  for (let tick = 1; tick <= REPLAY_TICKS; tick++) {
    const simTime = simTimeAt(tick);
    const events: Event[] = [];
    let n = 0;
    const push = <T extends EventType>(type: T, payload: EventOf<T>['payload'], m: Meta) => {
      const event = {
        event_id: `evt-m-${String(tick).padStart(3, '0')}-${String(n++)}`, timestamp: simTime, sim_time: simTime,
        source: m.source, location: m.location, severity: m.severity, incident_id: m.incidentId ?? null, event_type: type, payload,
      };
      events.push(event as unknown as EventOf<T>); // event_type and payload are matched by the signature
    };
    const stageName = [...(scenario?.stages ?? [])].reverse().find((s) => s.start_tick <= tick)?.name ?? 'construction_and_rain';
    const stage = scenario?.stages.find((s) => s.start_tick === tick);
    if (stage) {
      push('scenario.stage', { scenario: REPLAY_SCENARIO, stage_index: stage.index, stage: stage.name, description: stage.description, tick },
        { source: `scenario:${REPLAY_SCENARIO}`, location: null, severity: 'info' });
    }
    if (tick % 12 === 0) {
      push('infrastructure.construction',
        { project_id: PROJECT_ID, status: 'active', activity: 'excavating', excavation_depth_m: r2(2.5 + 0.15 * (tick / 12)), planned_depth_m: 6 },
        { source: 'simulation:engine', location: HILLVIEW_ZONE_ID, severity: 'low' });
    }

    const rain = rainAt(tick);
    const hv = hillviewAt(tick);
    const rs = riversideAt(tick);
    for (const g of gauges) {
      const zone = g.zone_id ?? HILLVIEW_ZONE_ID;
      const mmH = zone === HILLVIEW_ZONE_ID || zone === 'Z-TH' ? rain : r2(rain * 0.6);
      rain24[g.id] = (rain24[g.id] ?? 0) + (mmH * TICK_MINUTES) / 60;
      push('weather.observation', {
        station_id: g.id, rainfall_intensity_mm_h: mmH, cumulative_rainfall_24h_mm: r2(rain24[g.id] ?? 0),
        temperature_c: null, wind_speed_kmh: null, wind_direction_deg: null,
      }, { source: `sensor:${g.id}`, location: g.zone_id, severity: rainSeverity(mmH) });
    }
    for (const p of probes) {
      const saturation = r3(p.zone_id === HILLVIEW_ZONE_ID ? hv.saturation : hv.saturation * 0.9);
      push('environment.soil', { probe_id: p.id, slope_id: p.target_id, soil_moisture_pct: r2(45 * saturation), saturation },
        { source: `sensor:${p.id}`, location: p.zone_id, severity: soilSeverity(saturation) });
    }
    const load = r3(0.3 + 1.2 * rs.flood);
    push('environment.drainage', {
      gauge_id: DRAIN_GAUGE_ID, channel_id: 'D-7', flow_m3s: r2(27 * load), capacity_m3s: 27, load_ratio: load, blocked_fraction: 0,
      overflow_m3s: r2(Math.max(0, 27 * load - 27)),
    }, { source: `sensor:${DRAIN_GAUGE_ID}`, location: HILLVIEW_ZONE_ID, severity: load >= 1 ? 'critical' : load >= 0.8 ? 'moderate' : 'info' });

    // ---- PENDING: the threat detector's view, scripted ----
    const changes: { zoneId: string; band: Band; prev: Band; hazard: Hazard; index: number }[] = [];
    for (const [zoneId, ix] of [[HILLVIEW_ZONE_ID, hv], [RIVERSIDE_ZONE_ID, rs]] as const) {
      const lb = indexBand(MOCK_BANDS, 'landslide', ix.landslide);
      const fb = indexBand(MOCK_BANDS, 'flood', ix.flood);
      const hazard: Hazard = rank(lb) >= rank(fb) ? 'landslide' : 'flood';
      const band = hazard === 'landslide' ? lb : fb;
      const prev = prevBand[zoneId] ?? 'normal';
      const zoneRain = zoneId === HILLVIEW_ZONE_ID ? rain : r2(rain * 0.6);
      const state: ZoneState = {
        saturation: r3(ix.saturation), rain_24h_mm: Math.round((zoneRain * tick * TICK_MINUTES) / 60), rain_intensity_mm_h: zoneRain,
        landslide_index: r3(ix.landslide), flood_index: r3(ix.flood), band, updated_sim_time: simTime,
      };
      push('zone.state', { ...state, zone_id: zoneId, prev_band: prev === band ? null : prev },
        { source: DETECTOR_SOURCE, location: zoneId, severity: BAND_SEVERITY[band] });
      if (prev !== band) changes.push({ zoneId, band, prev, hazard, index: r3(hazard === 'landslide' ? ix.landslide : ix.flood) });
      prevBand[zoneId] = band;
    }
    for (const c of changes) {
      const threat = { incident_id: MOCK_INCIDENT_ID, zone_id: c.zoneId, hazard: c.hazard, band: c.band, prev_band: c.prev, index: c.index };
      const meta = { source: DETECTOR_SOURCE, location: c.zoneId, severity: BAND_SEVERITY[c.band], incidentId: MOCK_INCIDENT_ID };
      if (c.zoneId === HILLVIEW_ZONE_ID && !incidentOpen && c.band !== 'normal') {
        incidentOpen = true;
        push('threat.detected', threat, meta);
        push('incident.opened', openedIncident(simTime, c.band), meta);
      } else if (c.zoneId === HILLVIEW_ZONE_ID && rank(c.band) > rank(c.prev)) {
        push('threat.escalated', threat, meta);
      } else if (c.zoneId === RIVERSIDE_ZONE_ID && !riversideDetected && c.band !== 'normal') {
        // Riverside's flood watch is reported as a detection only; the mock keeps one incident (plan Task 5).
        riversideDetected = true;
        push('threat.detected', threat, meta);
      }
    }

    push('sim.tick', { tick, sim_time: simTime, scenario: REPLAY_SCENARIO, stage: stageName, speed: 1, running: true },
      { source: 'simulation:engine', location: null, severity: 'info' });
    steps.push({ tick, events });
  }
  return steps;
}

function openedIncident(simTime: string, band: Band): Incident {
  return {
    id: MOCK_INCIDENT_ID, zone_id: HILLVIEW_ZONE_ID, hazard: 'landslide', band, status: 'open', opened_at: simTime,
    opened_sim_time: simTime, closed_at: null, runs: [], approvals: [], actions: [],
  };
}
