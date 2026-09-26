import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from '@/App';
import { MockApiClient } from '@/mock/MockApiClient';

describe('App', () => {
  it('renders the shell with every panel and the mock banner', async () => {
    render(<App client={new MockApiClient({ tickMs: 100000 })} />);
    expect(screen.getByRole('heading', { name: 'GridLine AI' })).toBeInTheDocument();
    for (const title of ['City map', 'Risk timeline', 'Live events', 'Incident', 'Approvals', 'Actions']) {
      expect(screen.getByRole('heading', { name: title })).toBeInTheDocument();
    }
    expect(screen.getByText('Mock data. Backend not connected.')).toBeInTheDocument();
    expect(await screen.findByText('No backend')).toBeInTheDocument();
    expect(await screen.findByRole('option', { name: 'Hillside landslide' })).toBeInTheDocument();
    expect(screen.getByTestId('dashboard')).toHaveClass('overflow-hidden', 'h-screen');
  });

  it('Start drives the mock replay: sim clock advances and city status goes Watch then Warning', async () => {
    render(<App client={new MockApiClient({ tickMs: 4 })} />);
    await screen.findByRole('option', { name: 'Hillside landslide' });
    const status = () => screen.getByRole('group', { name: 'City status' });
    expect(within(status()).getByText('Normal')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Start' }));
    await waitFor(() => { expect(within(status()).getByText('Watch')).toBeInTheDocument(); }, { timeout: 3000, interval: 5 });
    await waitFor(() => { expect(within(status()).getByText('Warning')).toBeInTheDocument(); }, { timeout: 3000 });
    expect(screen.getByRole('group', { name: 'Active incidents' })).toHaveTextContent('1');
    expect(screen.getByText(/^\d\d:\d\d:\d\d$/)).toBeInTheDocument();
  });
});
