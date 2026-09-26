import { describe, expect, it } from 'vitest';
import type { AgentRun, Incident } from '@/api/types';
import { pendingApprovalFixture } from '@/test/fixtures/approval';
import { executedActionFixture, failedActionFixture } from '@/test/fixtures/action';
import { incidentFixture, runFixture } from '@/test/fixtures/incident';
import { buildWhyContent } from './whyContent';

const incidents = (i: Incident = incidentFixture): Record<string, Incident> => ({ [i.id]: i });
const withRun = (run: AgentRun, extra: Partial<Incident> = {}): Incident => ({ ...incidentFixture, runs: [run], ...extra });
const withoutNodes = (...nodes: string[]): AgentRun => ({ ...runFixture, steps: runFixture.steps.filter((s) => !nodes.includes(s.node)) });

describe('buildWhyContent', () => {
  it('explains a proposed action from the run that recommended it', () => {
    const c = buildWhyContent({ kind: 'action', actionId: 'act_1', incidentId: 'inc_1' }, incidents());
    expect(c?.title).toBe('Why: Halt construction');
    expect(c?.toolCall).toEqual({ tool: 'halt_construction', input: { project_id: 'ht_phase2' } });
    expect(c?.summary).toBe('fixture: rationale one');
    expect(c?.expectedEffect).toBe('fixture: effect one');
    expect(c?.evidence?.map((e) => e.doc_title)).toEqual(['Disaster Management Policy', 'Hillview Terrace permit']);
    expect(c?.citations).toEqual([{ id: 'dmp-2024#s4.2', kind: 'chunk', label: 'Disaster Management Policy §4.2' }]);
    expect(c?.cityState?.zone_id).toBe('hillview');
    expect(c?.missing).toEqual({});
  });

  it('keeps an uncited id as a bare citation so the chip still shows it', () => {
    const run = withoutNodes('assess'); // the assess step recorded the citation labels
    const c = buildWhyContent({ kind: 'action', actionId: 'act_2', incidentId: 'inc_1' }, incidents(withRun(run)));
    expect(c?.citations).toEqual([{ id: 'sensor:RG-02@2026-07-14T10:30:00' }]);
  });

  it('finds a proposal that only the approval carries', () => {
    const run = withoutNodes('recommend');
    const c = buildWhyContent({ kind: 'action', actionId: 'act_4', incidentId: 'inc_1' }, incidents(withRun(run, { approvals: [pendingApprovalFixture] })));
    expect(c?.title).toBe('Why: Open shelter');
    expect(c?.summary).toBe('fixture: rationale four');
  });

  it('names an executed action whose recommendation is not in the live state', () => {
    const c = buildWhyContent({ kind: 'action', actionId: 'act_5', incidentId: 'inc_1' }, incidents({ ...incidentFixture, actions: [failedActionFixture] }));
    expect(c?.title).toBe('Why: Close road');
    expect(c?.summary).toBeNull();
    expect(c?.missing.summary).toBe('The recommendation behind this action is not in the live state.');
  });

  it('uses the run that proposed an executed action', () => {
    const c = buildWhyContent({ kind: 'action', actionId: executedActionFixture.id, incidentId: 'inc_1' }, incidents());
    expect(c?.title).toBe('Why: Dispatch crew');
    expect(c?.summary).toBe('fixture: rationale two');
  });

  it('explains a step from its own output and claims', () => {
    const c = buildWhyContent({ kind: 'step', stepId: 'step_assess', runId: 'run_1', incidentId: 'inc_1' }, incidents());
    expect(c?.title).toBe('Why: Assess threat');
    expect(c?.toolCall).toBeNull();
    expect(c?.summary).toBe('fixture: assessment summary');
    expect(c?.expectedEffect).toBeNull();
    expect(c?.claims.map((cl) => cl.text)).toEqual(['fixture: claim one', 'fixture: claim two']);
    expect(c?.citations.map((ct) => ct.id)).toEqual(['dmp-2024#s4.2', 'sensor:RG-02@2026-07-14T10:30:00']);
  });

  it('summarises other node outputs as plain statements of what they hold', () => {
    const step = (id: string) => buildWhyContent({ kind: 'step', stepId: id, runId: 'run_1', incidentId: 'inc_1' }, incidents())?.summary;
    expect(step('step_observe')).toBe('City state observed at 10:30.');
    expect(step('step_retrieve')).toBe('Retrieved 2 sources.');
    expect(step('step_predict')).toBe('High probability within fixture: 6 to 12 hours; would change if fixture: rain stops.');
    expect(step('step_cascade')).toBe('fixture: hillview slope failure → fixture: d7 blocked, riverside floods.');
    expect(step('step_recommend')).toBe('Proposed 3 actions: Halt construction, Dispatch crew, Schedule inspection.');
    expect(step('step_approval_gate')).toBe('2 actions sent for approval, 1 auto-approved.');
    expect(step('step_execute')).toBe('Executed 1 action.');
    expect(step('step_verify')).toBe('Verified: 1 of 1 action verified.');
    expect(step('step_replan')).toBe('fixture: none');
  });

  it('names the node that has not finished for each empty section', () => {
    const run = withoutNodes('observe', 'retrieve');
    const c = buildWhyContent({ kind: 'step', stepId: 'step_assess', runId: 'run_1', incidentId: 'inc_1' }, incidents(withRun(run)));
    expect(c?.evidence).toBeNull();
    expect(c?.cityState).toBeNull();
    expect(c?.missing).toEqual({
      evidence: 'Retrieve evidence has not finished yet.',
      cityState: 'Observe has not finished yet.',
    });
  });

  it('says a running step has not finished and a failed step recorded nothing', () => {
    const running: AgentRun = {
      ...runFixture,
      steps: runFixture.steps.map((s) => (s.node === 'predict' ? { ...s, status: 'running' as const, output: null } : s.node === 'cascade' ? { ...s, status: 'failed' as const, output: null } : s)),
    };
    const at = (id: string) => buildWhyContent({ kind: 'step', stepId: id, runId: 'run_1', incidentId: 'inc_1' }, incidents(withRun(running)));
    expect(at('step_predict')?.missing.summary).toBe('Predict has not finished yet.');
    expect(at('step_cascade')?.missing.summary).toBe('Analyse cascade failed before recording an output.');
  });

  it('returns null when the target is no longer in the live state', () => {
    expect(buildWhyContent({ kind: 'step', stepId: 'step_assess', runId: 'run_9', incidentId: 'inc_1' }, incidents())).toBeNull();
    expect(buildWhyContent({ kind: 'action', actionId: 'act_1', incidentId: 'inc_9' }, incidents())).toBeNull();
    expect(buildWhyContent({ kind: 'action', actionId: 'act_99', incidentId: 'inc_1' }, incidents())).toBeNull();
  });
});
