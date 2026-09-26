import { fireEvent, render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import type { AgentRun, Incident } from '@/api/types';
import type { TelemetryPoint } from '@/live/types';
import { useUiStore } from '@/ui/uiStore';
import { cityFixture } from '@/test/fixtures/city';
import { incidentFixture, runFixture } from '@/test/fixtures/incident';
import { ReasoningTrace } from './ReasoningTrace';

function renderTrace(incident: Incident = incidentFixture, telemetry: TelemetryPoint[] = []) {
  return render(<ReasoningTrace incident={incident} telemetry={telemetry} city={cityFixture} />);
}
const region = (name: string) => screen.getByRole('region', { name });

describe('ReasoningTrace', () => {
  beforeEach(() => { useUiStore.getState().reset(); });

  it('node rail shows every node of the run with its status', () => {
    renderTrace();
    const rail = screen.getByRole('list', { name: 'Agent nodes' });
    expect(within(rail).getAllByRole('listitem')).toHaveLength(10);
    expect(within(rail).getByRole('listitem', { name: 'Assess threat: finished' })).toBeInTheDocument();
    expect(within(rail).getByRole('listitem', { name: 'Re-plan: finished' })).toBeInTheDocument();
  });

  it('node rail leaves re-plan out and marks unstarted nodes when the run is still going', () => {
    const run: AgentRun = { ...runFixture, status: 'running', steps: runFixture.steps.slice(0, 2) };
    renderTrace({ ...incidentFixture, runs: [run] });
    const rail = screen.getByRole('list', { name: 'Agent nodes' });
    expect(within(rail).getAllByRole('listitem')).toHaveLength(9);
    expect(within(rail).getByRole('listitem', { name: 'Retrieve evidence: finished' })).toBeInTheDocument();
    expect(within(rail).getByRole('listitem', { name: 'Assess threat: not started' })).toBeInTheDocument();
    expect(region('Why this threat?')).toHaveTextContent('Assess threat has not finished yet.');
  });

  it('renders the three reasoning sections', () => {
    renderTrace();
    expect(region('Why this threat?')).toBeInTheDocument();
    expect(region('What changed?')).toBeInTheDocument();
    expect(region('What evidence supports it?')).toBeInTheDocument();
  });

  it('why this threat shows the assessment summary and claims with citation chips', () => {
    renderTrace();
    const why = region('Why this threat?');
    expect(within(why).getByText('fixture: assessment summary')).toBeInTheDocument();
    const claims = within(within(why).getByRole('list', { name: 'Assessment claims' })).getAllByRole('listitem');
    expect(claims).toHaveLength(2);
    const [first, second] = claims as [HTMLElement, HTMLElement];
    expect(within(first).getByRole('button', { name: 'Disaster Management Policy §4.2' })).toBeInTheDocument();
    expect(within(second).getByRole('button', { name: 'RG-02 rain gauge' })).toBeInTheDocument();
  });

  it('what changed lists the trigger, band transition, reading deltas and cascade chain', () => {
    const t = (landslide: number, band: TelemetryPoint['band'], simTime: string): TelemetryPoint =>
      ({ simTime, rain: 40, saturation: 0.6, landslide, flood: 0.05, water: null, band });
    renderTrace(incidentFixture, [t(0.4, 'watch', '2026-07-14T10:00:00'), t(0.61, 'warning', '2026-07-14T10:10:00')]);
    const changed = region('What changed?');
    expect(changed).toHaveTextContent('Triggered by band change');
    expect(changed).toHaveTextContent('Watch → Warning');
    expect(within(changed).getByText('Landslide index', { exact: false })).toHaveTextContent('Landslide index 0.40 → 0.61');
    const chain = within(within(changed).getByRole('list', { name: 'Cascade chain' })).getAllByRole('listitem');
    expect(chain[0]).toHaveTextContent('fixture: hillview slope failure');
    expect(chain[0]).toHaveTextContent('fixture: d7 blocked, riverside floods');
  });

  it('evidence lists retrieved chunks and the run citations; a chip opens the source', () => {
    renderTrace();
    const evidence = region('What evidence supports it?');
    expect(within(evidence).getByText('Disaster Management Policy')).toBeInTheDocument();
    expect(within(evidence).getByText('Hillview Terrace permit')).toBeInTheDocument();
    expect(within(evidence).getByText('0.82')).toBeInTheDocument();
    const chip = screen.getAllByRole('button', { name: 'Disaster Management Policy §4.2' })[0];
    if (!chip) throw new Error('chip missing');
    fireEvent.click(chip);
    expect(useUiStore.getState().sourceCitationId).toBe('dmp-2024#s4.2');
  });

  it('shows the empty state when the incident has no run', () => {
    renderTrace({ ...incidentFixture, runs: [] });
    expect(screen.getByRole('note')).toHaveTextContent('No agent run yet for this incident. Reasoning appears here as each node finishes.');
  });

  it('flags an ungrounded step', () => {
    const run: AgentRun = { ...runFixture, steps: runFixture.steps.map((s) => (s.node === 'assess' ? { ...s, status: 'ungrounded' } : s)) };
    renderTrace({ ...incidentFixture, runs: [run] });
    expect(screen.getByRole('listitem', { name: 'Assess threat: ungrounded' })).toBeInTheDocument();
    expect(screen.getByText('Grounding check failed; confidence lowered.')).toBeInTheDocument();
  });

  it('each step row has a Why? button that targets the step', () => {
    renderTrace();
    fireEvent.click(screen.getByRole('button', { name: 'Why? Assess threat' }));
    expect(useUiStore.getState().whyTarget).toEqual({ kind: 'step', stepId: 'step_assess', runId: 'run_1', incidentId: 'inc_1' });
  });

  it('opens the latest run and collapses earlier ones', () => {
    const run2: AgentRun = { ...runFixture, id: 'run_2', trigger: 'replan', replan_reason: 'fixture: crew route blocked', started_at: '2026-09-26T10:40:00Z', steps: [] };
    renderTrace({ ...incidentFixture, runs: [runFixture, run2] });
    const latest = screen.getByRole('button', { name: /Run 2, triggered by replan/ });
    const earlier = screen.getByRole('button', { name: /Run 1, triggered by band change/ });
    expect(latest).toHaveAttribute('aria-expanded', 'true');
    expect(earlier).toHaveAttribute('aria-expanded', 'false');
    expect(region('What changed?')).toHaveTextContent('Re-plan reason: fixture: crew route blocked');
    fireEvent.click(earlier);
    expect(earlier).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getAllByRole('region', { name: 'What changed?' })).toHaveLength(2);
  });
});
