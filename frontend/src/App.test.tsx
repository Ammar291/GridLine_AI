import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import App from '@/App';
import { MockApiClient } from '@/mock/MockApiClient';
import { useUiStore } from '@/ui/uiStore';

describe('App', () => {
  beforeEach(() => { useUiStore.getState().reset(); });

  it('renders the shell with every panel and the mock banner', async () => {
    render(<App client={new MockApiClient({ tickMs: 100000 })} />);
    expect(screen.getByRole('heading', { name: 'GridLine AI' })).toBeInTheDocument();
    // Panel headings carry a count once data arrives ("Live events 1"), so match the title at the start.
    for (const title of ['City map', 'Risk timeline', 'Live events', 'Incident', 'Approvals', 'Actions']) {
      expect(screen.getByRole('heading', { name: new RegExp(`^${title}( \\d+)?$`) })).toBeInTheDocument();
    }
    expect(screen.getByText('Mock data. Backend not connected.')).toBeInTheDocument();
    expect(await screen.findByText('No backend')).toBeInTheDocument();
    expect(await screen.findByRole('option', { name: 'Hillside landslide risk' })).toBeInTheDocument();
    expect(screen.getByTestId('dashboard')).toHaveClass('overflow-hidden', 'h-screen');
  });

  it('mounts the real panels in place of the placeholders', async () => {
    render(<App client={new MockApiClient({ tickMs: 100000 })} />);
    expect(await screen.findByRole('group', { name: 'Map of Nandipur' })).toBeInTheDocument();
    expect(await screen.findByRole('log')).toBeInTheDocument();
    expect(await screen.findByRole('combobox', { name: 'Zone' })).toBeInTheDocument();
    expect(await screen.findByText('No approvals waiting. Proposed actions appear here when the agent asks for a decision.')).toBeInTheDocument();
    expect(screen.getByText('No actions yet. Approved actions appear here as they execute.')).toBeInTheDocument();
    expect(screen.getByText('No open incidents. Threats appear here when the detector opens an incident.')).toBeInTheDocument();
    expect(screen.queryByText('Coming in a later task')).toBeNull();
  });

  it('mounts the Why drawer', async () => {
    render(<App client={new MockApiClient({ tickMs: 100000 })} />);
    await screen.findByRole('group', { name: 'Map of Nandipur' });
    act(() => { useUiStore.getState().openWhy({ kind: 'action', actionId: 'act_x', incidentId: 'inc_x' }); });
    expect(screen.getByRole('dialog', { name: 'Why?' })).toHaveTextContent('This item is no longer in the live state.');
  });

  it('Start drives the mock replay: sim clock advances and the scripted detector takes the city to Watch then Warning', async () => {
    render(<App client={new MockApiClient({ tickMs: 4 })} />);
    await screen.findByRole('option', { name: 'Hillside landslide risk' });
    const status = () => screen.getByRole('group', { name: 'City status' });
    await waitFor(() => { expect(status()).toHaveTextContent('No threat detector readings yet'); });
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    await waitFor(() => { expect(within(status()).getByText('Watch')).toBeInTheDocument(); }, { timeout: 3000, interval: 5 });
    await waitFor(() => { expect(within(status()).getByText('Warning')).toBeInTheDocument(); }, { timeout: 3000 });
    expect(screen.getByRole('group', { name: 'Active incidents' })).toHaveTextContent('1');
    expect(screen.getByTitle('Simulation time')).toHaveTextContent(/^Sim time\s*\d\d:\d\d:\d\d$/);
  });
});
