import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { Chunk } from '@/api/types';
import { useUiStore } from '@/ui/uiStore';
import { eventsFixture } from '@/test/fixtures/events';
import { fakeClient } from '@/test/fakeClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';
import { SourceDrawer } from './SourceDrawer';

/** Shaped like the RAG layer's StoredChunk that GET /api/chunks/{chunk_id} answers. */
const chunkFixture: Chunk = {
  chunk_id: 'dmp-2024#s4.2', document_id: 'dmp-2024', document_title: 'Disaster Management Policy', section_id: 's4.2',
  section: 'Rainfall thresholds', source: 'fixture: municipal corporation', kind: 'policy', category: 'policy', zone_ids: [],
  hazards: ['landslide'], text: 'fixture: chunk text', metadata: {},
};

describe('SourceDrawer', () => {
  beforeEach(() => { seedLive([eventsFixture['weather.observation'], eventsFixture['environment.water_accumulation'], eventsFixture['zone.state']]); });

  it('renders nothing when no source is selected', () => {
    renderWithProviders(<SourceDrawer />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('shows a cited chunk with its document title, section, kind, category and text', async () => {
    useUiStore.getState().openSource('dmp-2024#s4.2');
    const chunk = vi.fn(() => Promise.resolve(chunkFixture));
    renderWithProviders(<SourceDrawer />, fakeClient({ chunk }));
    const dialog = screen.getByRole('dialog', { name: 'Source' });
    expect(await within(dialog).findByText('fixture: chunk text')).toBeInTheDocument();
    expect(within(dialog).getByText('Disaster Management Policy')).toBeInTheDocument();
    expect(within(dialog).getByText('s4.2 Rainfall thresholds')).toBeInTheDocument();
    expect(within(dialog).getByText('fixture: municipal corporation')).toBeInTheDocument();
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
    useUiStore.getState().openSource('sensor:RG-02@2026-07-14T10:30:00Z');
    const chunk = vi.fn(() => Promise.resolve(chunkFixture));
    renderWithProviders(<SourceDrawer />, fakeClient({ chunk }));
    const dialog = screen.getByRole('dialog', { name: 'Source' });
    expect(within(dialog).getByText('Live reading')).toBeInTheDocument();
    expect(within(dialog).getByText('RG-02')).toBeInTheDocument();
    expect(within(dialog).getByText('52.4 mm/h')).toBeInTheDocument();
    expect(chunk).not.toHaveBeenCalled();
  });

  it('shows cited zone state: the detector band (PENDING) with the live conditions', () => {
    useUiStore.getState().openSource('state:zone.hillview');
    renderWithProviders(<SourceDrawer />);
    const dialog = screen.getByRole('dialog', { name: 'Source' });
    expect(within(dialog).getByText('Live state')).toBeInTheDocument();
    expect(within(dialog).getByText('Hillview')).toBeInTheDocument();
    expect(within(dialog).getByText('0.61')).toBeInTheDocument();
    expect(within(dialog).getByText('52.4 mm/h')).toBeInTheDocument();
  });

  it('shows live conditions for a zone the detector has not reported', () => {
    useUiStore.getState().openSource('state:zone.riverside');
    renderWithProviders(<SourceDrawer />);
    const dialog = screen.getByRole('dialog', { name: 'Source' });
    expect(within(dialog).getByText('12.5 cm')).toBeInTheDocument();
    expect(within(dialog).queryByText('Band')).toBeNull();
  });

  it('shows a cited event from the live feed', () => {
    useUiStore.getState().openSource('event:evt-weather.observation');
    renderWithProviders(<SourceDrawer />);
    expect(screen.getByRole('dialog', { name: 'Source' })).toHaveTextContent('Rainfall RG-02 (Hillview) 52.4 mm/h');
  });

  it('closes on Escape', () => {
    useUiStore.getState().openSource('state:zone.hillview');
    renderWithProviders(<SourceDrawer />);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(useUiStore.getState().sourceCitationId).toBeNull();
  });
});
