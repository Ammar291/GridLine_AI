import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { Action, Event } from '@/api/types';
import { useLiveStore } from '@/live/liveStore';
import { useUiStore } from '@/ui/uiStore';
import { executedActionFixture, failedActionFixture, pendingActionFixture } from '@/test/fixtures/action';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';
import { seedLive } from '@/test/seedStores';
import { ActionsLog } from './ActionsLog';
import { StateTransition } from './StateTransition';
import { VerificationBadge } from './VerificationBadge';
import { verificationState, type VerificationState } from './verification';

function executed(action: Action): Event {
  return { ...eventsFixture['action.executed'], event_id: `evt_exec_${action.id}`, payload: action };
}
const row = (name: string) => screen.getByRole('article', { name });
const badge = (el: HTMLElement) => within(el).getByTestId('verification-badge');

describe('ActionsLog', () => {
  beforeEach(() => { seedLive(); });

  it('shows the verb, target, state transition and verification of an executed action', () => {
    render(<ActionsLog />);
    expect(screen.getByRole('heading', { name: /Actions/ })).toHaveTextContent('1');
    const r = row('Dispatch crew: Rescue Team 03');
    expect(within(r).getByText('Dispatch crew')).toBeInTheDocument();
    const transition = within(r).getByLabelText('Rescue Team 03 changed from available to dispatched');
    expect(transition).toHaveTextContent('Available → Dispatched');
    expect(badge(r)).toHaveTextContent('Verified');
    expect(badge(r)).toHaveAttribute('data-state', 'verified');
    expect(badge(r).querySelector('svg')).not.toBeNull();
    expect(within(r).getByText('Expected', { selector: 'dt' }).parentElement).toHaveTextContent('fixture: crew at hillview');
    expect(within(r).getByText('Observed', { selector: 'dt' }).parentElement).toHaveTextContent('fixture: crew at hillview');
    expect(r).toHaveTextContent('10:40');
  });

  it('lists the newest action first', () => {
    seedLive([executed(failedActionFixture)]);
    render(<ActionsLog />);
    expect(screen.getAllByRole('article').map((a) => a.getAttribute('aria-label'))).toEqual([
      'Close road: Kalinadi Bridge B-04',
      'Dispatch crew: Rescue Team 03',
    ]);
  });

  it('shows a failed verification with its failures', () => {
    seedLive([executed(failedActionFixture)]);
    render(<ActionsLog />);
    const r = row('Close road: Kalinadi Bridge B-04');
    expect(badge(r)).toHaveTextContent('Failed');
    expect(r).toHaveTextContent('fixture: crew C-2 route blocked');
  });

  it('shows re-planning when a replan event references the run, and keeps the failures visible', () => {
    seedLive([executed(failedActionFixture), eventsFixture['replan.triggered']]);
    render(<ActionsLog />);
    const r = row('Close road: Kalinadi Bridge B-04');
    expect(badge(r)).toHaveTextContent('Re-planning');
    expect(r).toHaveTextContent('fixture: crew C-2 route blocked');
    expect(badge(row('Dispatch crew: Rescue Team 03'))).toHaveTextContent('Verified');
  });

  it('shows verifying while the check is pending, with sim minutes since execution', () => {
    seedLive([executed(pendingActionFixture)]);
    useLiveStore.setState({ sim: { ...useLiveStore.getState().sim, simTime: '2026-07-14T10:50:00' } });
    render(<ActionsLog />);
    const pending = screen.getAllByRole('article').find((a) => within(a).queryByTestId('verification-badge')?.dataset.state === 'pending');
    if (!pending) throw new Error('pending row missing');
    expect(badge(pending)).toHaveTextContent('Verifying…');
    expect(badge(pending)).toHaveTextContent('10 min');
  });

  it('renders the raw tool name and input target for an unknown tool', () => {
    const unknown: Action = { ...executedActionFixture, id: 'act_9', tool: 'do_something_new', input: { foo: 'bar' }, state_changes: [], verification: null };
    seedLive([executed(unknown)]);
    render(<ActionsLog />);
    const r = row('do_something_new: bar');
    expect(within(r).getByText('do_something_new')).toBeInTheDocument();
    expect(r).toHaveTextContent('No state change recorded.');
    expect(badge(r)).toHaveTextContent('Verifying…');
  });

  it('Why? opens the why drawer for the action', () => {
    render(<ActionsLog />);
    fireEvent.click(screen.getByRole('button', { name: 'Why? Dispatch crew' }));
    expect(useUiStore.getState().whyTarget).toEqual({ kind: 'action', actionId: 'act_2', incidentId: 'inc_1' });
  });

  it('shows the empty state when no action has run', () => {
    seedLive([snapshotEventFixture], { snapshot: false });
    render(<ActionsLog />);
    expect(screen.getByRole('note')).toHaveTextContent('No actions yet. Approved actions appear here as they execute.');
  });

  it('shows a loading state before the first snapshot', () => {
    seedLive([], { snapshot: false });
    render(<ActionsLog />);
    expect(screen.getByLabelText('Waiting for city state')).toHaveAttribute('aria-busy', 'true');
  });
});

describe('StateTransition', () => {
  it('names the field when it is not the status', () => {
    render(<ul><StateTransition change={{ entity_type: 'channel', entity_id: 'd7', entity_name: 'D-7 Kalinadi drain', field: 'current_capacity_m3s', from: '8.5', to: '12' }} /></ul>);
    const item = screen.getByLabelText('D-7 Kalinadi drain current capacity m3s changed from 8.5 to 12');
    expect(item).toHaveTextContent('8.5 → 12');
  });
});

describe('VerificationBadge', () => {
  const cases: [VerificationState, string][] = [
    ['verified', 'Verified'],
    ['partially_verified', 'Partially verified'],
    ['failed', 'Failed'],
    ['pending', 'Verifying…'],
    ['replanning', 'Re-planning'],
  ];
  it.each(cases)('%s renders an icon and the text %s', (state, text) => {
    render(<VerificationBadge state={state} />);
    const el = screen.getByTestId('verification-badge');
    expect(el).toHaveTextContent(text);
    expect(el.querySelector('svg')).not.toBeNull();
  });

  it('verificationState reads the verification, the action status and the replan set', () => {
    const none = new Set<string>();
    expect(verificationState(executedActionFixture, none)).toBe('verified');
    expect(verificationState(executedActionFixture, new Set(['run_1']))).toBe('verified');
    expect(verificationState(failedActionFixture, none)).toBe('failed');
    expect(verificationState(failedActionFixture, new Set(['run_1']))).toBe('replanning');
    expect(verificationState(pendingActionFixture, none)).toBe('pending');
    expect(verificationState({ ...executedActionFixture, verification: null, status: 'executing' }, none)).toBe('pending');
    expect(verificationState({ ...executedActionFixture, verification: null, status: 'failed' }, none)).toBe('failed');
  });
});
