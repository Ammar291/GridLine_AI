// Typed test fixtures for the backend's city (GET /api/city) and live world (sim.snapshot). Synthetic, deliberately
// small; geometry is placeholder (the mock city JSON, written by the backend, owns the real geometry).
import type { City, WorldSnapshot, Zone, ZoneState } from '@/api/types';

const P = 'M0 0L10 0L10 10Z';
export const FIXTURE_SIM_TIME = '2026-07-14T10:00:00Z';

/** PENDING (threat detector): a zone.state payload body for detector-driven tests. */
export const normalZoneState: ZoneState = {
  saturation: 0.4,
  rain_24h_mm: 20,
  rain_intensity_mm_h: 8,
  landslide_index: 0.15,
  flood_index: 0.1,
  band: 'normal',
  updated_sim_time: FIXTURE_SIM_TIME,
};

function zone(id: string, name: string, slope_deg: number, population: number, drains: string | null): Zone {
  return {
    id, name, kind: 'fixture', slope_deg, soil_type: 'fixture: soil', population, drains_to_channel_id: drains, svg_path: P,
    label_xy: { x: 5, y: 5 },
  };
}

export const cityFixture: City = {
  name: 'Nandipur',
  view_box: { x: 0, y: 0, width: 1000, height: 700 },
  zones: [
    zone('hillview', 'Hillview', 32, 4200, 'd7'),
    zone('riverside', 'Riverside', 4, 18500, 'd7'),
    zone('old_town', 'Old Town', 6, 26000, 'd3'),
    zone('market_ward', 'Market Ward', 5, 22400, null),
    zone('station_road', 'Station Road', 3, 15800, null),
    zone('lakeside', 'Lakeside', 2, 9600, 'd11'),
  ],
  roads: [
    { id: 'hill_road', name: 'Hill Road', kind: 'fixture', zone_ids: ['riverside', 'hillview'], is_evacuation_route: false, is_only_access: true, svg_path: P },
    { id: 'riverside_bypass', name: 'Riverside Bypass', kind: 'fixture', zone_ids: ['riverside'], is_evacuation_route: true, is_only_access: false, svg_path: P },
    { id: 'b04', name: 'Kalinadi Bridge B-04', kind: 'fixture', zone_ids: ['old_town', 'riverside'], is_evacuation_route: false, is_only_access: false, svg_path: P },
  ],
  bridges: [
    { id: 'br_1', name: 'Kalinadi Bridge', road_id: 'b04', zone_id: 'old_town', crosses_id: 'kalinadi', xy: { x: 560, y: 390 } },
  ],
  channels: [
    { id: 'd7', name: 'D-7 Kalinadi drain', zone_id: 'hillview', downstream_zone_id: 'riverside', design_capacity_m3s: 12, current_capacity_m3s: 8.5, svg_path: P },
    { id: 'd3', name: 'D-3 Old Town drain', zone_id: 'old_town', downstream_zone_id: 'riverside', design_capacity_m3s: 9, current_capacity_m3s: 9, svg_path: P },
    { id: 'd11', name: 'D-11 Lakeside drain', zone_id: 'lakeside', downstream_zone_id: 'lakeside', design_capacity_m3s: 6, current_capacity_m3s: 6, svg_path: P },
  ],
  slopes: [{ id: 'sl_hv', name: 'Hillview Terrace slope', zone_id: 'hillview', xy: { x: 780, y: 200 } }],
  projects: [
    {
      id: 'ht_phase2', name: 'Hillview Terrace Phase 2', zone_id: 'hillview', slope_id: 'sl_hv', planned_depth_m: 6,
      permit_number: 'HT-2026-014', permit_doc_id: 'permit-ht-2026-014', xy: { x: 780, y: 190 },
    },
  ],
  sensors: [
    { id: 'RG-01', name: 'fixture: rain gauge 1', kind: 'rain_gauge', zone_id: 'hillview', target_id: 'hillview', xy: { x: 850, y: 120 } },
    { id: 'RG-02', name: 'fixture: rain gauge 2', kind: 'rain_gauge', zone_id: 'hillview', target_id: 'hillview', xy: { x: 740, y: 250 } },
    { id: 'RG-03', name: 'fixture: rain gauge 3', kind: 'rain_gauge', zone_id: 'old_town', target_id: 'old_town', xy: { x: 400, y: 250 } },
    { id: 'SM-01', name: 'fixture: soil probe 1', kind: 'soil_moisture', zone_id: 'hillview', target_id: 'sl_hv', xy: { x: 800, y: 230 } },
    { id: 'SM-02', name: 'fixture: soil probe 2', kind: 'soil_moisture', zone_id: 'hillview', target_id: 'sl_hv', xy: { x: 720, y: 180 } },
    { id: 'CL-D7', name: 'fixture: channel gauge', kind: 'channel_level', zone_id: 'riverside', target_id: 'd7', xy: { x: 705, y: 335 } },
    { id: 'RV-01', name: 'fixture: river gauge', kind: 'river_level', zone_id: 'old_town', target_id: 'kalinadi', xy: { x: 475, y: 445 } },
  ],
  crews: [
    { id: 'c1', name: 'Rescue Team 01', kind: 'rescue', base_zone_id: 'old_town', xy: { x: 400, y: 380 } },
    { id: 'c2', name: 'Rescue Team 02', kind: 'rescue', base_zone_id: 'station_road', xy: { x: 600, y: 600 } },
    { id: 'c3', name: 'Rescue Team 03', kind: 'rescue', base_zone_id: 'market_ward', xy: { x: 150, y: 250 } },
  ],
  shelters: [
    { id: 's1', name: 'Market Ward School', zone_id: 'market_ward', capacity: 400, xy: { x: 200, y: 330 } },
    { id: 's2', name: 'Station Road Hall', zone_id: 'station_road', capacity: 600, xy: { x: 520, y: 600 } },
  ],
  hospitals: [
    { id: 'h1', name: 'Nandipur General', zone_id: 'old_town', beds_total: 320, xy: { x: 470, y: 320 } },
    { id: 'h2', name: 'Riverside Clinic', zone_id: 'riverside', beds_total: 60, xy: { x: 800, y: 400 } },
  ],
  pump_depot: {
    zone_id: 'station_road',
    xy: { x: 700, y: 600 },
    units: ['p1', 'p2', 'p3', 'p4'].map((id) => ({ id, name: `fixture: pump ${id}`, status: 'available', capacity_m3s: 0.6 })),
  },
  map_features: [
    { id: 'kalinadi', kind: 'river', svg_path: P, label: 'Kalinadi' },
    { id: 'nandi_lake', kind: 'lake', svg_path: P, label: 'Nandi Lake' },
    { id: 'contour_1', kind: 'hill_contour', svg_path: P, label: '300 m' },
  ],
  scenarios: [
    {
      name: 'hillside_landslide', title: 'Hillside landslide', description: 'fixture: scenario', duration_ticks: 288,
      stages: [{ index: 0, name: 'construction_and_rain', description: 'fixture: stage one', start_tick: 0 }],
    },
    { name: 'flash_flood', title: 'Flash flood', description: 'fixture: scenario', duration_ticks: 240, stages: [] },
  ],
  injections: [
    {
      id: 'crew_route_blocked', label: 'Crew route blocked', description: 'fixture: blocks Hill Road',
      request: { event_type: 'infrastructure.road', location: null, payload: { road_id: 'hill_road', status: 'blocked', reason: 'fixture' }, source: 'operator:api', severity: null },
    },
    {
      id: 'culvert_blocked', label: 'Culvert blocked', description: 'fixture: blocks D-7',
      request: { event_type: 'infrastructure.drainage_obstruction', location: null, payload: { channel_id: 'd7', blocked_fraction: 0.6, cause: 'fixture' }, source: 'operator:api', severity: null },
    },
  ],
  triggers: [
    { id: 'heavy_rain', label: 'Heavy Rain', description: 'fixture: rain over the city' },
    { id: 'landslide', label: 'Landslide', description: 'fixture: cut slope in the rain' },
    { id: 'drainage_block', label: 'Drainage Block', description: 'fixture: debris in D-7' },
    { id: 'flash_flood', label: 'Flash Flood', description: 'fixture: cloudburst' },
    { id: 'industrial_fire', label: 'Industrial Fire', description: 'fixture: warehouse fire' },
    { id: 'cascading_disaster', label: 'Cascading Disaster', description: 'fixture: landslide, blockage, flood' },
  ],
};

