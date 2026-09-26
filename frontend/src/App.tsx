import { useMemo, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ApiClientProvider, useApiClient } from '@/api/ApiClientProvider';
import { readApiMode, type ApiClient } from '@/api/client';
import { createApiClient } from '@/api/createApiClient';
import { Dashboard } from '@/components/layout/Dashboard';
import { PanelSlot } from '@/components/layout/PanelSlot';
import { useLive } from '@/live/useLive';

function Shell() {
  const client = useApiClient();
  useLive(client);
  return (
    <Dashboard
      map={<PanelSlot title="City map" />}
      timeline={<PanelSlot title="Risk timeline" />}
      feed={<PanelSlot title="Live events" />}
      incident={<PanelSlot title="Incident" />}
      approvals={<PanelSlot title="Approvals" />}
      actions={<PanelSlot title="Actions" />}
    />
  );
}

export default function App(props: { client?: ApiClient }) {
  const client = useMemo(() => props.client ?? createApiClient(readApiMode()), [props.client]);
  const [qc] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } }));
  return (
    <QueryClientProvider client={qc}>
      <ApiClientProvider client={client}>
        <Shell />
      </ApiClientProvider>
    </QueryClientProvider>
  );
}
