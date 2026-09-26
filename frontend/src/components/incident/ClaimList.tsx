import type { Citation, Claim } from '@/api/types';
import { CitationChip } from './CitationChip';
import { resolveCitation } from './citations';

/** Claims from a node output, each followed by the chips of the sources it cites. */
export function ClaimList({ claims, citations, label = 'Claims' }: { claims: Claim[]; citations: Citation[]; label?: string }) {
  if (claims.length === 0) return null;
  return (
    <ul aria-label={label} className="flex flex-col gap-1.5">
      {claims.map((claim, i) => (
        <li key={`${String(i)}:${claim.text}`} className="flex flex-wrap items-center gap-1.5 text-ink">
          <span className="mr-0.5">{claim.text}</span>
          {claim.citation_ids.map((id) => <CitationChip key={id} citation={resolveCitation(id, citations)} />)}
        </li>
      ))}
    </ul>
  );
}
