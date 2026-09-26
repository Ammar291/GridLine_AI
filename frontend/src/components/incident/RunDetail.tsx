import { useMemo } from 'react';
import type { AgentRun, City, Incident, NodeName } from '@/api/types';
import { IconChevron } from '@/components/ui/icons';
import { stepOutput, whatChanged } from '@/live/derive';
import { fmtIndex, statusLabel } from '@/live/format';
import type { TelemetryPoint } from '@/live/types';
import { useUiStore } from '@/ui/uiStore';
import { CitationChip } from './CitationChip';
import { ClaimList } from './ClaimList';
import { runCitations } from './citations';
import { NodeRail } from './NodeRail';
import { NODE_LABELS } from './nodeLabels';
import { StepList } from './StepList';
import { TraceSection } from './TraceSection';

interface RunDetailProps { incident: Incident; run: AgentRun; telemetry: TelemetryPoint[]; city: City | null }

const notYet = (node: NodeName) => <p className="text-ink-3">{`${NODE_LABELS[node]} has not finished yet.`}</p>;

/** One run's trace: node rail, then why, what changed, what evidence, and the step timings. */
export function RunDetail({ incident, run, telemetry, city }: RunDetailProps) {
  const openSource = useUiStore((s) => s.openSource);
  const assess = stepOutput(run, 'assess');
  const predict = stepOutput(run, 'predict');
  const cascade = stepOutput(run, 'cascade');
  const retrieve = stepOutput(run, 'retrieve');
  const citations = useMemo(() => runCitations(run), [run]);
  const changed = useMemo(() => whatChanged(incident, run, telemetry, city), [incident, run, telemetry, city]);

  return (
    <>
      <NodeRail run={run} />
      <TraceSection title="Why this threat?">
        {assess ? (
          <>
            <p className="text-ink">{assess.summary}</p>
            <ClaimList claims={assess.claims} citations={citations} label="Assessment claims" />
          </>
        ) : notYet('assess')}
        {predict && (
          <>
            <p className="text-ink-2 mt-1">
              {`${statusLabel(predict.probability_band)} probability within ${predict.time_horizon}`}
              {predict.what_would_change_it.length > 0 && `; would change if ${predict.what_would_change_it.join('; ')}`}
            </p>
            <ClaimList claims={predict.claims} citations={citations} label="Prediction claims" />
          </>
        )}
      </TraceSection>
      <TraceSection title="What changed?">
        <ul className="flex flex-col gap-0.5 list-disc pl-4 marker:text-ink-3">
          <li>{`Triggered by ${changed.trigger.replace(/_/g, ' ')}`}</li>
          {changed.replanReason !== null && <li>{`Re-plan reason: ${changed.replanReason}`}</li>}
          {changed.bandTransitions.map((t, i) => <li key={`${String(i)}:${t}`}>{`Band ${t}`}</li>)}
          {changed.readingDeltas.map((d) => <li key={d.label} className="tnum">{`${d.label} ${d.from} → ${d.to}`}</li>)}
        </ul>
        {cascade && cascade.chain.length > 0 && (
          <ol aria-label="Cascade chain" className="flex flex-col gap-1">
            {cascade.chain.map((link, i) => (
              <li key={`${String(i)}:${link.cause}`} className="flex flex-wrap items-center gap-1.5">
                <span>{link.cause}</span>
                <IconChevron className="shrink-0 text-ink-3" title="leads to" />
                <span>{link.effect}</span>
              </li>
            ))}
          </ol>
        )}
      </TraceSection>
      <TraceSection title="What evidence supports it?">
        {retrieve ? (
          <table className="w-full text-left text-[12px]">
            <thead className="text-[11px] text-ink-2">
              <tr><th className="font-normal py-0.5">Source</th><th className="font-normal">Section</th><th className="font-normal">Kind</th><th className="font-normal text-right">Score</th></tr>
            </thead>
            <tbody>
              {retrieve.chunks.map((c) => (
                <tr key={c.id} className="border-t border-line">
                  <td className="py-1 pr-2">
                    <button type="button" title={c.id} onClick={() => { openSource(c.id); }} className="text-accent hover:text-accent-strong text-left">
                      {c.doc_title}
                    </button>
                  </td>
                  <td className="pr-2 tnum text-ink-2">{c.section}</td>
                  <td className="pr-2 text-ink-2">{c.kind}</td>
                  <td className="tnum text-right">{fmtIndex(c.score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : notYet('retrieve')}
        {citations.length > 0 && (
          <ul aria-label="Citations in this run" className="flex flex-wrap gap-1.5 mt-1">
            {citations.map((c) => <li key={c.id}><CitationChip citation={c} /></li>)}
          </ul>
        )}
      </TraceSection>
      <TraceSection title="Steps">
        <StepList run={run} />
      </TraceSection>
    </>
  );
}
