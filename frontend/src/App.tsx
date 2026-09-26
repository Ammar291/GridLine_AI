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
import { LiveConditions } from '@/components/source/LiveConditions';
import { LiveForecast } from '@/components/source/LiveForecast';
import { RiskTimeline } from '@/components/timeline/RiskTimeline';
import { WorkflowPanel } from '@/components/workflow/WorkflowPanel';
import { useLiveStore } from '@/live/liveStore';
import { dataModeOf } from '@/live/liveWeather';
import { useLive } from '@/live/useLive';

function Shell() {
  const client = useApiClient();
  useLive(client);
  // One pipeline for both modes; only the data source differs, so only the source-specific panels swap.
  const live = useLiveStore((s) => dataModeOf(s) === 'live');
  const hasAgentRun = useLiveStore((s) => s.agentRun !== null);
  return (
    <Dashboard
      map={live ? <LiveConditions /> : <CityMap />}
      timeline={live ? <LiveForecast /> : <RiskTimeline />}
      feed={<EventFeed />}
      incident={hasAgentRun ? <WorkflowPanel /> : <IncidentPanel />}
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
