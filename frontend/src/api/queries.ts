import { useMutation, useQuery, useQueryClient, type UseMutationResult, type UseQueryResult } from '@tanstack/react-query';
import { useApiClient } from './ApiClientProvider';
import type { ApiError } from './client';
import type { Action, Approval, ApprovalDecision, ApprovalStatus, Chunk, City, Incident, InjectEvent, LlmStatus, SimStatus } from './types';

export const queryKeys = {
  city: ['city'] as const,
  llm: ['llm'] as const,
  incidents: ['incidents'] as const,
  incident: (id: string) => ['incident', id] as const,
  approvals: (s?: ApprovalStatus) => ['approvals', s ?? 'all'] as const,
  actions: ['actions'] as const,
  chunk: (id: string) => ['chunk', id] as const,
  document: (id: string) => ['document', id] as const,
};

export function useCity(): UseQueryResult<City> {
  const client = useApiClient();
  return useQuery({ queryKey: queryKeys.city, queryFn: () => client.city() });
}

export function useLlmStatus(): UseQueryResult<LlmStatus> {
  const client = useApiClient();
  return useQuery({ queryKey: queryKeys.llm, queryFn: () => client.llmStatus(), refetchInterval: 15_000 });
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
  start: UseMutationResult<SimStatus, ApiError, { scenario: string; speed: number }>;
  pause: UseMutationResult<SimStatus, ApiError, void>;
  resume: UseMutationResult<SimStatus, ApiError, void>;
  reset: UseMutationResult<SimStatus, ApiError, void>;
  setSpeed: UseMutationResult<SimStatus, ApiError, number>;
  inject: UseMutationResult<SimStatus, ApiError, InjectEvent>;
}

export function useSimulationControls(): SimulationControls {
  const client = useApiClient();
  return {
    start: useMutation<SimStatus, ApiError, { scenario: string; speed: number }>({ mutationFn: (b) => client.simulation.start(b) }),
    pause: useMutation<SimStatus, ApiError>({ mutationFn: () => client.simulation.pause() }),
    resume: useMutation<SimStatus, ApiError>({ mutationFn: () => client.simulation.resume() }),
    reset: useMutation<SimStatus, ApiError>({ mutationFn: () => client.simulation.reset() }),
    setSpeed: useMutation<SimStatus, ApiError, number>({ mutationFn: (s) => client.simulation.setSpeed(s) }),
    inject: useMutation<SimStatus, ApiError, InjectEvent>({ mutationFn: (b) => client.simulation.inject(b) }),
  };
}
