import { useMutation, type UseMutationResult } from '@tanstack/react-query';
import { useApiClient } from '@/api/ApiClientProvider';
import type { ApiError } from '@/api/client';
import type { WorkflowDecision, WorkflowRun } from '@/api/types';

/** Posts the operator's decision at the approval gate. The agent.step events that follow are the source of truth. */
export function useDecideRunApproval(runId: string): UseMutationResult<WorkflowRun, ApiError, WorkflowDecision> {
  const client = useApiClient();
  return useMutation<WorkflowRun, ApiError, WorkflowDecision>({ mutationFn: (body) => client.decideRunApproval(runId, body) });
}
