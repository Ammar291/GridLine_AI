import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Event } from '@/api/types';
import { useLiveStore } from '@/live/liveStore';
import { useUiStore } from '@/ui/uiStore';
import { failedActionFixture } from '@/test/fixtures/action';
import { cityFixture } from '@/test/fixtures/city';
import { eventsFixture } from '@/test/fixtures/events';
import { fakeClient } from '@/test/fakeClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';
import { CityMap } from './CityMap';

const renderMap = (client = fakeClient()) => renderWithProviders(<CityMap />, client);
const findMap = () => screen.findByRole('img', { name: 'Map of Nandipur' });

function zoneStateEvent(zoneId: string, band: 'warning' | 'critical'): Event {
  const e = eventsFixture['zone.state'];
  return { ...e, id: `evt_zs_${zoneId}_${band}`, payload: { ...e.payload, zone_id: zoneId, band } };
}

describe('CityMap', () => {
  beforeEach(() => { seedLive(); });

  it('renders one element per zone, road and channel with data attributes', async () => {
    renderMap();
    const svg = await findMap();
    expect(svg.querySelectorAll('[data-layer="zones"] [data-zone-id]')).toHaveLength(6);
    expect(svg.querySelectorAll('[data-layer="roads"] [data-road-id]')).toHaveLength(cityFixture.roads.length);
    expect(svg.querySelectorAll('[data-layer="drainage"] [data-channel-id]')).toHaveLength(3);
  });

  it('zone fill follows band and click selects the zone and its incident', async () => {
    useLiveStore.getState().dispatch(eventsFixture['zone.state']); // hillview → warning
    renderMap();
    const hill = await screen.findByTestId('zone-hillview');
    expect(hill).toHaveAttribute('data-band', 'warning');
    expect(hill).toHaveAccessibleName('Hillview, Warning');
    fireEvent.click(hill);
    expect(useUiStore.getState().selectedEntity).toEqual({ kind: 'zone', id: 'hillview' });
    expect(useUiStore.getState().selectedIncidentId).toBe('inc_1');
  });

  it('zones are keyboard selectable', async () => {
    renderMap();
    const river = await screen.findByTestId('zone-riverside');
    fireEvent.keyDown(river, { key: 'Enter' });
    expect(useUiStore.getState().selectedEntity).toEqual({ kind: 'zone', id: 'riverside' });
    expect(screen.getByRole('dialog', { name: 'Riverside' })).toHaveTextContent('18,500');
  });

  it('layer toggle hides the group', async () => {
    renderMap();
    await findMap();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Roads' }));
    expect(document.querySelector('[data-layer="roads"]')).toBeNull();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Roads' }));
    expect(document.querySelector('[data-layer="roads"]')).not.toBeNull();
  });

  it('wheel zooms the viewBox and the controls zoom and fit', async () => {
    renderMap();
    const svg = await findMap();
    const before = svg.getAttribute('viewBox');
    fireEvent.wheel(svg, { deltaY: -100, clientX: 0, clientY: 0 });
    expect(svg.getAttribute('viewBox')).not.toBe(before);
    fireEvent.click(screen.getByRole('button', { name: 'Fit' }));
    expect(svg.getAttribute('viewBox')).toBe(before);
    fireEvent.click(screen.getByRole('button', { name: 'Zoom in' }));
    expect(svg.getAttribute('viewBox')).not.toBe(before);
    fireEvent.click(screen.getByRole('button', { name: 'Zoom out' }));
    expect(svg.getAttribute('viewBox')).toBe(before);
  });

  it('ignores zone.state for zones not in the city', async () => {
    const ghost = zoneStateEvent('ghost', 'critical');
    expect(() => { useLiveStore.getState().dispatch(ghost); }).not.toThrow();
    renderMap();
    const svg = await findMap();
    expect(svg.querySelectorAll('[data-zone-id="ghost"]')).toHaveLength(0);
    expect(svg.querySelectorAll('[data-threat-zone-id="ghost"]')).toHaveLength(0);
    expect(svg.querySelectorAll('[data-layer="zones"] [data-zone-id]')).toHaveLength(6);
  });

  it('shows a popover with entity fields when a crew is selected, and closes it', async () => {
    renderMap();
    fireEvent.click(await screen.findByTestId('crew-c3'));
    const dialog = screen.getByRole('dialog', { name: 'Rescue Team 03' });
    expect(dialog).toHaveTextContent('Available');
    expect(dialog).toHaveTextContent('Market Ward');
    fireEvent.click(screen.getByRole('button', { name: 'Close details' }));
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(useUiStore.getState().selectedEntity).toBeNull();
  });

  it('applies live asset state: a closed road is drawn closed', async () => {
    useLiveStore.getState().dispatch({ ...eventsFixture['action.executed'], id: 'evt_close_b04', payload: failedActionFixture });
    renderMap();
    const svg = await findMap();
    expect(svg.querySelector('[data-road-id="b04"]')).toHaveAttribute('data-status', 'closed');
    expect(svg.querySelector('[data-road-id="hill_road"]')).toHaveAttribute('data-status', 'open');
  });

  it('draws the threat overlay: critical pulse, evacuation ring and cascade arrow', async () => {
    useLiveStore.getState().dispatch(zoneStateEvent('hillview', 'critical'));
    const alert = eventsFixture['alert.issued'];
    useLiveStore.getState().dispatch({ ...alert, payload: { ...alert.payload, level: 'evacuate' } });
    renderMap();
    const svg = await findMap();
    const threats = svg.querySelector('[data-layer="threats"]');
    expect(threats?.querySelector('[data-threat="critical"][data-threat-zone-id="hillview"]')).not.toBeNull();
    expect(threats?.querySelector('[data-threat="evacuate"][data-threat-zone-id="riverside"]')).not.toBeNull();
    // incidentFixture's cascade step names riverside as affected by the hillview incident.
    expect(threats?.querySelector('[data-cascade="hillview>riverside"]')).not.toBeNull();
  });

  it('shows a loading state while the city loads and no snapshot has arrived', () => {
    seedLive([], { snapshot: false });
    renderMap(fakeClient({ city: () => new Promise(() => undefined) }));
    expect(screen.getByLabelText('Loading city map')).toHaveAttribute('aria-busy', 'true');
  });

  it('shows an error with retry when the city fails to load', async () => {
    seedLive([], { snapshot: false });
    const city = vi.fn(() => Promise.reject(new Error('boom')));
    renderMap(fakeClient({ city }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('City map could not be loaded.');
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => { expect(city).toHaveBeenCalledTimes(2); });
  });

  it('shows an empty state for a city with no zones', async () => {
    seedLive([], { snapshot: false });
    renderMap(fakeClient({ city: () => Promise.resolve({ ...cityFixture, zones: [] }) }));
    expect(await screen.findByRole('note')).toHaveTextContent('The city model has no zones yet.');
  });
});
