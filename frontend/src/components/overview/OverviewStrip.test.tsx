import { fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { OverviewStrip } from './OverviewStrip';
import { useUiStore } from '@/ui/uiStore';
import { useLiveStore } from '@/live/liveStore';
import { eventsFixture } from '@/test/fixtures/events';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';

const tile = (name: string) => screen.getByRole('group', { name });

describe('OverviewStrip', () => {
  beforeEach(() => { seedLive([eventsFixture['zone.state']]); });

  it('tiles reflect derived values', () => {
    renderWithProviders(<OverviewStrip />);
    expect(within(tile('City status')).getByText('Warning')).toBeInTheDocument();
    expect(tile('City status')).toHaveAttribute('data-band', 'warning');
    expect(tile('Active threats')).toHaveTextContent('1');
    expect(tile('Active threats')).toHaveTextContent('Landslide 1');
    expect(tile('Risk zones')).toHaveTextContent('1');
    expect(tile('Risk zones')).toHaveTextContent('Hillview');
    expect(tile('Preventive actions')).toHaveTextContent('3');
    expect(tile('Preventive actions')).toHaveTextContent('1 executed, 1 verified, 0 failed');
    expect(tile('Active incidents')).toHaveTextContent('1');
    expect(tile('Emergency resources')).toHaveTextContent('3 of 3 crews available');
  });

  it('clicking a tile selects the incident', () => {
    renderWithProviders(<OverviewStrip />);
    fireEvent.click(within(tile('Active incidents')).getByRole('button'));
    expect(useUiStore.getState().selectedIncidentId).toBe('inc_1');
  });

  it('clicking risk zones selects the zone and its incident', () => {
    renderWithProviders(<OverviewStrip />);
    fireEvent.click(within(tile('Risk zones')).getByRole('button'));
    expect(useUiStore.getState().selectedEntity).toEqual({ kind: 'zone', id: 'hillview' });
    expect(useUiStore.getState().selectedIncidentId).toBe('inc_1');
  });

  it('shows placeholders and aria-busy before the first snapshot', () => {
    seedLive([], { snapshot: false });
    renderWithProviders(<OverviewStrip />);
    expect(tile('City status')).toHaveTextContent('—');
    expect(tile('Emergency resources')).toHaveTextContent('—');
    expect(screen.getByTestId('overview-strip')).toHaveAttribute('aria-busy', 'true');
  });

  it('keeps its values while the connection is reconnecting', () => {
    useLiveStore.getState().setConnection('reconnecting');
    renderWithProviders(<OverviewStrip />);
    expect(tile('Active incidents')).toHaveTextContent('1');
    expect(screen.getByTestId('overview-strip')).toHaveAttribute('aria-busy', 'false');
  });
});
