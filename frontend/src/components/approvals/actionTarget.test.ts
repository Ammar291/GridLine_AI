import { describe, expect, it } from 'vitest';
import { applyEvent } from '@/live/applyEvent';
import { initialLiveState } from '@/live/types';
import { cityFixture } from '@/test/fixtures/city';
import { snapshotEventFixture } from '@/test/fixtures/events';
import { actionTargetName } from './actionTarget';

const { assets } = applyEvent(initialLiveState('mock'), snapshotEventFixture);
const target = (tool: string, input: Record<string, unknown>) => actionTargetName(tool, input, assets, cityFixture);

describe('actionTargetName', () => {
  it('names the project, road, shelter and inspected asset', () => {
    expect(target('halt_construction', { project_id: 'ht_phase2' })).toBe('Hillview Terrace Phase 2');
    expect(target('close_road', { road_id: 'b04' })).toBe('Kalinadi Bridge B-04');
    expect(target('open_shelter', { shelter_id: 's1' })).toBe('Market Ward School');
    expect(target('schedule_inspection', { asset_id: 'd7', priority: 'high' })).toBe('D-7 Kalinadi drain');
  });

  it('names the crew and where it is sent', () => {
    expect(target('dispatch_crew', { crew_id: 'c3', zone_id: 'hillview' })).toBe('Rescue Team 03 to Hillview');
  });

  it('adds the number of pump units', () => {
    expect(target('deploy_pumps', { channel_id: 'd7', units: 2 })).toBe('D-7 Kalinadi drain, 2 units');
    expect(target('deploy_pumps', { channel_id: 'd7', units: 1 })).toBe('D-7 Kalinadi drain, 1 unit');
  });

  it('names the zone when a zone is the only target', () => {
    expect(target('issue_alert', { zone_id: 'riverside', level: 'warning' })).toBe('Riverside');
  });

  it('keeps unknown ids as they are', () => {
    expect(target('close_road', { road_id: 'r_ghost' })).toBe('r_ghost');
  });

  it('falls back to the first string value for unknown tools, else empty', () => {
    expect(target('do_something_new', { foo: 'bar' })).toBe('bar');
    expect(target('do_something_new', { n: 3 })).toBe('');
  });
});
