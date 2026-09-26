import { useMutation, useQuery, useQueryClient, type UseMutationResult, type UseQueryResult } from '@tanstack/react-query';
import { useApiClient } from './ApiClientProvider';
import type { ApiError } from './client';
import type {
  Action, Approval, ApprovalDecision, ApprovalStatus, Bands, Chunk, City, DataMode, Event, Incident, InjectRequest, LlmStatus,
  SimulationStart, SimulationStatus, SourceStatus, TriggerRequest,
} from './types';

export const queryKeys = {
  city: ['city'] as const,
  llm: ['llm'] as const,
  bands: ['bands'] as const,
  incidents: ['incidents'] as const,
  incident: (id: string) => ['incident', id] as const,
  approvals: (s?: ApprovalStatus) => ['approvals', s ?? 'all'] as const,
  actions: ['actions'] as const,
  chunk: (id: string) => ['chunk', id] as const,
  document: (id: string) => ['document', id] as const,
};

export function useCity(): UseQueryResult<City> {
  const client = useApiClient();
  return useQuery({ queryKey: queryKeys.city, queryFn: () => client.city(), staleTime: Infinity });
}

/** PENDING (LLM provider): answered 501 by the HTTP client until the backend serves it. */
export function useLlmStatus(): UseQueryResult<LlmStatus> {
  const client = useApiClient();
  return useQuery({ queryKey: queryKeys.llm, queryFn: () => client.llmStatus(), refetchInterval: 15_000, retry: false });
}

/** Index band thresholds for the timeline's threshold lines (GET /api/detector/bands). */
export function useBands(): UseQueryResult<Bands> {
  const client = useApiClient();
  return useQuery({ queryKey: queryKeys.bands, queryFn: () => client.bands(), staleTime: Infinity, retry: false });
}

export function useIncident(id: string | null): UseQueryResult<Incident> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.incident(id ?? ''),
    queryFn: () => client.incident(id ?? ''),
    enabled: id !== null && id !== '',
  });
}

export function useApprovals(status?: ApprovalStatus): UseQueryResult<Approval[]> {
  const client = useApiClient();
  return useQuery({ queryKey: queryKeys.approvals(status), queryFn: () => client.approvals(status) });
}

export function useActions(): UseQueryResult<Action[]> {
  const client = useApiClient();
  return useQuery({ queryKey: queryKeys.actions, queryFn: () => client.actions() });
}

export function useChunk(id: string | null): UseQueryResult<Chunk> {
  const client = useApiClient();
  return useQuery({
    queryKey: queryKeys.chunk(id ?? ''),
    queryFn: () => client.chunk(id ?? ''),
    enabled: id !== null && id !== '',
  });
}

/** Posts an operator decision. The approval.decided event remains the source of truth for the final state. */
export function useDecideApproval(): UseMutationResult<Approval, ApiError, { id: string; body: ApprovalDecision }> {
  const client = useApiClient();
  const qc = useQueryClient();
  return useMutation<Approval, ApiError, { id: string; body: ApprovalDecision }>({
    mutationFn: ({ id, body }) => client.decide(id, body),
    onSuccess: (approval) => {
      void qc.invalidateQueries({ queryKey: ['approvals'] });
      void qc.invalidateQueries({ queryKey: queryKeys.incident(approval.incident_id) });
    },
  });
}

export interface SimulationControls {
  start: UseMutationResult<SimulationStatus, ApiError, SimulationStart>;
  pause: UseMutationResult<SimulationStatus, ApiError, void>;
  resume: UseMutationResult<SimulationStatus, ApiError, void>;
  reset: UseMutationResult<SimulationStatus, ApiError, void>;
  setSpeed: UseMutationResult<SimulationStatus, ApiError, number>;
  inject: UseMutationResult<Event[], ApiError, InjectRequest>;
  trigger: UseMutationResult<Event[], ApiError, TriggerRequest>;
}

export function useSimulationControls(): SimulationControls {
  const client = useApiClient();
  return {
    start: useMutation<SimulationStatus, ApiError, SimulationStart>({ mutationFn: (b) => client.simulation.start(b) }),
    pause: useMutation<SimulationStatus, ApiError>({ mutationFn: () => client.simulation.pause() }),
    resume: useMutation<SimulationStatus, ApiError>({ mutationFn: () => client.simulation.resume() }),
    reset: useMutation<SimulationStatus, ApiError>({ mutationFn: () => client.simulation.reset() }),
    setSpeed: useMutation<SimulationStatus, ApiError, number>({ mutationFn: (s) => client.simulation.setSpeed(s) }),
    inject: useMutation<Event[], ApiError, InjectRequest>({ mutationFn: (b) => client.simulation.inject(b) }),
    trigger: useMutation<Event[], ApiError, TriggerRequest>({ mutationFn: (b) => client.simulation.trigger(b) }),
  };
}

/** Switches LIVE / DEMO. The source.status event on the socket is what updates the dashboard. */
export function useSetDataMode(): UseMutationResult<SourceStatus, ApiError, DataMode> {
  const client = useApiClient();
  return useMutation<SourceStatus, ApiError, DataMode>({ mutationFn: (mode) => client.setSource(mode) });
}
