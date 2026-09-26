import { Button } from '@/components/ui/Button';
import { IconDrop, IconPending, IconSensor } from '@/components/ui/icons';
import { useUiStore } from '@/ui/uiStore';
import { citationKind, type CitationKind, type CitationRef } from './citations';

const glyphClass = 'size-3.5 shrink-0 text-ink-3';

function glyph(kind: CitationKind) {
  switch (kind) {
    case 'sensor': return <IconSensor className={glyphClass} />;
    case 'state': return <IconDrop className={glyphClass} />;
    case 'event': return <IconPending className={glyphClass} />;
    case 'chunk': return <span aria-hidden="true" className="text-ink-3">§</span>;
  }
}

/** A cited source. Clicking it opens the source drawer on that citation id. */
export function CitationChip({ citation }: { citation: CitationRef }) {
  const openSource = useUiStore((s) => s.openSource);
  const kind = 'kind' in citation ? citation.kind : citationKind(citation.id);
  const label = 'label' in citation && citation.label !== '' ? citation.label : citation.id;
  return (
    <Button size="sm" title={citation.id} className="max-w-[260px]" onClick={() => { openSource(citation.id); }}>
      {glyph(kind)}
      <span className="truncate">{label}</span>
    </Button>
  );
}
