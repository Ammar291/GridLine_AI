import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { Event } from '@/api/types';
import { describeEvent } from '@/live/describeEvent';
import { useLiveStore } from '@/live/liveStore';
import { useUiStore } from '@/ui/uiStore';
import { cityFixture } from '@/test/fixtures/city';
import { eventsFixture } from '@/test/fixtures/events';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';
import { EventFeed } from './EventFeed';

const dispatched: Event[] = [eventsFixture['weather.observation'], eventsFixture['zone.state'], eventsFixture['approval.requested']];
const rows = () => within(screen.getByRole('log')).getAllByRole('listitem');
const heading = () => screen.getByRole('heading', { name: /Live events/ });

describe('EventFeed', () => {
  beforeEach(() => { seedLive(dispatched); });

  it('renders rows in dispatch order with the describeEvent text and sim time', () => {
    renderWithProviders(<EventFeed />);
    const items = rows();
    expect(items).toHaveLength(5); // the seeded snapshot and incident come first
    expect(items[0]).toHaveTextContent('Connected: city state received');
    dispatched.forEach((e, i) => {
      expect(items[i + 2]).toHaveTextContent(describeEvent(e, cityFixture));
      expect(items[i + 2]).toHaveTextContent('10:31:04');
    });
    expect(heading()).toHaveTextContent('5');
  });

  it('filters by group, the count follows the visible rows, and All restores', () => {
    renderWithProviders(<EventFeed />);
    fireEvent.click(screen.getByRole('radio', { name: 'Approvals' }));
    expect(rows()).toHaveLength(1);
    expect(rows()[0]).toHaveTextContent('Approval requested for 3 actions');
    expect(heading()).toHaveTextContent('1');
    expect(useUiStore.getState().feedFilter).toBe('approval');
    fireEvent.click(screen.getByRole('radio', { name: 'All' }));
    expect(rows()).toHaveLength(5);
    expect(screen.getByRole('radio', { name: 'All' })).toBeChecked();
  });

  it('tags raised sensor bands and quiets routine readings; Readings and City filter the backend groups', () => {
    const calm: Event = { ...eventsFixture['environment.soil'], event_id: 'evt_calm', severity: 'low' };
    seedLive([eventsFixture['weather.observation'], calm, eventsFixture['infrastructure.road']]);
    renderWithProviders(<EventFeed />);
    const [, , rain, soil, road] = rows();
    expect(rain).toHaveAttribute('data-severity', 'high');
    expect(within(rain ?? document.body).getByTitle('Sensor band')).toHaveTextContent('High');
    expect(within(soil ?? document.body).queryByTitle('Sensor band')).toBeNull();
    expect(within(soil ?? document.body).getByTitle(/Soil moisture/)).toHaveClass('text-ink-2');
    expect(within(road ?? document.body).getByTitle(/Hill Road blocked/)).toHaveClass('text-ink');
    fireEvent.click(screen.getByRole('radio', { name: 'Readings' }));
    expect(rows()).toHaveLength(2);
    fireEvent.click(screen.getByRole('radio', { name: 'City' }));
    expect(rows().map((r) => r.dataset.eventType)).toEqual(['infrastructure.road']);
  });

  it('says so when a filter matches nothing yet', () => {
    renderWithProviders(<EventFeed />);
    fireEvent.click(screen.getByRole('radio', { name: 'Alerts' }));
    expect(screen.getByRole('note')).toHaveTextContent('No alert events yet.');
    expect(heading()).toHaveTextContent('0');
  });

  it('an Incident tag selects that incident', () => {
    renderWithProviders(<EventFeed />);
    const approvalRow = rows()[4];
    if (!approvalRow) throw new Error('missing row');
    fireEvent.click(within(approvalRow).getByRole('button', { name: 'Incident' }));
    expect(useUiStore.getState().selectedIncidentId).toBe('inc_1');
    expect(within(rows()[2] ?? approvalRow).queryByRole('button', { name: 'Incident' })).toBeNull();
  });

  it('shows a New events pill when scrolled up and new events arrive, and jumps back on click', () => {
    renderWithProviders(<EventFeed />);
    const scroller = screen.getByTestId('event-feed-scroll');
    Object.defineProperty(scroller, 'scrollHeight', { configurable: true, value: 2000 });
    Object.defineProperty(scroller, 'clientHeight', { configurable: true, value: 200 });
    scroller.scrollTop = 0;
    fireEvent.scroll(scroller);
    expect(screen.queryByRole('button', { name: /New events/ })).toBeNull();
    act(() => { useLiveStore.getState().dispatch({ ...eventsFixture['sim.tick'], event_id: 'evt_new_tick' }); });
    const pill = screen.getByRole('button', { name: 'New events (1)' });
    fireEvent.click(pill);
    expect(screen.queryByRole('button', { name: /New events/ })).toBeNull();
    expect(scroller.scrollTop).toBe(2000);
  });

  it('stays pinned to the newest row when already at the bottom', () => {
    renderWithProviders(<EventFeed />);
    const scroller = screen.getByTestId('event-feed-scroll');
    Object.defineProperty(scroller, 'scrollHeight', { configurable: true, value: 900 });
    act(() => { useLiveStore.getState().dispatch({ ...eventsFixture['sim.tick'], event_id: 'evt_new_tick' }); });
    expect(scroller.scrollTop).toBe(900);
    expect(screen.queryByRole('button', { name: /New events/ })).toBeNull();
  });

  it('shows the empty state when connected with no events yet', () => {
    seedLive([], { snapshot: false });
    useLiveStore.getState().setConnection('open');
    renderWithProviders(<EventFeed />);
    expect(screen.getByRole('note')).toHaveTextContent('Events appear here as the city runs.');
  });

  it('shows a loading state while connecting with no events', () => {
    seedLive([], { snapshot: false });
    renderWithProviders(<EventFeed />);
    expect(screen.getByLabelText('Connecting to the live stream')).toHaveAttribute('aria-busy', 'true');
  });

  it('shows an error when the connection is down and nothing has arrived', () => {
    seedLive([], { snapshot: false });
    useLiveStore.getState().setConnection('reconnecting');
    renderWithProviders(<EventFeed />);
    expect(screen.getByRole('alert')).toHaveTextContent('No live connection. Retrying automatically.');
  });

  it('keeps its rows while reconnecting', () => {
    useLiveStore.getState().setConnection('reconnecting');
    renderWithProviders(<EventFeed />);
    expect(rows()).toHaveLength(5);
  });
});
