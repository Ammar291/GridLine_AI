import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Chunk } from '@/api/types';
import { useUiStore } from '@/ui/uiStore';
import { eventsFixture } from '@/test/fixtures/events';
import { fakeClient } from '@/test/fakeClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';
import { SourceDrawer } from './SourceDrawer';

const chunkFixture: Chunk = {
  id: 'dmp-2024#s4.2', doc_id: 'dmp-2024', doc_title: 'Disaster Management Policy', section: 's4.2', kind: 'policy',
  text: 'fixture: chunk text', metadata: {},
};

describe('SourceDrawer', () => {
  beforeEach(() => { seedLive([eventsFixture['sensor.reading'], eventsFixture['zone.state']]); });

  it('renders nothing when no source is selected', () => {
    renderWithProviders(<SourceDrawer />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('shows a cited chunk with its document title, section and text', async () => {
    useUiStore.getState().openSource('dmp-2024#s4.2');
    const chunk = vi.fn(() => Promise.resolve(chunkFixture));
    renderWithProviders(<SourceDrawer />, fakeClient({ chunk }));
    const dialog = screen.getByRole('dialog', { name: 'Source' });
    expect(await within(dialog).findByText('fixture: chunk text')).toBeInTheDocument();
    expect(within(dialog).getByText('Disaster Management Policy')).toBeInTheDocument();
    expect(within(dialog).getByText('s4.2')).toBeInTheDocument();
    expect(chunk).toHaveBeenCalledWith('dmp-2024#s4.2');
  });

  it('says the source could not be loaded and retries', async () => {
    useUiStore.getState().openSource('dmp-2024#s4.2');
    const chunk = vi.fn(() => Promise.reject(new Error('fixture: offline')));
    renderWithProviders(<SourceDrawer />, fakeClient({ chunk }));
    expect(await screen.findByText('Source could not be loaded.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => { expect(chunk).toHaveBeenCalledTimes(2); });
  });

  it('shows a cited sensor reading from live state without fetching a chunk', () => {
    useUiStore.getState().openSource('sensor:RG-02@2026-07-14T10:30:00');
    const chunk = vi.fn(() => Promise.resolve(chunkFixture));
    renderWithProviders(<SourceDrawer />, fakeClient({ chunk }));
    const dialog = screen.getByRole('dialog', { name: 'Source' });
    expect(within(dialog).getByText('Live reading')).toBeInTheDocument();
    expect(within(dialog).getByText('RG-02')).toBeInTheDocument();
    expect(within(dialog).getByText('84 mm/h')).toBeInTheDocument();
    expect(chunk).not.toHaveBeenCalled();
  });

  it('shows cited zone state from live state', () => {
    useUiStore.getState().openSource('state:zone.hillview');
    renderWithProviders(<SourceDrawer />);
    const dialog = screen.getByRole('dialog', { name: 'Source' });
    expect(within(dialog).getByText('Live state')).toBeInTheDocument();
    expect(within(dialog).getByText('Hillview')).toBeInTheDocument();
    expect(within(dialog).getByText('0.61')).toBeInTheDocument();
  });

  it('shows a cited event from the live feed', () => {
    useUiStore.getState().openSource('event:evt_sensor.reading');
    renderWithProviders(<SourceDrawer />);
    expect(screen.getByRole('dialog', { name: 'Source' })).toHaveTextContent('Rainfall RG-02 (Hillview) 84 mm/h');
  });

  it('closes on Escape', () => {
    useUiStore.getState().openSource('state:zone.hillview');
    renderWithProviders(<SourceDrawer />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(useUiStore.getState().sourceCitationId).toBeNull();
  });
});
