import type { RetrievedChunk } from '@/api/types';
import { fmtIndex } from '@/live/format';
import { useUiStore } from '@/ui/uiStore';

/** Chunks the retrieve node returned; each title opens its source. */
export function EvidenceTable({ chunks }: { chunks: RetrievedChunk[] }) {
  const openSource = useUiStore((s) => s.openSource);
  if (chunks.length === 0) return <p className="text-ink-3">Retrieval returned no sources.</p>;
  return (
    <table className="w-full text-left text-[12px]">
      <thead className="text-[11px] text-ink-2">
        <tr><th className="font-normal py-0.5">Source</th><th className="font-normal">Section</th><th className="font-normal">Kind</th><th className="font-normal text-right">Score</th></tr>
      </thead>
      <tbody>
        {chunks.map((c) => (
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
  );
}
