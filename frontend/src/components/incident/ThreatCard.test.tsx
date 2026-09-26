import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { Zone } from '@/api/types';
import { useUiStore } from '@/ui/uiStore';
import { cityFixture } from '@/test/fixtures/city';
import { incidentFixture, runFixture } from '@/test/fixtures/incident';
import { ThreatCard } from './ThreatCard';

function zone(id: string): Zone {
  const z = cityFixture.zones.find((x) => x.id === id);
  if (!z) throw new Error(`fixture zone ${id} missing`);
  return z;
}
const hillview = zone('hillview');
const riverside = zone('riverside');

/** The <dt> label's wrapper holds both the label and its value. */
const field = (label: string) => {
  const wrapper = screen.getByText(label, { selector: 'dt' }).parentElement;
  if (!wrapper) throw new Error(`no field ${label}`);
  return wrapper;
};

describe('ThreatCard', () => {
  beforeEach(() => { useUiStore.getState().reset(); });

  it('shows hazard, zone, band, assessment and prediction from the latest run', () => {
    render(<ThreatCard incident={incidentFixture} run={runFixture} zone={hillview} zoneState={hillview.state} cascadeZones={[]} />);
    expect(screen.getByRole('heading', { name: 'Landslide risk' })).toBeInTheDocument();
    expect(screen.getByText('Hillview')).toBeInTheDocument();
    expect(screen.getByText('Warning')).toHaveAttribute('data-band', 'warning');
    expect(field('Confidence')).toHaveTextContent('72%');
    expect(field('Population at risk')).toHaveTextContent('4,200');
    expect(field('Estimated onset')).toHaveTextContent('fixture: 6 to 12 hours');
    expect(field('Landslide index')).toHaveTextContent('0.15');
    expect(field('Saturation')).toHaveTextContent('40%');
    expect(field('Rain intensity')).toHaveTextContent('8 mm/h');
  });

  it('lists each contributing factor with its citation chip', () => {
    render(<ThreatCard incident={incidentFixture} run={runFixture} zone={hillview} zoneState={hillview.state} cascadeZones={[]} />);
    const factors = within(screen.getByRole('list', { name: 'Contributing factors' })).getAllByRole('listitem');
    expect(factors).toHaveLength(2);
    const [first, second] = factors as [HTMLElement, HTMLElement];
    expect(first).toHaveTextContent('fixture: factor one: fixture: 0.71');
    expect(within(first).getByRole('button', { name: 'RG-02 rain gauge' })).toBeInTheDocument();
    fireEvent.click(within(second).getByRole('button', { name: 'Disaster Management Policy §4.2' }));
    expect(useUiStore.getState().sourceCitationId).toBe('dmp-2024#s4.2');
  });

  it('adds cascade zones to the population at risk', () => {
    render(<ThreatCard incident={incidentFixture} run={runFixture} zone={hillview} zoneState={hillview.state} cascadeZones={[riverside]} />);
    expect(field('Population at risk')).toHaveTextContent('22,700');
    expect(field('Population at risk')).toHaveTextContent('Riverside');
  });

  it('says what it is waiting for when no run has finished', () => {
    render(<ThreatCard incident={incidentFixture} run={undefined} zone={hillview} zoneState={hillview.state} cascadeZones={[]} />);
    expect(field('Confidence')).toHaveTextContent('Awaiting assessment');
    expect(field('Estimated onset')).toHaveTextContent('Awaiting prediction');
    expect(screen.getByTestId('contributing-factors')).toHaveTextContent('Awaiting assessment');
    expect(screen.queryByRole('list', { name: 'Contributing factors' })).toBeNull();
  });

  it('shows the flood index for a flood incident', () => {
    render(<ThreatCard incident={{ ...incidentFixture, hazard: 'flood' }} run={undefined} zone={hillview} zoneState={hillview.state} cascadeZones={[]} />);
    expect(screen.getByRole('heading', { name: 'Flood risk' })).toBeInTheDocument();
    expect(field('Flood index')).toHaveTextContent('0.10');
  });
});
