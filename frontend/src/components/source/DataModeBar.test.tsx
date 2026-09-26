import { fireEvent, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { SourceStatus } from '@/api/types';
import { useLiveStore } from '@/live/liveStore';
import { fakeClient } from '@/test/fakeClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';
import { DataModeBar } from './DataModeBar';
import { LiveConditions } from './LiveConditions';

const LIVE: SourceStatus = {
  mode: 'live', label: 'LIVE — Kalyan-Dombivli', city: 'Kalyan-Dombivli', provider: 'Open-Meteo', latitude: 19.235, longitude: 73.13,
  poll_seconds: 300, last_updated: '2026-09-26T10:31:00Z', last_error: null,
};

describe('DataModeBar', () => {
  beforeEach(() => { seedLive(); useLiveStore.setState({ mode: 'http' }); });

  it('shows DEMO — Nandipur by default and switches to LIVE through the API', async () => {
    const setSource = vi.fn(() => Promise.resolve(LIVE));
    renderWithProviders(<DataModeBar />, fakeClient({ mode: 'http', setSource }));
    expect(screen.getByTestId('data-mode-label')).toHaveTextContent('DEMO — Nandipur');
    expect(screen.getByRole('radio', { name: 'DEMO' })).toHaveAttribute('aria-checked', 'true');
    fireEvent.click(screen.getByRole('radio', { name: 'LIVE' }));
    await waitFor(() => { expect(setSource).toHaveBeenCalledWith('live'); });
  });

  it('labels live mode with its city and freshness', () => {
    useLiveStore.setState({ source: LIVE });
    renderWithProviders(<DataModeBar />, fakeClient({ mode: 'http' }));
    expect(screen.getByTestId('data-mode-label')).toHaveTextContent('LIVE — Kalyan-Dombivli');
    expect(screen.getByText(/Open-Meteo/)).toBeInTheDocument();
  });

  it('says so when live data is unavailable instead of showing numbers', () => {
    useLiveStore.setState({ source: { ...LIVE, last_updated: null, last_error: 'URLError: offline' } });
    renderWithProviders(<LiveConditions />, fakeClient({ mode: 'http' }));
    expect(screen.getByRole('alert')).toHaveTextContent('URLError: offline');
  });

  it('renders the latest live observation', () => {
    useLiveStore.setState({
      source: LIVE,
      liveWeather: {
        observation: {
          station_id: 'OM-KDMC', rainfall_intensity_mm_h: 1.2, cumulative_rainfall_24h_mm: 70.4, temperature_c: 27.5, wind_speed_kmh: 18,
          wind_direction_deg: 262, severity: 'moderate', observedAt: '2026-09-26T10:30:00Z',
        },
        forecast: null,
      },
    });
    renderWithProviders(<LiveConditions />, fakeClient({ mode: 'http' }));
    expect(screen.getByText('70.4 mm')).toBeInTheDocument();
    expect(screen.getByText('IMD: Heavy')).toBeInTheDocument();
    expect(screen.getByText('27.5 °C')).toBeInTheDocument();
  });
});
