import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
import { ApiClientProvider } from './ApiClientProvider';
import { useCity, useDecideApproval } from './queries';
import type { ApiClient } from './client';
import { fakeClient } from '@/test/fakeClient';
import { decidedApprovalFixture } from '@/test/fixtures/approval';

function wrapper(client: ApiClient) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}><ApiClientProvider client={client}>{children}</ApiClientProvider></QueryClientProvider>);
}
describe('queries', () => {
  it('useCity loads through the provided client', async () => {
    const { result } = renderHook(() => useCity(), { wrapper: wrapper(fakeClient()) });
    await waitFor(() => { expect(result.current.data?.zones).toHaveLength(6); });
  });
  it('useDecideApproval calls decide with id and body', async () => {
    const decide = vi.fn(() => Promise.resolve(decidedApprovalFixture));
    const { result } = renderHook(() => useDecideApproval(), { wrapper: wrapper(fakeClient({ decide })) });
    result.current.mutate({ id: 'appr_1', body: { decision: 'approve', approved_action_ids: ['act_1', 'act_2'] } });
    await waitFor(() => { expect(result.current.isSuccess).toBe(true); });
    expect(decide).toHaveBeenCalledWith('appr_1', { decision: 'approve', approved_action_ids: ['act_1', 'act_2'] });
  });
});
