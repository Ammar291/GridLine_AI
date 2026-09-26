import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ScenarioBar } from './ScenarioBar';
import { ProviderBadge } from './ProviderBadge';
import { ModeBanner } from './ModeBanner';
import { OverviewStrip } from '@/components/overview/OverviewStrip';
import { ApiError } from '@/api/client';
import type { SimulationStatus, SourceStatus } from '@/api/types';
import { useLiveStore } from '@/live/liveStore';
import { initialSim, type SimState } from '@/live/types';
import { cityFixture } from '@/test/fixtures/city';
import { fakeClient } from '@/test/fakeClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';

const status: SimulationStatus = {
  state: 'running', running: true, scenario: 'hillside_landslide', seed: 42, speed: 1, tick: 0, sim_time: '2026-07-14T06:00:00Z',
  stage: null, minutes_per_tick: 5, tick_seconds: 1,
};
const sim = (s: Partial<SimState>) => { useLiveStore.setState({ sim: { ...initialSim(), ...s } }); };

describe('ScenarioBar', () => {
  beforeEach(() => {
    seedLive();
    sim({ scenario: 'flash_flood' });
  });

  it('lists the backend scenarios by title; Start names the chosen one when it is not the loaded one', async () => {
    const start = vi.fn(() => Promise.resolve(status));
    const client = fakeClient();
    renderWithProviders(<ScenarioBar />, { ...client, simulation: { ...client.simulation, start } });
    await screen.findByRole('option', { name: 'Hillside landslide' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Scenario' }), { target: { value: 'hillside_landslide' } });
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    await waitFor(() => { expect(start).toHaveBeenCalledWith({ scenario: 'hillside_landslide', speed: 1 }); });
  });

  it('Start continues the loaded scenario without resetting it', async () => {
    const start = vi.fn(() => Promise.resolve(status));
    const client = fakeClient();
    renderWithProviders(<ScenarioBar />, { ...client, simulation: { ...client.simulation, start } });
    await screen.findByRole('option', { name: 'Flash flood' });
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    await waitFor(() => { expect(start).toHaveBeenCalledWith({ speed: 1 }); });
  });

  it('follows the runner state: Pause while running, Resume while paused; shows sim time and stage', () => {
    sim({ state: 'running', running: true, simTime: '2026-07-14T07:00:00Z', tick: 12, scenario: 'hillside_landslide', stage: 'slope_creep' });
    const { unmount } = renderWithProviders(<ScenarioBar />);
    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();
    expect(screen.getByText('07:00:00')).toBeInTheDocument();
    expect(screen.getByTitle('Scenario stage')).toHaveTextContent('Slope creep');
    unmount();
    sim({ state: 'paused', simTime: '2026-07-14T07:00:00Z', tick: 12, scenario: 'hillside_landslide' });
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

  it('in http mode an inject preset posts its backend request', async () => {
    useLiveStore.getState().setMode('http');
    const inject = vi.fn(() => Promise.resolve([]));
    const client = fakeClient();
    renderWithProviders(<ScenarioBar />, { ...client, mode: 'http', simulation: { ...client.simulation, inject } });
    await screen.findByRole('option', { name: 'Culvert blocked' });
    fireEvent.change(screen.getByRole('combobox', { name: 'Inject' }), { target: { value: 'culvert_blocked' } });
    await waitFor(() => { expect(inject).toHaveBeenCalledWith(cityFixture.injections[1]?.request); });
  });

  it('lists one demo event per backend trigger, then Reset, in a Demo events group', async () => {
    renderWithProviders(<ScenarioBar />);
    const group = await screen.findByRole('group', { name: 'Demo events' });
    await within(group).findByRole('button', { name: 'Heavy Rain' });
    expect(within(group).getAllByRole('button').map((b) => b.textContent)).toEqual([
      'Heavy Rain', 'Landslide', 'Drainage Block', 'Flash Flood', 'Industrial Fire', 'Cascading Disaster', 'Reset',
    ]);
    expect(within(group).getByRole('button', { name: 'Flash Flood' })).toHaveAttribute('title', 'fixture: cloudburst');
  });

  it('disables the demo events in mock mode but keeps Reset', async () => {
    renderWithProviders(<ScenarioBar />);
    const group = await screen.findByRole('group', { name: 'Demo events' });
    expect(await within(group).findByRole('button', { name: 'Heavy Rain' })).toBeDisabled();
    expect(within(group).getByRole('button', { name: 'Reset' })).toBeEnabled();
  });

  it('in http mode each demo event posts its trigger', async () => {
    useLiveStore.getState().setMode('http');
    const trigger = vi.fn(() => Promise.resolve([]));
    const client = fakeClient();
    renderWithProviders(<ScenarioBar />, { ...client, mode: 'http', simulation: { ...client.simulation, trigger } });
    for (const t of cityFixture.triggers) {
      const button = await screen.findByRole('button', { name: t.label });
      await waitFor(() => { expect(button).toBeEnabled(); });
      fireEvent.click(button);
      await waitFor(() => { expect(trigger).toHaveBeenLastCalledWith({ trigger: t.id }); });
    }
    expect(trigger).toHaveBeenCalledTimes(6);
  });

  it('disables every demo event while a request is pending', async () => {
    useLiveStore.getState().setMode('http');
    const trigger = vi.fn(() => new Promise<never>(() => undefined));
    const client = fakeClient();
    renderWithProviders(<ScenarioBar />, { ...client, mode: 'http', simulation: { ...client.simulation, trigger } });
    fireEvent.click(await screen.findByRole('button', { name: 'Landslide' }));
    await waitFor(() => { expect(screen.getByRole('button', { name: 'Flash Flood' })).toBeDisabled(); });
    fireEvent.click(screen.getByRole('button', { name: 'Flash Flood' }));
    expect(trigger).toHaveBeenCalledTimes(1);
  });

  it('a failed demo event shows an inline error', async () => {
    useLiveStore.getState().setMode('http');
    const trigger = vi.fn(() => Promise.reject(new ApiError(409, null, 'live')));
    const client = fakeClient();
    renderWithProviders(<ScenarioBar />, { ...client, mode: 'http', simulation: { ...client.simulation, trigger } });
    fireEvent.click(await screen.findByRole('button', { name: 'Heavy Rain' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Demo event failed (409)');
  });

  it('shows no demo events in LIVE mode', () => {
    const live: SourceStatus = {
      mode: 'live', label: 'LIVE — Kalyan-Dombivli', city: 'Kalyan-Dombivli', provider: 'Open-Meteo', latitude: 19.235,
      longitude: 73.13, poll_seconds: 300, last_updated: null, last_error: null,
    };
    useLiveStore.setState({ source: live });
    renderWithProviders(<ScenarioBar />);
    expect(screen.queryByRole('group', { name: 'Demo events' })).toBeNull();
  });
});

describe('ProviderBadge', () => {
  it('names the provider, and a connected backend without an LLM layer as having no reasoner yet', () => {
    const { rerender } = render(<ProviderBadge llm={{ provider: 'none', model: null }} />);
    expect(screen.getByText('No backend')).toBeInTheDocument();
    rerender(<ProviderBadge llm={{ provider: 'anthropic', model: 'claude-opus-5' }} />);
    expect(screen.getByText('Anthropic claude-opus-5')).toBeInTheDocument();
    rerender(<ProviderBadge llm={{ provider: 'mock', model: null }} />);
    expect(screen.getByText('Mock reasoner')).toBeInTheDocument();
    rerender(<ProviderBadge llm={null} />);
    expect(screen.getByText('No backend')).toBeInTheDocument();
    rerender(<ProviderBadge llm={null} backend />);
    expect(screen.getByText('No reasoner yet')).toBeInTheDocument();
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
