import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { Event } from '@/api/types';
import { useLiveStore } from '@/live/liveStore';
import { useUiStore } from '@/ui/uiStore';
import { eventsFixture } from '@/test/fixtures/events';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';
import { RiskTimeline } from './RiskTimeline';
import { TimelineTooltip } from './TimelineTooltip';

const SIZE = { width: 800, height: 400 };

function hillviewAt(hhmm: string, landslide: number, band: 'watch' | 'warning', prev: 'watch' | null): Event {
  const e = eventsFixture['zone.state'];
  const simTime = `2026-07-14T${hhmm}:00`;
  return {
    ...e, id: `evt_zs_${hhmm}`, sim_time: simTime,
    payload: { ...e.payload, landslide_index: landslide, band, prev_band: prev, updated_sim_time: simTime },
  };
}

const rising: Event[] = [hillviewAt('10:00', 0.3, 'watch', null), hillviewAt('10:05', 0.4, 'watch', null), hillviewAt('10:10', 0.61, 'warning', 'watch')];

describe('RiskTimeline', () => {
  beforeEach(() => { seedLive(rising); });

  it('renders both charts, the legend and landslide thresholds for the selected incident zone', () => {
    renderWithProviders(<RiskTimeline size={SIZE} />);
    expect(screen.getByRole('heading', { name: 'Rain intensity (mm/h)' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Indices' })).toBeInTheDocument();
    for (const name of ['Landslide index', 'Flood index', 'Saturation']) expect(screen.getByText(name)).toBeInTheDocument();
    expect(screen.getByText('Landslide thresholds')).toBeInTheDocument();
    for (const t of ['Watch 0.35', 'Warning 0.55', 'Critical 0.75']) expect(screen.getByText(t)).toBeInTheDocument();
    expect(screen.getByRole('combobox', { name: 'Zone' })).toHaveValue('hillview');
  });

  it('draws the series and a marker for the band-change milestone', () => {
    const { container } = renderWithProviders(<RiskTimeline size={SIZE} />);
    expect(container.querySelectorAll('.recharts-bar-rectangle')).toHaveLength(3);
    expect(container.querySelectorAll('.recharts-line')).toHaveLength(2);
    expect(container.querySelectorAll('.recharts-area')).toHaveLength(1);
    const markers = container.querySelectorAll('[data-milestone-kind]');
    expect(markers).toHaveLength(1);
    expect(markers[0]).toHaveTextContent('Hillview: Warning');
  });

  it('lines up bar centres with index points so both charts share one x axis', () => {
    const { container } = renderWithProviders(<RiskTimeline size={SIZE} />);
    const barCentres = [...container.querySelectorAll('.recharts-bar-rectangle path')].map((p) => {
      const d = p.getAttribute('d') ?? '';
      const xs = [...d.matchAll(/[ML]\s*([\d.]+)[ ,]/g)].map((m) => Number(m[1]));
      return (Math.min(...xs) + Math.max(...xs)) / 2;
    });
    const line = container.querySelector('.recharts-line-curve')?.getAttribute('d') ?? '';
    const pointXs = [...line.matchAll(/[ML]\s*([\d.]+)[ ,]/g)].map((m) => Number(m[1]));
    expect(barCentres).toHaveLength(3);
    expect(pointXs).toHaveLength(3);
    pointXs.forEach((x, i) => { expect(x).toBeCloseTo(barCentres[i] ?? Number.NaN, 0); });
    const marker = container.querySelector('[data-milestone-kind] circle');
    expect(Number(marker?.getAttribute('cx'))).toBeCloseTo(pointXs[2] ?? Number.NaN, 0); // the 10:10 band change
  });

  it('switching to a zone without readings shows its empty state', () => {
    renderWithProviders(<RiskTimeline size={SIZE} />);
    fireEvent.change(screen.getByRole('combobox', { name: 'Zone' }), { target: { value: 'riverside' } });
    expect(useUiStore.getState().timelineZoneId).toBe('riverside');
    expect(screen.getByRole('note')).toHaveTextContent('No readings yet for Riverside.');
  });

  it('shows the empty state when the city is known but nothing has been read', () => {
    seedLive();
    renderWithProviders(<RiskTimeline size={SIZE} />);
    expect(screen.getByRole('note')).toHaveTextContent('Readings appear here once the simulation runs.');
  });

  it('shows a loading state before the first snapshot', () => {
    seedLive([], { snapshot: false });
    renderWithProviders(<RiskTimeline size={SIZE} />);
    expect(screen.getByLabelText('Loading readings')).toHaveAttribute('aria-busy', 'true');
  });

  it('shows an error when the connection is down and nothing has been read', () => {
    seedLive([], { snapshot: false });
    useLiveStore.getState().setConnection('reconnecting');
    renderWithProviders(<RiskTimeline size={SIZE} />);
    expect(screen.getByRole('alert')).toHaveTextContent('No live connection. Readings resume when it reconnects.');
  });

  it('keeps its charts while reconnecting', () => {
    useLiveStore.getState().setConnection('reconnecting');
    renderWithProviders(<RiskTimeline size={SIZE} />);
    expect(screen.getByRole('heading', { name: 'Indices' })).toBeInTheDocument();
  });
});

describe('TimelineTooltip', () => {
  it('lists every series at the hovered time, values first, plus the milestones there', () => {
    const row = { simTime: '2026-07-14T10:10:00', label: '10:10', rain: 84, saturation: 0.71, landslide: 0.61, flood: 0.05 };
    render(<TimelineTooltip row={row} markers={[{ id: 'm1', simTime: row.simTime, label: 'Hillview: Warning', kind: 'band' }]} />);
    const items = screen.getAllByRole('listitem').map((li) => li.textContent);
    expect(items).toEqual(['84 mm/hRain intensity', '71%Saturation', '0.61Landslide index', '0.05Flood index', 'Hillview: Warning']);
    expect(screen.getByText('Sim time 10:10')).toBeInTheDocument();
  });
});
