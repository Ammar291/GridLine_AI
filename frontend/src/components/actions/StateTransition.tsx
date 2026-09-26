import type { StateChange } from '@/api/types';
import { statusLabel } from '@/live/format';

const spoken = (s: string) => s.replace(/_/g, ' ');

/** `Rescue Team 03  Available → Dispatched`; the field is named when it is not the status. */
export function StateTransition({ change }: { change: StateChange }) {
  const field = change.field === 'status' ? '' : ` ${spoken(change.field)}`;
  return (
    <li aria-label={`${change.entity_name}${field} changed from ${spoken(change.from)} to ${spoken(change.to)}`}
      className="flex flex-wrap items-center gap-x-1.5 text-[12px]">
      <span className="text-ink">{change.entity_name}</span>{' '}
      {field !== '' && <span className="text-ink-3">{field.trim()}</span>}{' '}
      <span className="tnum rounded-[3px] bg-raised px-1.5 leading-5 text-ink-2">{statusLabel(change.from)}</span>{' '}
      <span aria-hidden="true" className="text-ink-3">→</span>{' '}
      <span className="tnum rounded-[3px] border border-accent px-1.5 leading-5 text-accent">{statusLabel(change.to)}</span>
    </li>
  );
}
