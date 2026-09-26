// Bodies of the first four steps: the trigger, the situation, the knowledge-graph paths and the retrieved evidence.
import { Fragment } from 'react';
import type {
  WorkflowEntity, WorkflowEvidenceOutput, WorkflowGraphOutput, WorkflowObserveOutput, WorkflowReceiveOutput,
} from '@/api/types';
import { statusLabel } from '@/live/format';
import { Cites, Meta, Tag } from './bits';

export function ReceiveBody({ out }: { out: WorkflowReceiveOutput }) {
  return (
    <div className="flex flex-col gap-1">
      <p>{out.description}</p>
      <Meta>
        {`${statusLabel(out.failure_kind)} at ${out.asset.id} ${out.asset.name}, ${out.zone_name} (${out.zone_id}), sim ${out.sim_time.slice(11, 16)}`}
      </Meta>
      <Cites ids={[out.citation_id]} />
    </div>
  );
}

export function ObserveBody({ out }: { out: WorkflowObserveOutput }) {
  return (
    <div className="flex flex-col gap-1">
      <p>{out.headline}</p>
      <ul className="flex flex-col gap-0.5">
        {out.signals.map((s) => (
          <li key={s.id} className="flex items-baseline gap-1.5 text-[12px] text-ink-2">
            <Tag tone={s.severity === 'critical' || s.severity === 'high' ? 'bad' : 'muted'}>{s.severity}</Tag>
            <span className="min-w-0">{s.summary}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function EntityChip({ e }: { e: WorkflowEntity }) {
  return (
    <span title={e.table} className="inline-flex items-baseline gap-1 rounded-[3px] bg-raised px-1.5 text-[12px] leading-5">
      <span className="font-medium tnum">{e.id}</span>
      <span className="text-ink-2">{e.name}</span>
    </span>
  );
}

export function GraphBody({ out }: { out: WorkflowGraphOutput }) {
  return (
    <div className="flex flex-col gap-1.5">
      {out.paths.map((path, i) => (
        <p key={i} className="flex flex-wrap items-center gap-1" data-testid="graph-path">
          {path.nodes.map((n, j) => (
            <Fragment key={`${n.id}-${String(j)}`}>
              {j > 0 && (
                <span title={path.citation_ids[j - 1]} className="text-[11px] text-accent">{`→${path.relations[j - 1] ?? ''}→`}</span>
              )}
              <EntityChip e={n} />
            </Fragment>
          ))}
        </p>
      ))}
      <Meta>{`${String(out.entity_count)} entities, ${String(out.edge_count)} edges from ${out.start.id}`}</Meta>
    </div>
  );
}

export function EvidenceBody({ out }: { out: WorkflowEvidenceOutput }) {
  return (
    <ul className="flex flex-col gap-1">
      {out.chunks.map((c) => (
        <li key={c.chunk_id} className="flex flex-wrap items-baseline gap-x-1.5 text-[12px]">
          <span className="font-medium">{c.document_title}</span>
          <span className="text-ink-2">{c.section}</span>
          <Cites ids={[c.chunk_id]} />
          <span className="text-[11px] text-ink-3 tnum">{`similarity ${c.similarity.toFixed(2)}`}</span>
        </li>
      ))}
    </ul>
  );
}