const conditions = { saturation: 0.4, rainfall_intensity_mm_h: 8, rain_24h_mm: 20, water_depth_cm: 0, water_trend: 'steady' as const };

export const worldFixture: WorldSnapshot = {
  tick: 12,
  sim_time: FIXTURE_SIM_TIME,
  stage_index: 0,
  weather: { temperature_c: 24, wind_speed_kmh: 10, wind_direction_deg: 240 },
  forecast: null,
  zones: Object.fromEntries(cityFixture.zones.map((z) => [z.id, { ...conditions }])),
  slopes: { sl_hv: { saturation: 0.5, movement_rate_mm_h: 0, cumulative_movement_mm: 0 } },
  channels: {
    d7: { blocked_fraction: 0, capacity_m3s: 8.5, extra_capacity_m3s: 0, gate_closed: false, flow_m3s: 2, overflow_m3s: 0 },
    d3: { blocked_fraction: 0, capacity_m3s: 9, extra_capacity_m3s: 0, gate_closed: false, flow_m3s: 1, overflow_m3s: 0 },
    d11: { blocked_fraction: 0, capacity_m3s: 6, extra_capacity_m3s: 0, gate_closed: false, flow_m3s: 1, overflow_m3s: 0 },
  },
  rivers: { kalinadi: { level_m: 1.6, inflow_m3s: 85, trend: 'steady' } },
  roads: { hill_road: { status: 'open', reason: '' }, riverside_bypass: { status: 'open', reason: '' }, b04: { status: 'open', reason: '' } },
  bridges: { br_1: { status: 'open', reason: '' } },
  projects: { ht_phase2: { status: 'active', activity: 'excavating', excavation_depth_m: 3.5 } },
  crews: {
    c1: { status: 'available', location_zone_id: 'old_town', task: '' },
    c2: { status: 'available', location_zone_id: 'station_road', task: '' },
    c3: { status: 'available', location_zone_id: 'market_ward', task: '' },
  },
  ambulances: { a1: { status: 'available', location_zone_id: 'old_town' }, a2: { status: 'dispatched', location_zone_id: 'riverside' } },
  hospitals: { h1: { beds_occupied: 200, er_status: 'normal' }, h2: { beds_occupied: 30, er_status: 'normal' } },
  shelters: { s1: { status: 'closed', occupancy: 0 }, s2: { status: 'closed', occupancy: 0 } },
  fires: {},
};
