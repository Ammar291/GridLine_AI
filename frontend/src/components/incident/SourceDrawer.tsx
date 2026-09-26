import { useChunk } from '@/api/queries';
import { Drawer } from '@/components/ui/Drawer';
import { ErrorState } from '@/components/ui/ErrorState';
import { KeyValue } from '@/components/ui/KeyValue';
import { LoadingState } from '@/components/ui/LoadingState';
import { useLiveStore } from '@/live/liveStore';
import { useLiveAssets } from '@/live/useLiveAssets';
import { useUiStore } from '@/ui/uiStore';
import { citationKind } from './citations';
import { sourceFacts } from './sourceFacts';

/** The cited source behind a chip: a knowledge-base chunk from the API, or the live reading, state or event it names. */
export function SourceDrawer() {
  const citationId = useUiStore((s) => s.sourceCitationId);
  const closeSource = useUiStore((s) => s.closeSource);
  const city = useLiveStore((s) => s.city);
  const world = useLiveStore((s) => s.world);
  const zoneState = useLiveStore((s) => s.zoneState);
  const feed = useLiveStore((s) => s.feed);
  const assets = useLiveAssets();
  const isChunk = citationId !== null && citationKind(citationId) === 'chunk';
  const chunk = useChunk(isChunk ? citationId : null);

  if (citationId === null) return null;
  const facts = isChunk ? null : sourceFacts(citationId, { city, world, zoneState, assets, feed });

  return (
    <Drawer open stacked title="Source" onClose={closeSource}>
      <div className="flex flex-col gap-3">
        <p className="tnum text-[11px] text-ink-3 break-all">{citationId}</p>
        {isChunk && chunk.isPending && <LoadingState label="Loading source" />}
        {isChunk && chunk.isError && <ErrorState message="Source could not be loaded." onRetry={() => { void chunk.refetch(); }} />}
        {isChunk && chunk.data && (
          <>
            <h3 className="condensed text-[15px] font-medium">{chunk.data.document_title}</h3>
            <KeyValue columns={3} items={[
              { label: 'Section', value: `${chunk.data.section_id} ${chunk.data.section}` },
              { label: 'Kind', value: chunk.data.kind },
              { label: 'Category', value: chunk.data.category },
              { label: 'Document', value: chunk.data.document_id },
              { label: 'Source', value: chunk.data.source },
            ]} />
            <p className="whitespace-pre-wrap max-w-[80ch] text-ink leading-relaxed">{chunk.data.text}</p>
          </>
        )}
        {facts && (
          <>
            <h3 className="condensed text-[15px] font-medium">{facts.heading}</h3>
            <KeyValue columns={2} items={facts.items} />
            {facts.note !== null && <p className="text-ink-2">{facts.note}</p>}
          </>
        )}
      </div>
    </Drawer>
  );
}
