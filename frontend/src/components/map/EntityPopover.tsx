import { KeyValue } from '@/components/ui/KeyValue';
import { SeverityChip } from '@/components/ui/SeverityChip';
import { IconClose } from '@/components/ui/icons';
import type { EntityDetails } from './entityDetails';

/** Non-modal details card for the selected map entity, pinned to the map's top-right corner. */
export function EntityPopover({ details, onClose }: { details: EntityDetails; onClose: () => void }) {
  return (
    <div role="dialog" aria-label={details.title}
      className="absolute top-2 right-2 z-10 w-64 max-h-[calc(100%-1rem)] overflow-auto bg-raised border border-line rounded-[3px] p-3">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <p className="text-[11px] text-ink-2">{details.kindLabel}</p>
          <h3 className="condensed text-[14px] font-medium leading-5 truncate">{details.title}</h3>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          {details.band && <SeverityChip band={details.band} />}
          <button type="button" aria-label="Close details" onClick={onClose}
            className="inline-flex items-center justify-center size-6 rounded-[3px] text-ink-2 hover:bg-panel hover:text-ink">
            <IconClose />
          </button>
        </div>
      </div>
      <KeyValue items={details.items} columns={2} />
    </div>
  );
}
