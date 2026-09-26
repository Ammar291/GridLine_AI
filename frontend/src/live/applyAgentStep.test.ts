import { describe, expect, it } from 'vitest';
import type { Event, WorkflowStep } from '@/api/types';
import { eventsFixture, snapshotEventFixture } from '@/test/fixtures/events';
import { doneSteps, RUN_ID, stepOf, waitingSteps, workflowRunFixture } from '@/test/fixtures/workflow';
import { agentRunFromSnapshot, applyAgentStep, runStatus } from './applyAgentStep';
import { applyEvents } from './applyEvent';
import { describeEvent } from './describeEvent';
import { initialLiveState } from './types';

const stepEvent = (payload: WorkflowStep): Event => ({ ...eventsFixture['agent.step'], payload });

describe('applyAgentStep', () => {
  it('upserts by node and keeps steps sorted by index whatever the arrival order', () => {
    let run = applyAgentStep(null, stepOf('retrieve'));
    run = applyAgentStep(run, stepOf('receive'));
    run = applyAgentStep(run, stepOf('observe'));
    expect(run.runId).toBe(RUN_ID);
    expect(run.steps.map((s) => s.node)).toEqual(['receive', 'observe', 'retrieve']);
  });

  it('replaces a running step with its done state', () => {
    let run = applyAgentStep(null, stepOf('receive'));
    run = applyAgentStep(run, stepOf('observe', { status: 'running', output: null, finished_at: null, duration_ms: null }));
    expect(run.steps.at(-1)?.status).toBe('running');
    run = applyAgentStep(run, stepOf('observe'));
    expect(run.steps).toHaveLength(2);
    expect(run.steps.at(-1)?.status).toBe('done');
    expect(run.steps.at(-1)?.output?.node).toBe('observe');
  });

  it('a step of a new run replaces the old run', () => {
    const old = doneSteps.reduce<ReturnType<typeof applyAgentStep> | null>((r, s) => applyAgentStep(r, s), null);
    const run = applyAgentStep(old, { ...stepOf('receive'), run_id: 'run_wf_2', status: 'running', output: null });
    expect(run.runId).toBe('run_wf_2');
    expect(run.steps).toHaveLength(1);
  });

  it('seeds from the snapshot agent_run and clears on a snapshot without one', () => {
    expect(agentRunFromSnapshot(null)).toBeNull();
    expect(agentRunFromSnapshot(undefined)).toBeNull();
    const reversed = { ...workflowRunFixture, steps: [...workflowRunFixture.steps].reverse() };
    const seeded = agentRunFromSnapshot(reversed);
    expect(seeded?.steps.map((s) => s.index)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);

    const withRun: Event = { ...snapshotEventFixture, payload: { ...snapshotEventFixture.payload, agent_run: reversed } };
    const s1 = applyEvents(initialLiveState('mock'), [withRun]);
    expect(s1.agentRun?.runId).toBe(RUN_ID);
    expect(s1.agentRun?.steps).toHaveLength(8);
    const s2 = applyEvents(s1, [{ ...snapshotEventFixture, payload: { ...snapshotEventFixture.payload, agent_run: null } }]);
    expect(s2.agentRun).toBeNull();
  });

  it('agent.step events reach the live state and the feed', () => {
    const s = applyEvents(initialLiveState('mock'), [snapshotEventFixture, stepEvent(stepOf('receive')), stepEvent(stepOf('assess'))]);
    expect(s.agentRun?.steps.map((x) => x.node)).toEqual(['receive', 'assess']);
    expect(s.feed.filter((e) => e.event_type === 'agent.step')).toHaveLength(2);
    expect(describeEvent(eventsFixture['agent.step'], null)).toBe('Agent: Threat assessment done');
  });
});

describe('runStatus', () => {
  it('mirrors the backend rule', () => {
    expect(runStatus([])).toBe('running');
    expect(runStatus(doneSteps.slice(0, 3))).toBe('running');
    expect(runStatus(waitingSteps)).toBe('waiting');
    expect(runStatus(doneSteps)).toBe('completed');
    const rejected = stepOf('complete', { output: { node: 'complete', outcome: 'rejected', entities: [] } });
    expect(runStatus([...doneSteps.slice(0, 10), rejected])).toBe('rejected');
    expect(runStatus([...waitingSteps, stepOf('execute', { status: 'failed', error: 'boom' })])).toBe('failed');
  });
});
