import { useMemo, type ReactNode } from 'react';
import type { City } from '@/api/types';
import { actionTargetName } from '@/components/approvals/actionTarget';
import { CitationChip } from '@/components/incident/CitationChip';
import { ClaimList } from '@/components/incident/ClaimList';
import { EvidenceTable } from '@/components/incident/EvidenceTable';
import { TraceSection } from '@/components/incident/TraceSection';
import { Drawer } from '@/components/ui/Drawer';
import { EmptyState } from '@/components/ui/EmptyState';
import { zoneName } from '@/live/derive';
import { statusLabel } from '@/live/format';
import { useLiveStore } from '@/live/liveStore';
import { useLiveAssets } from '@/live/useLiveAssets';
import type { LiveAssets } from '@/live/assets';
import { useUiStore } from '@/ui/uiStore';
import { CityStateFacts } from './CityStateFacts';
import { buildWhyContent, type WhyContent } from './whyContent';

const pending = (text: string) => <p className="text-ink-3">{text}</p>;

/** Why? for an action or an agent step: its reasoning, the evidence it drew on, its citations, and the city state it saw. */
export function WhyDrawer() {
  const target = useUiStore((s) => s.whyTarget);
  const closeWhy = useUiStore((s) => s.closeWhy);
  const incidents = useLiveStore((s) => s.incidents);
  const city = useLiveStore((s) => s.city);
  const assets = useLiveAssets();
  const content = useMemo(() => (target ? buildWhyContent(target, incidents) : null), [target, incidents]);

  if (!target) return null;
  const incident = incidents[target.incidentId];
  const context = [
    content?.toolCall ? actionTargetName(content.toolCall.tool, content.toolCall.input, assets, city) : '',
    incident ? `${statusLabel(incident.hazard)} in ${zoneName(city, incident.zone_id)}` : '',
  ].filter((s) => s !== '');

  return (
    <Drawer open title={content?.title ?? 'Why?'} onClose={closeWhy} width={520}>
      {content ? (
        <div className="flex flex-col gap-4">
          {context.length > 0 && (
            <div>
              {context.map((line, i) => <p key={line} className={i === 0 ? 'text-ink' : 'text-ink-2 text-[12px]'}>{line}</p>)}
            </div>
          )}
          <WhySections content={content} city={city} roads={assets.roads} />
        </div>
      ) : (
        <EmptyState title="This item is no longer in the live state." />
      )}
    </Drawer>
  );
}

interface WhySectionsProps { content: WhyContent; city: City | null; roads: LiveAssets['roads'] }

function WhySections({ content, city, roads }: WhySectionsProps) {
  const { missing } = content;
  const recorded = content.citations.flatMap((c) => ('kind' in c ? [c] : []));
  let summary: ReactNode = missing.summary !== undefined ? pending(missing.summary) : null;
  if (content.summary !== null) {
    summary = (
      <>
        <p className="text-ink leading-relaxed">{content.summary}</p>
        {content.expectedEffect !== null && (
          <p className="text-ink-2"><span className="text-ink-3">Expected effect </span>{content.expectedEffect}</p>
        )}
        <ClaimList claims={content.claims} citations={recorded} />
      </>
    );
  }
  return (
    <>
      <TraceSection title="Reasoning summary">{summary}</TraceSection>
      <TraceSection title="Retrieved evidence">
        {content.evidence ? <EvidenceTable chunks={content.evidence} /> : pending(missing.evidence ?? '')}
      </TraceSection>
      <TraceSection title="Citations">
        {content.citations.length === 0 ? pending('No sources were cited.') : (
          <ul aria-label="Citations" className="flex flex-wrap gap-1.5">
            {content.citations.map((c) => <li key={c.id}><CitationChip citation={c} /></li>)}
          </ul>
        )}
      </TraceSection>
      <TraceSection title="Relevant city state">
        {content.cityState ? <CityStateFacts snapshot={content.cityState} city={city} roads={roads} /> : pending(missing.cityState ?? '')}
      </TraceSection>
    </>
  );
}
