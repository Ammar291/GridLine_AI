// What the Why? drawer shows for an action or a step: read from the agent's recorded outputs, never inferred (spec 6.9).
import type { AgentRun, AgentStep, Claim, CitySnapshot, Incident, ProposedAction, RetrievedChunk, StepOutput } from '@/api/types';
import { resolveCitation, runCitations, type CitationRef } from '@/components/incident/citations';
import { latestRun, stepOutput } from '@/live/derive';
import { fmtSimTime, NODE_LABELS, statusLabel, toolVerb } from '@/live/format';
import type { WhyTarget } from '@/ui/uiStore';

export type WhySection = 'summary' | 'evidence' | 'cityState';

export interface WhyContent {
  title: string;
  /** The tool call behind an action target, so the drawer can name what it acts on; null for steps. */
  toolCall: { tool: string; input: Record<string, unknown> } | null;
  summary: string | null;
  expectedEffect: string | null;
  claims: Claim[];
  /** Chunks from the run's retrieve step; null until that node finishes. */
  evidence: RetrievedChunk[] | null;
  citations: CitationRef[];
  /** The run's observe snapshot: the city as the agent saw it. */
  cityState: CitySnapshot | null;
  /** For each section that has nothing to show, the sentence that says why. */
  missing: Partial<Record<WhySection, string>>;
}

const notFinished = (node: AgentStep['node']) => `${NODE_LABELS[node]} has not finished yet.`;
const plural = (n: number, word: string) => `${String(n)} ${word}${n === 1 ? '' : 's'}`;

function outputSummary(out: StepOutput): string {
  switch (out.node) {
    case 'observe': return `City state observed at ${fmtSimTime(out.sim_time)}.`;
    case 'retrieve': return `Retrieved ${plural(out.chunks.length, 'source')}.`;
    case 'assess': return out.summary;
    case 'predict': {
      const change = out.what_would_change_it.length > 0 ? `; would change if ${out.what_would_change_it.join('; ')}` : '';
      return `${statusLabel(out.probability_band)} probability within ${out.time_horizon}${change}.`;
    }
    case 'cascade': return `${out.chain.map((l) => `${l.cause} → ${l.effect}`).join('; ')}.`;
    case 'recommend': return `Proposed ${plural(out.actions.length, 'action')}: ${out.actions.map((a) => toolVerb(a.tool)).join(', ')}.`;
    case 'approval_gate':
      return `${plural(out.pending_action_ids.length, 'action')} sent for approval, ${String(out.auto_approved_action_ids.length)} auto-approved.`;
    case 'execute': return `Executed ${plural(out.action_ids.length, 'action')}.`;
    case 'verify': {
      const verified = out.per_action.filter((a) => a.status === 'verified').length;
      return `${statusLabel(out.status)}: ${String(verified)} of ${plural(out.per_action.length, 'action')} verified.`;
    }
    case 'replan': return out.reason;
  }
}

function outputClaims(out: StepOutput | null): Claim[] {
  return out && (out.node === 'assess' || out.node === 'predict' || out.node === 'cascade') ? out.claims : [];
}

/** Evidence and city state come from the run the target belongs to. */
function runContext(run: AgentRun | undefined): Pick<WhyContent, 'evidence' | 'cityState' | 'missing'> {
  const evidence = stepOutput(run, 'retrieve')?.chunks ?? null;
  const cityState = stepOutput(run, 'observe');
  const missing: WhyContent['missing'] = {};
  if (evidence === null) missing.evidence = notFinished('retrieve');
  if (cityState === null) missing.cityState = notFinished('observe');
  return { evidence, cityState, missing };
}

function stepContent(step: AgentStep, run: AgentRun): WhyContent {
  const ctx = runContext(run);
  const out = step.status === 'finished' || step.status === 'ungrounded' ? step.output : null;
  const missing = { ...ctx.missing };
  if (out === null) {
    missing.summary = step.status === 'failed' ? `${NODE_LABELS[step.node]} failed before recording an output.` : notFinished(step.node);
  }
  const claims = outputClaims(out);
  const ids = [...step.citations.map((c) => c.id), ...claims.flatMap((c) => c.citation_ids)];
  return {
    ...ctx, missing, claims, toolCall: null, expectedEffect: null,
    title: `Why: ${NODE_LABELS[step.node]}`,
    summary: out === null ? null : outputSummary(out),
    citations: [...new Set(ids)].map((id) => resolveCitation(id, step.citations)),
  };
}

const newestFirst = (runs: AgentRun[]) => [...runs].sort((a, b) => b.started_at.localeCompare(a.started_at));

interface FoundAction { proposal: ProposedAction | null; toolCall: NonNullable<WhyContent['toolCall']>; run: AgentRun | undefined }

/** The proposal behind an action id and the run that made it: the recommend output first, then approvals, then executed actions. */
function findAction(incident: Incident, actionId: string): FoundAction | null {
  for (const run of newestFirst(incident.runs)) {
    const proposal = stepOutput(run, 'recommend')?.actions.find((a) => a.action_id === actionId);
    if (proposal) return { proposal, toolCall: { tool: proposal.tool, input: proposal.input }, run };
  }
  const runById = (id: string) => incident.runs.find((r) => r.id === id);
  for (const approval of incident.approvals) {
    const proposal = approval.proposed_actions.find((a) => a.action_id === actionId);
    if (proposal) return { proposal, toolCall: { tool: proposal.tool, input: proposal.input }, run: runById(approval.run_id) ?? latestRun(incident) };
  }
  const executed = incident.actions.find((a) => a.id === actionId);
  if (!executed) return null;
  return { proposal: null, toolCall: { tool: executed.tool, input: executed.input }, run: runById(executed.run_id) ?? latestRun(incident) };
}

function actionContent(actionId: string, incident: Incident): WhyContent | null {
  const found = findAction(incident, actionId);
  if (!found) return null;
  const { proposal, toolCall, run } = found;
  const ctx = runContext(run);
  const recorded = runCitations(run);
  return {
    ...ctx,
    missing: proposal ? ctx.missing : { ...ctx.missing, summary: 'The recommendation behind this action is not in the live state.' },
    title: `Why: ${toolVerb(toolCall.tool)}`,
    toolCall,
    summary: proposal?.rationale ?? null,
    expectedEffect: proposal?.expected_effect ?? null,
    claims: [],
    citations: (proposal?.citation_ids ?? []).map((id) => resolveCitation(id, recorded)),
  };
}

/** Null when the target's incident, run, step or action is no longer in the live state. */
export function buildWhyContent(target: WhyTarget, incidents: Record<string, Incident>): WhyContent | null {
  const incident = incidents[target.incidentId];
  if (!incident) return null;
  if (target.kind === 'action') return actionContent(target.actionId, incident);
  const run = incident.runs.find((r) => r.id === target.runId);
  const step = run?.steps.find((s) => s.id === target.stepId);
  return run && step ? stepContent(step, run) : null;
}
