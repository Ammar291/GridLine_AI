import { beforeEach, describe, expect, it } from 'vitest';
import { ALL_LAYERS, useUiStore } from './uiStore';

describe('uiStore', () => {
  beforeEach(() => { useUiStore.getState().reset(); });
  it('starts with every layer on and toggles one off and on', () => {
    expect([...useUiStore.getState().activeLayers].sort()).toEqual([...ALL_LAYERS].sort());
    useUiStore.getState().toggleLayer('roads');
    expect(useUiStore.getState().activeLayers.has('roads')).toBe(false);
    useUiStore.getState().toggleLayer('roads');
    expect(useUiStore.getState().activeLayers.has('roads')).toBe(true);
  });
  it('selectEntity sets the entity and, for a zone, its open incident', () => {
    useUiStore.getState().selectEntity({ kind: 'zone', id: 'hillview' });
    expect(useUiStore.getState().selectedEntity).toEqual({ kind: 'zone', id: 'hillview' });
    expect(useUiStore.getState().selectedIncidentId).toBeNull();
    useUiStore.getState().selectEntity({ kind: 'zone', id: 'hillview' }, 'inc_1');
    expect(useUiStore.getState().selectedIncidentId).toBe('inc_1');
    useUiStore.getState().selectEntity({ kind: 'crew', id: 'c3' }, 'inc_9');
    expect(useUiStore.getState().selectedIncidentId).toBe('inc_1');
    useUiStore.getState().selectEntity(null);
    expect(useUiStore.getState().selectedEntity).toBeNull();
  });
  it('opens and closes the why and source drawers; sets filters', () => {
    useUiStore.getState().openWhy({ kind: 'action', actionId: 'act_1', incidentId: 'inc_1' });
    expect(useUiStore.getState().whyTarget).toEqual({ kind: 'action', actionId: 'act_1', incidentId: 'inc_1' });
    useUiStore.getState().closeWhy();
    expect(useUiStore.getState().whyTarget).toBeNull();
    useUiStore.getState().openSource('dmp-2024#s4.2');
    expect(useUiStore.getState().sourceCitationId).toBe('dmp-2024#s4.2');
    useUiStore.getState().closeSource();
    expect(useUiStore.getState().sourceCitationId).toBeNull();
    useUiStore.getState().setFeedFilter('approval');
    expect(useUiStore.getState().feedFilter).toBe('approval');
    useUiStore.getState().setTimelineZone('riverside');
    expect(useUiStore.getState().timelineZoneId).toBe('riverside');
    useUiStore.getState().selectIncident('inc_2');
    expect(useUiStore.getState().selectedIncidentId).toBe('inc_2');
  });
});
