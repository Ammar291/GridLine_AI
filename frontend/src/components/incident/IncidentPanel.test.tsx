import { fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { Event } from '@/api/types';
import { useUiStore } from '@/ui/uiStore';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';
import { incidentFixture } from '@/test/fixtures/incident';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';
import { IncidentPanel } from './IncidentPanel';

/** The snapshot, then one PENDING incident.opened per incident. */
function snapshotWith(incidents: typeof incidentFixture[]): Event[] {
  return [
    snapshotEventFixture,
    ...incidents.map((i): Event => ({ ...eventsFixture['incident.opened'], event_id: `evt_open_${i.id}`, payload: i })),
  ];
}

describe('IncidentPanel', () => {
  beforeEach(() => { seedLive(); });

  it('shows the selected incident threat card and reasoning', () => {
    renderWithProviders(<IncidentPanel />);
    const panel = screen.getByRole('region', { name: 'Incident' });
    expect(within(panel).getByRole('heading', { name: 'Landslide risk' })).toBeInTheDocument();
    expect(within(panel).getByRole('list', { name: 'Agent nodes' })).toBeInTheDocument();
    expect(within(panel).getByRole('heading', { name: /Incident/ })).toHaveTextContent('1');
  });

  it('shows detector fields and awaits the agent when the incident has no run (mock mode)', () => {
    seedLive(snapshotWith([{ ...incidentFixture, runs: [] }]), { snapshot: false });
    renderWithProviders(<IncidentPanel />);
    expect(screen.getAllByText('Awaiting assessment')).not.toHaveLength(0);
    expect(screen.getByText('No agent run yet for this incident. Reasoning appears here as each node finishes.')).toBeInTheDocument();
  });

  it('shows a loading state before the first snapshot', () => {
    seedLive([], { snapshot: false });
    renderWithProviders(<IncidentPanel />);
    expect(screen.getByLabelText('Waiting for city state')).toHaveAttribute('aria-busy', 'true');
  });

  it('shows the empty state when no incident is open', () => {
    seedLive(snapshotWith([]), { snapshot: false });
    renderWithProviders(<IncidentPanel />);
    expect(screen.getByRole('note')).toHaveTextContent('No open incidents. Threats appear here when the detector opens an incident.');
  });

  it('offers an incident switcher when more than one incident is open', () => {
    const flood = { ...incidentFixture, id: 'inc_2', zone_id: 'riverside', hazard: 'flood' as const, band: 'watch' as const, runs: [] };
    seedLive(snapshotWith([incidentFixture, flood]), { snapshot: false });
    renderWithProviders(<IncidentPanel />);
    const select = screen.getByRole('combobox', { name: 'Incident' });
    expect(select).toHaveValue('inc_1');
    fireEvent.change(select, { target: { value: 'inc_2' } });
    expect(useUiStore.getState().selectedIncidentId).toBe('inc_2');
    expect(screen.getByRole('heading', { name: 'Flood risk' })).toBeInTheDocument();
  });

  it('mounts the source drawer', () => {
    seedLive([eventsFixture['zone.state']]);
    useUiStore.getState().openSource('state:zone.hillview');
    renderWithProviders(<IncidentPanel />);
    expect(screen.getByRole('dialog', { name: 'Source' })).toBeInTheDocument();
  });
});
