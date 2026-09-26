import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, type ApiClient } from '@/api/client';
import type { Approval, ApprovalDecision, Event } from '@/api/types';
import { useUiStore } from '@/ui/uiStore';
import { decidedApprovalFixture, pendingApprovalFixture } from '@/test/fixtures/approval';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';
import { fakeClient } from '@/test/fakeClient';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';
import { ApprovalsInbox } from './ApprovalsInbox';

type Decide = ApiClient['decide'];

function renderInbox(decide: Decide = vi.fn<Decide>(() => Promise.resolve(pendingApprovalFixture))) {
  renderWithProviders(<ApprovalsInbox />, fakeClient({ decide }));
  return decide;
}
const cards = () => screen.getAllByRole('article');
const approveButton = () => screen.getByRole('button', { name: /^Approve \d+ actions?$/ });

function requested(approval: Approval): Event {
  return { ...eventsFixture['approval.requested'], id: `evt_${approval.id}`, payload: approval };
}
function decided(approval: Approval): Event {
  return { ...eventsFixture['approval.decided'], id: `evt_d_${approval.id}`, payload: approval };
}

describe('ApprovalsInbox', () => {
  beforeEach(() => { seedLive(); });

  it('lists the proposed actions with verb, target, rationale, effect, evidence and state', () => {
    renderInbox();
    expect(screen.getByRole('heading', { name: /Approvals/ })).toHaveTextContent('1');
    expect(cards()).toHaveLength(3);
    const [halt, dispatch, shelter] = cards() as [HTMLElement, HTMLElement, HTMLElement];
    expect(halt).toHaveTextContent('Halt construction');
    expect(halt).toHaveTextContent('Hillview Terrace Phase 2');
    expect(dispatch).toHaveTextContent('Dispatch crew');
    expect(dispatch).toHaveTextContent('Rescue Team 03 to Hillview');
    expect(shelter).toHaveTextContent('Open shelter');
    expect(halt).toHaveTextContent('fixture: rationale one');
    expect(halt).toHaveTextContent('fixture: effect one');
    expect(within(halt).getByRole('button', { name: 'Disaster Management Policy §4.2' })).toBeInTheDocument();
    for (const card of cards()) expect(within(card).getByText('Proposed')).toBeInTheDocument();
  });

  it('approve all posts decision approve with every action id', async () => {
    const decide = renderInbox();
    fireEvent.click(screen.getByRole('button', { name: 'Approve 3 actions' }));
    const body: ApprovalDecision = { decision: 'approve', approved_action_ids: ['act_1', 'act_2', 'act_4'], note: null };
    await waitFor(() => { expect(decide).toHaveBeenCalledWith('appr_1', body); });
  });

  it('unchecking an action approves the rest as partial', async () => {
    const decide = renderInbox();
    fireEvent.click(screen.getByRole('checkbox', { name: 'Include Dispatch crew: Rescue Team 03 to Hillview' }));
    expect(approveButton()).toHaveTextContent('Approve 2 actions');
    fireEvent.click(approveButton());
    const body: ApprovalDecision = { decision: 'partial', approved_action_ids: ['act_1', 'act_4'], note: null };
    await waitFor(() => { expect(decide).toHaveBeenCalledWith('appr_1', body); });
  });

  it('approve is disabled when nothing is selected', () => {
    renderInbox();
    for (const box of screen.getAllByRole('checkbox')) fireEvent.click(box);
    expect(screen.getByRole('button', { name: 'Approve 0 actions' })).toBeDisabled();
  });

  it('reject posts the typed note', async () => {
    const decide = renderInbox();
    fireEvent.change(screen.getByRole('textbox', { name: 'Note' }), { target: { value: 'fixture: too early' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reject plan' }));
    const body: ApprovalDecision = { decision: 'reject', approved_action_ids: [], note: 'fixture: too early' };
    await waitFor(() => { expect(decide).toHaveBeenCalledWith('appr_1', body); });
  });

  it('disables the decision while it is being sent', async () => {
    renderInbox(vi.fn<Decide>(() => new Promise<Approval>(() => undefined)));
    fireEvent.click(screen.getByRole('button', { name: 'Approve 3 actions' }));
    expect(await screen.findByText('Sending decision…')).toBeInTheDocument();
    expect(approveButton()).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Reject plan' })).toBeDisabled();
    for (const box of screen.getAllByRole('checkbox')) expect(box).toBeDisabled();
  });

  it('shows an inline error when the decision fails and re-enables the buttons', async () => {
    renderInbox(vi.fn<Decide>(() => Promise.reject(new ApiError(500, null, 'boom'))));
    fireEvent.click(screen.getByRole('button', { name: 'Approve 3 actions' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Decision failed (500). Try again.');
    expect(approveButton()).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Reject plan' })).toBeEnabled();
  });

  it('waits for the backend to confirm after the decision is sent', async () => {
    renderInbox();
    fireEvent.click(screen.getByRole('button', { name: 'Approve 3 actions' }));
    expect(await screen.findByText('Decision sent. Waiting for confirmation.')).toBeInTheDocument();
    expect(approveButton()).toBeDisabled();
  });

  it('renders the raw tool name when the tool is unknown', () => {
    const unknown: Approval = {
      ...pendingApprovalFixture,
      id: 'appr_2',
      proposed_actions: [{
        action_id: 'act_9', tool: 'do_something_new', input: { foo: 'bar' }, rationale: 'fixture: new rationale',
        expected_effect: 'fixture: new effect', citation_ids: [], requires_approval: true,
      }],
    };
    seedLive([requested(unknown)]);
    renderInbox();
    const card = screen.getByRole('article', { name: 'do_something_new: bar' });
    expect(within(card).getByText('do_something_new')).toBeInTheDocument();
    expect(card).toHaveTextContent('fixture: new rationale');
  });

  it('shows auto-approved actions without a checkbox', () => {
    const withAuto: Approval = {
      ...pendingApprovalFixture,
      proposed_actions: [...pendingApprovalFixture.proposed_actions, {
        action_id: 'act_3', tool: 'schedule_inspection', input: { asset_id: 'd7' }, rationale: 'fixture: rationale three',
        expected_effect: 'fixture: effect three', citation_ids: [], requires_approval: false,
      }],
    };
    seedLive([requested(withAuto)]);
    renderInbox();
    const auto = screen.getByRole('article', { name: 'Schedule inspection: D-7 Kalinadi drain' });
    expect(within(auto).getByText('Auto-approved')).toBeInTheDocument();
    expect(within(auto).queryByRole('checkbox')).toBeNull();
    expect(screen.getByRole('button', { name: 'Approve 3 actions' })).toBeInTheDocument();
  });

  it('moves a decided approval under Decided with its status chip', () => {
    seedLive([decided(decidedApprovalFixture)]);
    renderInbox();
    expect(screen.getByRole('note')).toHaveTextContent('No approvals waiting. Proposed actions appear here when the agent asks for a decision.');
    const toggle = screen.getByRole('button', { name: /Decided/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    const section = screen.getByRole('region', { name: 'Landslide in Hillview' });
    expect(within(section).getByText('Partial')).toBeInTheDocument();
    expect(within(section).getByText('fixture: note')).toBeInTheDocument();
    expect(within(section).queryByRole('checkbox')).toBeNull();
    expect(within(section).getByText('Approved')).toBeInTheDocument();
    expect(within(section).getAllByText('Rejected')).toHaveLength(2);
    expect(within(section).queryByText('Auto-approved (demo)')).toBeNull();
  });

  it('labels a synthetic decision as auto-approved for the demo', () => {
    seedLive([decided({ ...decidedApprovalFixture, synthetic: true, decided_by: 'auto_approve' })]);
    renderInbox();
    fireEvent.click(screen.getByRole('button', { name: /Decided/ }));
    expect(screen.getByText('Auto-approved (demo)')).toBeInTheDocument();
  });

  it('Why? opens the why drawer for the action', () => {
    renderInbox();
    fireEvent.click(screen.getByRole('button', { name: 'Why? Halt construction' }));
    expect(useUiStore.getState().whyTarget).toEqual({ kind: 'action', actionId: 'act_1', incidentId: 'inc_1' });
  });

  it('shows the empty state when nothing is waiting', () => {
    seedLive([{ ...snapshotEventFixture, payload: { ...snapshotEventFixture.payload, approvals: [] } }], { snapshot: false });
    renderInbox();
    expect(screen.getByRole('note')).toHaveTextContent('No approvals waiting. Proposed actions appear here when the agent asks for a decision.');
    expect(screen.queryByRole('button', { name: /Decided/ })).toBeNull();
  });

  it('shows a loading state before the first snapshot', () => {
    seedLive([], { snapshot: false });
    renderInbox();
    expect(screen.getByLabelText('Waiting for city state')).toHaveAttribute('aria-busy', 'true');
  });
});
