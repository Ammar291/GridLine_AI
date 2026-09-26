import { useId, type ReactNode } from 'react';

/** A titled region of the reasoning trace. */
export function TraceSection({ title, children }: { title: string; children: ReactNode }) {
  const id = useId();
  return (
    <section aria-labelledby={id} className="flex flex-col gap-1.5 max-w-[80ch]">
      <h3 id={id} className="text-[12px] font-medium text-ink-2">{title}</h3>
      {children}
    </section>
  );
}
