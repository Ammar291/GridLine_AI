import { describe, expect, it } from 'vitest';
import { cityFixture, worldFixture } from '@/test/fixtures/city';
import { emptyAssets, liveAssets } from './assets';

describe('liveAssets', () => {
  it('merges each static city entity with its live world state', () => {
    const a = liveAssets(cityFixture, worldFixture, { 'RG-02': { value: 12, text: '12 mm/h', simTime: '2026-07-14T10:00:00Z' } });
    expect(a.channels.d7).toMatchObject({ name: 'D-7 Kalinadi drain', design_capacity_m3s: 12, capacity_m3s: 8.5, flow_m3s: 2 });
    expect(a.projects.ht_phase2).toMatchObject({ planned_depth_m: 6, status: 'active', excavation_depth_m: 3.5 });
    expect(a.hospitals.h1).toMatchObject({ beds_total: 320, beds_occupied: 200, er_status: 'normal' });
    expect(a.sensors['RG-02']?.reading?.text).toBe('12 mm/h');
    expect(a.sensors['RG-01']?.reading).toBeNull();
    expect(a.pumpUnits).toHaveLength(4);
  });

  it('entities the world does not hold keep static defaults, and no city means no assets', () => {
    const a = liveAssets(cityFixture, null, {});
    expect(a.roads.hill_road).toMatchObject({ status: 'open', reason: '' });
    expect(a.crews.c1).toMatchObject({ status: 'available', location_zone_id: 'old_town', task: '' });
    expect(a.channels.d7).toMatchObject({ capacity_m3s: 8.5, blocked_fraction: 0 });
    expect(liveAssets(null, worldFixture, {})).toEqual(emptyAssets());
  });
});
