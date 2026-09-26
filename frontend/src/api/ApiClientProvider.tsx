import { createContext, useContext, type ReactNode } from 'react';
import type { ApiClient } from './client';

const ApiClientContext = createContext<ApiClient | null>(null);

export function ApiClientProvider({ client, children }: { client: ApiClient; children: ReactNode }) {
  return <ApiClientContext value={client}>{children}</ApiClientContext>;
}

// eslint-disable-next-line react-refresh/only-export-components -- the hook belongs with its provider
export function useApiClient(): ApiClient {
  const client = useContext(ApiClientContext);
  if (!client) throw new Error('useApiClient must be used inside ApiClientProvider');
  return client;
}
