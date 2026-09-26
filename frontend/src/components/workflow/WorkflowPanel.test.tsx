import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, type ApiClient } from '@/api/client';
import type { WorkflowStep } from '@/api/types';
import { useLiveStore } from '@/live/liveStore';
import { fakeClient } from '@/test/fakeClient';
import { doneSteps, RUN_ID, stepOf, waitingSteps, workflowRunFixture } from '@/test/fixtures/workflow';
import { renderWithProviders } from '@/test/renderWithProviders';
import { WorkflowPanel } from './WorkflowPanel';

type DecideRun = ApiClient['decideRunApproval'];

function seed(steps: WorkflowStep[]) {
  useLiveStore.setState({ agentRun: { runId: RUN_ID, steps } });
}
function renderPanel(decideRunApproval: DecideRun = vi.fn<DecideRun>(() => Promise.resolve(workflowRunFixture))) {
  renderWithProviders(<WorkflowPanel />, fakeClient({ decideRunApproval }));
  return decideRunApproval;
}
const row = (node: string) => {
  const el = document.querySelector(`li[data-node="${node}"]`);
  if (!(el instanceof HTMLElement)) throw new Error(`no row ${node}`);
  return el;
};

describe('WorkflowPanel', () => {
  beforeEach(() => { useLiveStore.setState({ agentRun: null }); });

  it('shows an empty state without a run', () => {
    renderPanel();
    expect(screen.getByText(/No agent run yet/)).toBeInTheDocument();
  });

  it('renders every step with the output each node produced', () => {
    seed(doneSteps);
    renderPanel();
    expect(screen.getByRole('heading', { name: 'LIVE AGENT WORKFLOW' })).toBeInTheDocument();
    expect(within(screen.getByRole('list', { name: 'Workflow steps' })).getAllByRole('listitem', { name: '' }).length).toBeGreaterThanOrEqual(11);
    expect(screen.getByText('Landslide at SL-HV-1')).toBeInTheDocument();
    expect(screen.getByText('ollama · llama3.1:8b')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Completed');

    expect(row('observe')).toHaveTextContent('fixture: 3 critical signals around Hillview');
    const path = within(row('query_graph')).getByTestId('graph-path');
    expect(path).toHaveTextContent('PR-HT2Hillview Terrace Phase 2→on→SL-HV-1Hillview upper slope→blocks→D-7');
    expect(row('query_graph')).toHaveTextContent('4 entities, 3 edges');
    expect(row('retrieve')).toHaveTextContent('Disaster Management Policy');
    expect(row('retrieve')).toHaveTextContent('similarity 0.83');
    expect(within(row('reason')).getAllByTestId('citation').map((c) => c.textContent)).toEqual(['kg:e2', 'dmp-4.2']);
    expect(row('assess')).toHaveTextContent('Landslide risk: CRITICAL');
    expect(row('assess')).toHaveTextContent('87% confidence');
    expect(row('assess')).toHaveTextContent('Grounded');
    expect(row('recommend')).toHaveTextContent('Halt Hillview Terrace Phase 2');
    expect(row('recommend')).toHaveTextContent('Needs approval');
    expect(row('approval_gate')).toHaveTextContent('Approved 1 action');
    expect(row('execute')).toHaveTextContent('fixture: PR-HT2 halted');
    expect(row('verify')).toHaveTextContent('project status: expected halted, observed halted');
    expect(row('complete')).toHaveTextContent('status: halted');
    expect(screen.queryByRole('button', { name: 'APPROVE ACTIONS' })).not.toBeInTheDocument();
  });

  it('waiting at the gate: APPROVE ACTIONS posts approve for the run, later steps stay pending', async () => {
    seed(waitingSteps);
    const decide = renderPanel();
    expect(screen.getByRole('status')).toHaveTextContent('Waiting for approval');
    expect(row('approval_gate')).toHaveAttribute('aria-current', 'step');
    expect(row('execute')).toHaveAttribute('data-status', 'pending');
    fireEvent.click(screen.getByRole('button', { name: 'APPROVE ACTIONS' }));
    await waitFor(() => { expect(decide).toHaveBeenCalledWith(RUN_ID, { decision: 'approve' }); });
    await waitFor(() => { expect(screen.getByRole('button', { name: 'APPROVE ACTIONS' })).toBeDisabled(); });
    expect(screen.getByRole('button', { name: 'Reject' })).toBeDisabled();
  });

  it('Reject posts reject; a failed decision shows inline', async () => {
    seed(waitingSteps);
    const decide = renderPanel(vi.fn<DecideRun>(() => Promise.reject(new ApiError(409, null, 'The run is not waiting for approval'))));
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }));
    await waitFor(() => { expect(decide).toHaveBeenCalledWith(RUN_ID, { decision: 'reject' }); });
    expect(await screen.findByRole('alert')).toHaveTextContent('Decision failed: The run is not waiting for approval');
    expect(screen.getByRole('button', { name: 'APPROVE ACTIONS' })).toBeEnabled();
  });

  it('a failed step shows its error and fails the run', () => {
    seed([...doneSteps.slice(0, 8), stepOf('execute', { status: 'failed', output: null, error: 'tool halt_construction raised' })]);
    renderPanel();
    expect(screen.getByRole('status')).toHaveTextContent('Failed');
    expect(within(row('execute')).getByRole('alert')).toHaveTextContent('tool halt_construction raised');
  });

  it('shows the mock fallback and why Ollama was not used', () => {
    const reason = stepOf('reason', {
      output: { node: 'reason', provider: 'mock', model: null, fallback_reason: 'connection refused', duration_ms: 12, summary: 's', claims: [] },
    });
    seed([...doneSteps.slice(0, 4), reason]);
    renderPanel();
    expect(screen.getByText('mock — Ollama unavailable: connection refused')).toBeInTheDocument();
    expect(row('reason')).toHaveAttribute('aria-current', 'step');
  });

  it('shows mock (offline) when the mock reasoner ran without a fallback', () => {
    const reason = stepOf('reason', {
      output: { node: 'reason', provider: 'mock', model: null, fallback_reason: null, duration_ms: 12, summary: 's', claims: [] },
    });
    seed([...doneSteps.slice(0, 4), reason]);
    renderPanel();
    expect(screen.getByText('mock (offline)')).toBeInTheDocument();
  });
});
