import { describe, expect, it } from 'vitest';
import { describeEvent, eventGroup } from './describeEvent';
import { eventsFixture as ev } from '@/test/fixtures/events';
import { cityFixture } from '@/test/fixtures/city';
import type { Event } from '@/api/types';

const d = (e: Event) => describeEvent(e, cityFixture);

describe('describeEvent', () => {
  it('describes every event type in the contract in one non-empty line', () => {
    for (const e of Object.values(ev)) {
      const line = d(e);
      expect(line.length).toBeGreaterThan(3);
      expect(line.includes('\n')).toBe(false);
      expect(line.endsWith('.')).toBe(false);
    }
  });

  it('backend simulation and observation events', () => {
    expect(d(ev['sim.snapshot'])).toBe('Connected: city state received');
    expect(d(ev['sim.tick'])).toBe('Tick 13 at 10:31');
    expect(d(ev['sim.status'])).toBe('Simulation paused: hillside landslide, 2×, tick 13');
    expect(d(ev['scenario.stage'])).toBe('Stage 3: fixture: slope creep begins');
    expect(d(ev['weather.observation'])).toBe('Rainfall RG-02 (Hillview) 52.4 mm/h, 120 mm in 24 h');
    expect(d(ev['weather.forecast'])).toBe('Forecast: fixture: heavy rain warning (peak 40 mm/h)');
    expect(d(ev['environment.soil'])).toBe('Soil moisture SM-01 (Hillview) 74% saturated');
    expect(d(ev['environment.river'])).toBe('River level RV-01 (Kalinadi) 3.42 m, rising');
    expect(d(ev['environment.drainage'])).toBe('Drain d7: 10.2 of 8.5 m³/s (120%), overflowing 1.7 m³/s');
    expect(d(ev['environment.slope'])).toBe('Slope sl_hv Hillview Terrace slope moving 2.4 mm/h, 34 mm total');
    expect(d(ev['environment.water_accumulation'])).toBe('Standing water in Riverside 12.5 cm, rising');
  });

  it('backend infrastructure and emergency events use the city names', () => {
    expect(d(ev['infrastructure.road'])).toBe('Hill Road blocked: fixture: debris');
    expect(d(ev['infrastructure.bridge'])).toBe('Kalinadi Bridge closed: fixture: river at danger level');
    expect(d(ev['infrastructure.drainage_obstruction'])).toBe('Drain d7 70% blocked: fixture: landslide debris');
    expect(d(ev['infrastructure.construction'])).toBe('Hillview Terrace Phase 2 halted, 3.6 of 6 m dug');
    expect(d(ev['infrastructure.failure'])).toBe('Landslide at sl_hv: fixture: slope failed above D-7');
    expect(d(ev['emergency.rescue_team'])).toBe('c1 Rescue Team 01 on site in Riverside: fixture: evacuation support');
    expect(d(ev['emergency.ambulance'])).toBe('Ambulance a1 dispatched in Hillview (0 of 2 available)');
    expect(d(ev['emergency.hospital'])).toBe('Riverside Clinic: 52 of 60 beds occupied, ER busy');
    expect(d(ev['emergency.shelter'])).toBe('Market Ward School open: 120 of 400 places used');
  });

  it('a wind station reports wind and temperature', () => {
    const wind: Event = {
      ...ev['weather.observation'], location: 'old_town',
      payload: { station_id: 'WS-01', rainfall_intensity_mm_h: null, cumulative_rainfall_24h_mm: null, temperature_c: 22.1, wind_speed_kmh: 28, wind_direction_deg: 240 },
    };
    expect(d(wind)).toBe('Weather WS-01 (Old Town) wind 28 km/h, 22.1 °C');
  });

  it('PENDING events keep their lines', () => {
    expect(d(ev['zone.state'])).toBe('Hillview: landslide index 0.61, Watch → Warning');
    expect(d(ev['action.executed'])).toBe('Dispatch crew executed: Rescue Team 03 Available → Dispatched');
    expect(d(ev['incident.opened'])).toBe('Incident opened: landslide risk in Hillview (Warning)');
    expect(d(ev['approval.requested'])).toBe('Approval requested for 3 actions');
    expect(d(ev['threat.detected'])).toBe('Threat detected: landslide risk in Hillview (Watch)');
    expect(d(ev['threat.escalated'])).toBe('Threat escalated: landslide in Hillview, Watch → Warning');
    expect(d(ev['incident.closed'])).toBe('Incident closed: landslide in Hillview');
    expect(d(ev['agent.run.started'])).toBe('Agent run started (band_change)');
    expect(d(ev['agent.run.finished'])).toBe('Agent run finished');
    expect(d(ev['agent.node.started'])).toBe('Assess threat started');
    expect(d(ev['agent.node.finished'])).toBe('Assess threat finished');
    expect(d(ev['approval.decided'])).toBe('Approval partial by operator');
    expect(d(ev['action.verified'])).toBe('Action act_2 verified');
    expect(d(ev['replan.triggered'])).toBe('Re-planning: fixture: crew route blocked');
    expect(d(ev['alert.issued'])).toBe('Alert (warning) for Riverside: fixture: alert message');
    expect(d({ ...ev['sim.tick'], event_type: 'future.thing' } as unknown as Event)).toBe('future.thing');
  });

  it('flags ungrounded steps, synthetic decisions and re-plan runs; falls back to ids for unknown zones', () => {
    const finished = ev['agent.node.finished'];
    expect(d({ ...finished, payload: { ...finished.payload, status: 'ungrounded' } })).toBe('Assess threat finished (ungrounded)');
    const decided = ev['approval.decided'];
    expect(d({ ...decided, payload: { ...decided.payload, status: 'approved', decided_by: null, synthetic: true } })).toBe('Approval approved (auto)');
    const started = ev['agent.run.started'];
    expect(d({ ...started, payload: { ...started.payload, trigger: 'replan', replan_reason: 'fixture: blocked' } })).toBe('Agent run started (replan), re-plan: fixture: blocked');
    expect(describeEvent({ ...ev['weather.observation'], location: 'ghost' }, null)).toBe('Rainfall RG-02 (ghost) 52.4 mm/h, 120 mm in 24 h');
  });

  it('groups event types', () => {
    expect(eventGroup('sim.tick')).toBe('simulation');
    expect(eventGroup('sim.snapshot')).toBe('simulation');
    expect(eventGroup('scenario.stage')).toBe('simulation');
    expect(eventGroup('weather.observation')).toBe('reading');
    expect(eventGroup('environment.drainage')).toBe('reading');
    expect(eventGroup('weather.forecast')).toBe('city');
    expect(eventGroup('infrastructure.road')).toBe('city');
    expect(eventGroup('emergency.hospital')).toBe('city');
    expect(eventGroup('zone.state')).toBe('threat');
    expect(eventGroup('threat.detected')).toBe('threat');
    expect(eventGroup('incident.opened')).toBe('threat');
    expect(eventGroup('replan.triggered')).toBe('agent');
    expect(eventGroup('agent.node.finished')).toBe('agent');
    expect(eventGroup('approval.decided')).toBe('approval');
    expect(eventGroup('action.verified')).toBe('action');
    expect(eventGroup('alert.issued')).toBe('alert');
    expect(eventGroup('something.else')).toBe('simulation');
  });
});
