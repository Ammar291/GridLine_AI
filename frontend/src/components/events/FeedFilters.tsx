import { useId } from 'react';
import { FEED_FILTERS, GROUP_BORDER, type FeedFilter } from './eventGroups';

/** Native radios styled as chips: arrow keys move between them, and each chip carries its group's row tint. */
export function FeedFilters({ value, onChange }: { value: FeedFilter; onChange: (f: FeedFilter) => void }) {
  const name = useId();
  return (
    <div role="radiogroup" aria-label="Filter events" className="flex items-center gap-0.5">
      {FEED_FILTERS.map((f) => (
        <label key={f.value} className="relative cursor-pointer">
          <input type="radio" name={name} value={f.value} checked={value === f.value} onChange={() => { onChange(f.value); }}
            className="peer sr-only" />
          <span
            className={`flex items-center h-5 px-1.5 rounded-[3px] border border-transparent text-[11px] text-ink-2 hover:text-ink
              peer-checked:bg-raised peer-checked:border-line-strong peer-checked:text-ink
              peer-focus-visible:outline-2 peer-focus-visible:outline-accent
              ${f.value === 'all' ? '' : `border-l-2 ${GROUP_BORDER[f.value]}`}`}
          >
            {f.label}
          </span>
        </label>
      ))}
    </div>
  );
}
