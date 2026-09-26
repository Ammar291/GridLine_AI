import { useMemo, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ApiClientProvider, useApiClient } from '@/api/ApiClientProvider';
import { readApiMode, type ApiClient } from '@/api/client';
import { createApiClient } from '@/api/createApiClient';
import { ActionsLog } from '@/components/actions/ActionsLog';
import { ApprovalsInbox } from '@/components/approvals/ApprovalsInbox';
import { EventFeed } from '@/components/events/EventFeed';
import { IncidentPanel } from '@/components/incident/IncidentPanel';
import { Dashboard } from '@/components/layout/Dashboard';
import { CityMap } from '@/components/map/CityMap';
import { RiskTimeline } from '@/components/timeline/RiskTimeline';
import { useLive } from '@/live/useLive';

function Shell() {
  const client = useApiClient();
  useLive(client);
  return (
    <Dashboard
      map={<CityMap />}
      timeline={<RiskTimeline />}
      feed={<EventFeed />}
      incident={<IncidentPanel />}
      approvals={<ApprovalsInbox />}
      actions={<ActionsLog />}
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
