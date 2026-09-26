// Bodies of the last three steps: what the tools did, what re-reading the world showed, and the final state.
import type { WorkflowCompletionOutput, WorkflowExecutionOutput, WorkflowVerificationOutput } from '@/api/types';
import { statusLabel, toolVerb } from '@/live/format';
import { IconCheck, IconClose } from '@/components/ui/icons';
import { Tag } from './bits';

const RESULT_TONE = { executed: 'ok', unchanged: 'muted', rejected: 'warn', failed: 'bad' } as const;

export function ExecuteBody({ out }: { out: WorkflowExecutionOutput }) {
  return (
    <ul className="flex flex-col gap-1">
      {out.results.map((r) => (
        <li key={r.action_id} className="flex items-baseline gap-1.5 text-[12px]">
          <Tag tone={RESULT_TONE[r.status]}>{statusLabel(r.status)}</Tag>
          <span className="font-medium shrink-0">{toolVerb(r.tool)}</span>
          <span className="min-w-0 text-ink-2">{r.message}</span>
        </li>
      ))}
    </ul>
  );
}

const VERIFY_TONE = { verified: 'ok', partially_verified: 'warn', failed: 'bad' } as const;

export function VerifyBody({ out }: { out: WorkflowVerificationOutput }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p><Tag tone={VERIFY_TONE[out.status]}>{statusLabel(out.status)}</Tag></p>
      {out.per_action.map((a) => (
        <div key={a.action_id} className="flex flex-col gap-0.5">
          <p className="flex items-baseline gap-1.5 text-[12px]">
            <span className="font-medium">{toolVerb(a.tool)}</span>
            <Tag tone={a.status === 'verified' ? 'ok' : 'bad'}>{statusLabel(a.status)}</Tag>
          </p>
          <ul className="flex flex-col gap-0.5 pl-2">
            {a.checks.map((c) => (
              <li key={c.name} className="flex items-start gap-1.5 text-[12px] text-ink-2">
                {c.passed
                  ? <IconCheck className="size-3.5 shrink-0 text-ok-text mt-0.5" title="Passed" />
                  : <IconClose className="size-3.5 shrink-0 text-band-critical-text mt-0.5" title="Failed" />}
                <span className="min-w-0">{`${c.name}: expected ${c.expected}, observed ${c.observed}`}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

const OUTCOME_TONE = { completed: 'ok', completed_with_failures: 'warn', rejected: 'bad' } as const;
const fieldText = (v: unknown): string => (typeof v === 'string' ? v : JSON.stringify(v));

export function CompleteBody({ out }: { out: WorkflowCompletionOutput }) {
  return (
    <div className="flex flex-col gap-1.5">
      <p><Tag tone={OUTCOME_TONE[out.outcome]}>{statusLabel(out.outcome)}</Tag></p>
      {out.entities.length > 0 && (
        <ul className="flex flex-col gap-1">
          {out.entities.map((e) => (
            <li key={`${e.kind}:${e.id}`} className="text-[12px]">
              <span className="font-medium tnum">{e.id}</span>{' '}
              <span className="text-ink-2">{`${e.name} (${e.kind})`}</span>
              <span className="block text-ink-2 tnum">
                {Object.entries(e.fields).map(([k, v]) => `${k}: ${fieldText(v)}`).join(', ')}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
