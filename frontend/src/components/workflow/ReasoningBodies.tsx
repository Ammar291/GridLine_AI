// Bodies of the model's steps: the reasoning, the threat assessment and the action plan.
import type { WorkflowAssessmentOutput, WorkflowPlanOutput, WorkflowReasoningOutput } from '@/api/types';
import { fmtPct, statusLabel } from '@/live/format';
import { Cites, Meta, Tag } from './bits';
import { fmtMs } from './labels';

function providerText(out: WorkflowReasoningOutput | WorkflowPlanOutput): string {
  const who = out.provider === 'ollama' ? `ollama ${out.model ?? ''}`.trim() : 'mock reasoner';
  return `${who}, ${fmtMs(out.duration_ms)}${out.fallback_reason ? ` (Ollama unavailable: ${out.fallback_reason})` : ''}`;
}

export function ReasonBody({ out }: { out: WorkflowReasoningOutput }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p>{out.summary}</p>
      <ul className="flex flex-col gap-1">
        {out.claims.map((c, i) => (
          <li key={i} className="text-[12px] text-ink-2">
            {c.text}{' '}<Cites ids={c.citation_ids} />
          </li>
        ))}
      </ul>
      <Meta>{providerText(out)}</Meta>
    </div>
  );
}

const BAND_CLASSES: Record<WorkflowAssessmentOutput['band'], string> = {
  normal: 'bg-band-normal text-white',
  watch: 'bg-band-watch text-page',
  warning: 'bg-band-warning text-page',
  critical: 'bg-band-critical text-white',
};

export function AssessBody({ out }: { out: WorkflowAssessmentOutput }) {
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <span data-band={out.band} className={`condensed rounded-[3px] px-2.5 text-[16px] font-semibold leading-8 ${BAND_CLASSES[out.band]}`}>
          {`${statusLabel(out.hazard)} risk: ${out.band.toUpperCase()}`}
        </span>
        <span className="text-[13px] tnum">{`${fmtPct(out.confidence)} confidence`}</span>
        {out.grounded ? <Tag tone="ok">Grounded</Tag> : <Tag tone="bad">Ungrounded</Tag>}
      </div>
      <Meta>
        {`${String(out.cited_count)} citations checked`}
        {out.ungrounded_ids.length > 0 && `, rejected: ${out.ungrounded_ids.join(', ')}`}
        {out.affected_zone_ids.length > 0 && `. Affected zones: ${out.affected_zone_ids.join(', ')}`}
      </Meta>
    </div>
  );
}

export function PlanBody({ out }: { out: WorkflowPlanOutput }) {
  return (
    <div className="flex flex-col gap-1.5">
      <ol className="flex flex-col gap-1.5">
        {out.actions.map((a) => (
          <li key={a.action_id} className="flex flex-col gap-0.5 border-l-2 border-accent pl-2">
            <p className="flex flex-wrap items-baseline gap-1.5">
              <span className="font-medium">{a.label}</span>
              {a.requires_approval && <Tag tone="warn">Needs approval</Tag>}
            </p>
            <p className="text-[12px] text-ink-2">{a.rationale}</p>
            <p className="flex flex-wrap items-center gap-1.5 text-[11px] text-ink-3">
              <span className="tnum">{a.tool}</span>
              <Cites ids={a.citation_ids} />
            </p>
          </li>
        ))}
      </ol>
      <Meta>{`${String(out.actions.length)} of ${String(out.candidate_count)} candidates chosen by ${providerText(out)}`}</Meta>
    </div>
  );
}
