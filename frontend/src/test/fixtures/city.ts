// Typed test fixture. Synthetic, deliberately small; geometry is placeholder (the mock city owns real geometry).
import type { City, Zone, ZoneState } from '@/api/types';

const P = 'M0 0L10 0L10 10Z';

export const normalZoneState: ZoneState = {
  saturation: 0.4,
  rain_24h_mm: 20,
  rain_intensity_mm_h: 8,
  landslide_index: 0.15,
  flood_index: 0.1,
  band: 'normal',
  updated_sim_time: '2026-07-14T10:00:00',
};

function zone(id: string, name: string, slope_deg: number, population: number, drains: string | null): Zone {
  return {
    id,
    name,
    slope_deg,
    soil_type: 'fixture: soil',
    population,
    drains_to_channel_id: drains,
    svg_path: P,
    label_xy: { x: 5, y: 5 },
    state: { ...normalZoneState },
  };
}

export const cityFixture: City = {
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
    { id: 'hill_road', name: 'Hill Road', zone_ids: ['riverside', 'hillview'], status: 'open', is_evacuation_route: false, is_bridge: false, svg_path: P },
    { id: 'riverside_bypass', name: 'Riverside Bypass', zone_ids: ['riverside'], status: 'open', is_evacuation_route: true, is_bridge: false, svg_path: P },
    { id: 'b04', name: 'Kalinadi Bridge B-04', zone_ids: ['old_town', 'riverside'], status: 'open', is_evacuation_route: false, is_bridge: true, svg_path: P },
  ],
  channels: [
    { id: 'd7', name: 'D-7 Kalinadi drain', design_capacity_m3s: 12, current_capacity_m3s: 8.5, blocked_fraction: 0, downstream_zone_id: 'riverside', svg_path: P },
    { id: 'd3', name: 'D-3 Old Town drain', design_capacity_m3s: 9, current_capacity_m3s: 9, blocked_fraction: 0, downstream_zone_id: 'riverside', svg_path: P },
    { id: 'd11', name: 'D-11 Lakeside drain', design_capacity_m3s: 6, current_capacity_m3s: 6, blocked_fraction: 0, downstream_zone_id: 'lakeside', svg_path: P },
  ],
  projects: [
    { id: 'ht_phase2', name: 'Hillview Terrace Phase 2', zone_id: 'hillview', status: 'active', excavation_depth_m: 3.5, planned_depth_m: 6, permit_doc_id: 'permit-ht-2026-014', xy: { x: 780, y: 190 } },
  ],
  sensors: [
    { id: 'RG-01', kind: 'rain', zone_id: 'hillview', unit: 'mm/h', xy: { x: 850, y: 120 } },
    { id: 'RG-02', kind: 'rain', zone_id: 'hillview', unit: 'mm/h', xy: { x: 740, y: 250 } },
    { id: 'RG-03', kind: 'rain', zone_id: 'old_town', unit: 'mm/h', xy: { x: 400, y: 250 } },
    { id: 'RG-04', kind: 'rain', zone_id: 'lakeside', unit: 'mm/h', xy: { x: 120, y: 480 } },
    { id: 'SM-01', kind: 'soil', zone_id: 'hillview', unit: '%', xy: { x: 800, y: 230 } },
    { id: 'SM-02', kind: 'soil', zone_id: 'hillview', unit: '%', xy: { x: 720, y: 180 } },
    { id: 'SM-03', kind: 'soil', zone_id: 'riverside', unit: '%', xy: { x: 760, y: 420 } },
    { id: 'CL-D7', kind: 'channel', zone_id: 'riverside', unit: 'm', xy: { x: 705, y: 335 } },
    { id: 'CL-D3', kind: 'channel', zone_id: 'old_town', unit: 'm', xy: { x: 475, y: 445 } },
  ],
  crews: [
    { id: 'c1', name: 'Rescue Team 01', status: 'available', location_zone_id: 'old_town', xy: { x: 400, y: 380 } },
    { id: 'c2', name: 'Rescue Team 02', status: 'available', location_zone_id: 'station_road', xy: { x: 600, y: 600 } },
    { id: 'c3', name: 'Rescue Team 03', status: 'available', location_zone_id: 'market_ward', xy: { x: 150, y: 250 } },
  ],
  shelters: [
    { id: 's1', name: 'Market Ward School', status: 'closed', capacity: 400, occupancy: 0, zone_id: 'market_ward', xy: { x: 200, y: 330 } },
    { id: 's2', name: 'Station Road Hall', status: 'closed', capacity: 600, occupancy: 0, zone_id: 'station_road', xy: { x: 520, y: 600 } },
  ],
  pump_depot: {
    zone_id: 'station_road',
    xy: { x: 700, y: 600 },
    units: [
      { id: 'p1', status: 'at_depot' },
      { id: 'p2', status: 'at_depot' },
      { id: 'p3', status: 'at_depot' },
      { id: 'p4', status: 'at_depot' },
    ],
  },
  hospitals: [
    { id: 'h1', name: 'Nandipur General', zone_id: 'old_town', beds: 320, xy: { x: 470, y: 320 } },
    { id: 'h2', name: 'Riverside Clinic', zone_id: 'riverside', beds: 60, xy: { x: 800, y: 400 } },
  ],
  map_features: [
    { id: 'kalinadi', kind: 'river', svg_path: P, label: 'Kalinadi' },
    { id: 'nandi_lake', kind: 'lake', svg_path: P, label: 'Nandi Lake' },
    { id: 'contour_1', kind: 'hill_contour', svg_path: P },
    { id: 'contour_2', kind: 'hill_contour', svg_path: P },
    { id: 'contour_3', kind: 'hill_contour', svg_path: P },
  ],
  bands: {
    landslide: { watch: 0.35, warning: 0.55, critical: 0.75 },
    flood: { watch: 0.3, warning: 0.5, critical: 0.7 },
  },
  scenarios: [
    {
      id: 'hillside_landslide',
      name: 'Hillside landslide',
      injections: [
        { id: 'crew_route_blocked', label: 'Crew route blocked' },
        { id: 'culvert_blocked', label: 'Culvert blocked' },
      ],
    },
    { id: 'flash_flood', name: 'Flash flood', injections: [] },
  ],
};
