import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ScenarioBar } from './ScenarioBar';
import { ProviderBadge } from './ProviderBadge';
import { ModeBanner } from './ModeBanner';
import { OverviewStrip } from '@/components/overview/OverviewStrip';
import { ApiError } from '@/api/client';
import type { SimStatus } from '@/api/types';
import { useLiveStore } from '@/live/liveStore';
import { fakeClient } from '@/test/fakeClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';

const status: SimStatus = { scenario: 'hillside_landslide', running: true, speed: 1, sim_time: null, tick: 0 };

describe('ScenarioBar', () => {
  beforeEach(() => {
    seedLive();
    useLiveStore.setState({ sim: { simTime: null, tick: 0, running: false, speed: 1, scenario: null } });
  });

  it('Start calls simulation.start with the selected scenario and speed', async () => {
    const start = vi.fn(() => Promise.resolve(status));
    const client = fakeClient();
    renderWithProviders(<ScenarioBar />, { ...client, simulation: { ...client.simulation, start } });
    await screen.findByRole('option', { name: 'Hillside landslide' });
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    await waitFor(() => { expect(start).toHaveBeenCalledWith({ scenario: 'hillside_landslide', speed: 1 }); });
  });

  it('reads Pause while running and Resume when paused mid-run', () => {
    useLiveStore.setState({ sim: { simTime: '2026-07-14T07:00:00', tick: 12, running: true, speed: 1, scenario: 'hillside_landslide' } });
    const { unmount } = renderWithProviders(<ScenarioBar />);
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
    expect(screen.getByText('07:00:00')).toBeInTheDocument();
    unmount();
    useLiveStore.setState({ sim: { simTime: '2026-07-14T07:00:00', tick: 12, running: false, speed: 1, scenario: 'hillside_landslide' } });
    renderWithProviders(<ScenarioBar />);
    expect(screen.getByRole('button', { name: 'Resume' })).toBeInTheDocument();
  });

  it('shows an inline error when a control fails', async () => {
    const client = fakeClient();
    const reset = vi.fn(() => Promise.reject(new ApiError(500, null, 'boom')));
    renderWithProviders(<ScenarioBar />, { ...client, simulation: { ...client.simulation, reset } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Reset failed (500)');
  });

  it('disables inject in mock mode', async () => {
    renderWithProviders(<ScenarioBar />);
    await screen.findByRole('option', { name: 'Hillside landslide' });
    expect(screen.getByRole('combobox', { name: 'Inject' })).toBeDisabled();
  });
});

describe('ProviderBadge', () => {
  it('names the provider', () => {
    const { rerender } = render(<ProviderBadge llm={{ provider: 'none', model: null }} />);
    expect(screen.getByText('No backend')).toBeInTheDocument();
    rerender(<ProviderBadge llm={{ provider: 'anthropic', model: 'claude-opus-5' }} />);
    expect(screen.getByText('Anthropic claude-opus-5')).toBeInTheDocument();
    rerender(<ProviderBadge llm={{ provider: 'mock', model: null }} />);
    expect(screen.getByText('Mock reasoner')).toBeInTheDocument();
    rerender(<ProviderBadge llm={null} />);
    expect(screen.getByText('No backend')).toBeInTheDocument();
  });
});

describe('ModeBanner', () => {
  it('shows the mock banner and hides when http is open', () => {
    const { rerender, container } = render(<ModeBanner mode="mock" connection="open" />);
    expect(screen.getByText('Mock data. Backend not connected.')).toBeInTheDocument();
    rerender(<ModeBanner mode="http" connection="open" />);
    expect(container).toBeEmptyDOMElement();
    rerender(<ModeBanner mode="http" connection="connecting" />);
    expect(screen.getByText('Connecting…')).toBeInTheDocument();
  });

  it('keeps band colours for severity: the mock notice is ink on slate, a lost connection is a warning', () => {
    const { rerender } = render(<ModeBanner mode="mock" connection="open" />);
    expect(screen.getByRole('status').className).not.toMatch(/band-/);
    rerender(<ModeBanner mode="http" connection="reconnecting" />);
    expect(screen.getByRole('status')).toHaveClass('border-l-band-warning', 'text-band-warning-text', 'border-b-line');
  });

  it('reconnecting shows the banner while panels keep their last data', () => {
    seedLive();
    useLiveStore.getState().setMode('http');
    useLiveStore.getState().setConnection('reconnecting');
    render(<ModeBanner mode="http" connection="reconnecting" />);
    expect(screen.getByText('Connection lost. Reconnecting…')).toBeInTheDocument();
    renderWithProviders(<OverviewStrip />);
    expect(screen.getByRole('group', { name: 'Active incidents' })).toHaveTextContent('1');
  });
});
