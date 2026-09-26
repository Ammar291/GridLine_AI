import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement } from 'react';
import { ApiClientProvider } from '@/api/ApiClientProvider';
import type { ApiClient } from '@/api/client';
import { fakeClient } from './fakeClient';

/** Renders inside a fresh QueryClient (no retries) and an ApiClientProvider. */
export function renderWithProviders(ui: ReactElement, client: ApiClient = fakeClient()): RenderResult {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <ApiClientProvider client={client}>{ui}</ApiClientProvider>
    </QueryClientProvider>,
  );
}
