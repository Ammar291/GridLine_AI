import type { ReactNode } from 'react';

interface Item { label: string; value: ReactNode; muted?: boolean }

const COLS: Record<1 | 2 | 3, string> = { 1: 'grid-cols-1', 2: 'grid-cols-2', 3: 'grid-cols-3' };

export function KeyValue({ items, columns = 2 }: { items: Item[]; columns?: 1 | 2 | 3 }) {
  return (
    <dl className={`grid ${COLS[columns]} gap-x-4 gap-y-2`}>
      {items.map((it) => (
        <div key={it.label} className="min-w-0">
          <dt className="text-[11px] text-ink-2">{it.label}</dt>
          <dd className={`m-0 tnum text-[13px] ${it.muted === true ? 'text-ink-3' : 'text-ink'}`}>{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}
