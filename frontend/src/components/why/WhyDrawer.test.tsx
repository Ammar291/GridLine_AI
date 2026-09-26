import { act, fireEvent, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { AgentRun } from '@/api/types';
import { SourceDrawer } from '@/components/incident/SourceDrawer';
import { useLiveStore } from '@/live/liveStore';
import { useUiStore, type WhyTarget } from '@/ui/uiStore';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';
import { incidentFixture, runFixture } from '@/test/fixtures/incident';
import { renderWithProviders } from '@/test/renderWithProviders';
import { seedLive } from '@/test/seedStores';
import { WhyDrawer } from './WhyDrawer';

const region = (name: string) => within(screen.getByRole('dialog', { name: /^Why/ })).getByRole('region', { name });
const open = (target: WhyTarget) => {
  act(() => { useUiStore.getState().openWhy(target); });
};

describe('WhyDrawer', () => {
  beforeEach(() => { seedLive(); });

  it('renders nothing until a Why? target is chosen', () => {
    renderWithProviders(<WhyDrawer />);
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('explains an action with its reasoning, evidence, citations and the city state the agent saw', () => {
    renderWithProviders(<WhyDrawer />);
    open({ kind: 'action', actionId: 'act_1', incidentId: 'inc_1' });
    const dialog = screen.getByRole('dialog', { name: 'Why: Halt construction' });
    expect(dialog).toHaveTextContent('Hillview Terrace Phase 2');
    expect(dialog).toHaveTextContent('Landslide in Hillview');

    const summary = region('Reasoning summary');
    expect(summary).toHaveTextContent('fixture: rationale one');
    expect(summary).toHaveTextContent('Expected effect');
    expect(summary).toHaveTextContent('fixture: effect one');

    const evidence = region('Retrieved evidence');
    expect(within(evidence).getByRole('button', { name: 'Disaster Management Policy' })).toBeInTheDocument();
    expect(within(evidence).getByRole('button', { name: 'Hillview Terrace permit' })).toBeInTheDocument();

    expect(within(region('Citations')).getByRole('button', { name: /Disaster Management Policy §4.2/ })).toBeInTheDocument();

    const state = region('Relevant city state');
    const value = (label: string) => within(state).getByText(label, { selector: 'dt' }).parentElement;
    expect(value('Saturation')).toHaveTextContent('71%');
    expect(value('Landslide index')).toHaveTextContent('0.61');
    expect(value('Flood index')).toHaveTextContent('0.05');
    expect(value('Excavation depth')).toHaveTextContent('3.5 of 6 m');
    expect(value('Channel capacity')).toHaveTextContent('8.5 of 12 m³/s');
    expect(within(state).getByRole('list', { name: 'Crews' })).toHaveTextContent('Rescue Team 03: Available in Market Ward');
    expect(state).toHaveTextContent('Observed at 10:30');
  });

  it('opens the source when a citation chip is clicked, stacked above the Why drawer', () => {
    renderWithProviders(<><WhyDrawer /><SourceDrawer /></>);
    open({ kind: 'action', actionId: 'act_1', incidentId: 'inc_1' });
    fireEvent.click(within(region('Citations')).getByRole('button', { name: /Disaster Management Policy §4.2/ }));
    expect(useUiStore.getState().sourceCitationId).toBe('dmp-2024#s4.2');
    expect(screen.getByRole('dialog', { name: 'Source' })).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(useUiStore.getState().sourceCitationId).toBeNull();
    expect(useUiStore.getState().whyTarget).not.toBeNull();
  });

  it('explains a step from its node output', () => {
    renderWithProviders(<WhyDrawer />);
    open({ kind: 'step', stepId: 'step_assess', runId: 'run_1', incidentId: 'inc_1' });
    screen.getByRole('dialog', { name: 'Why: Assess threat' });
    const summary = region('Reasoning summary');
    expect(summary).toHaveTextContent('fixture: assessment summary');
    expect(within(summary).getByRole('list', { name: 'Claims' })).toHaveTextContent('fixture: claim one');
    expect(summary).not.toHaveTextContent('Expected effect');
  });

  it('says which node has not finished when a section has nothing yet', () => {
    const run: AgentRun = { ...runFixture, steps: runFixture.steps.filter((s) => s.node !== 'observe' && s.node !== 'retrieve') };
    const opened = { ...eventsFixture['incident.opened'], payload: { ...incidentFixture, runs: [run] } };
    seedLive([snapshotEventFixture, opened], { snapshot: false });
    renderWithProviders(<WhyDrawer />);
    open({ kind: 'step', stepId: 'step_assess', runId: 'run_1', incidentId: 'inc_1' });
    expect(region('Retrieved evidence')).toHaveTextContent('Retrieve evidence has not finished yet.');
    expect(region('Relevant city state')).toHaveTextContent('Observe has not finished yet.');
  });

  it('says so when the target has left the live state', () => {
    renderWithProviders(<WhyDrawer />);
    open({ kind: 'action', actionId: 'act_99', incidentId: 'inc_1' });
    expect(screen.getByRole('dialog', { name: 'Why?' })).toHaveTextContent('This item is no longer in the live state.');
  });

  it('follows live updates to the run while open', () => {
    renderWithProviders(<WhyDrawer />);
    open({ kind: 'step', stepId: 'step_r2_assess', runId: 'run_2', incidentId: 'inc_1' });
    expect(screen.getByRole('dialog', { name: 'Why?' })).toBeInTheDocument();
    act(() => {
      useLiveStore.getState().dispatch(eventsFixture['agent.run.started']);
      useLiveStore.getState().dispatch(eventsFixture['agent.node.finished']);
    });
    expect(region('Reasoning summary')).toHaveTextContent('fixture: second assessment summary');
  });

  it('closes on Escape and on the Close button, and takes focus while open', () => {
    renderWithProviders(<WhyDrawer />);
    open({ kind: 'action', actionId: 'act_1', incidentId: 'inc_1' });
    expect(screen.getByRole('dialog')).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(useUiStore.getState().whyTarget).toBeNull();
    expect(screen.queryByRole('dialog')).toBeNull();

    open({ kind: 'action', actionId: 'act_1', incidentId: 'inc_1' });
    fireEvent.click(screen.getByRole('button', { name: 'Close' }));
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});
