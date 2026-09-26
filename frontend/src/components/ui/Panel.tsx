import type { ReactNode } from 'react';

interface PanelProps {
  title: string;
  count?: number;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
  testId?: string;
}

export function Panel({ title, count, actions, children, className, testId }: PanelProps) {
  return (
    <section
      className={`flex flex-col h-full min-h-0 bg-panel border border-line ${className ?? ''}`}
      data-testid={testId}
      aria-label={title}
    >
      <header className="flex items-center justify-between h-8 shrink-0 px-3 border-b border-line gap-2">
        <h2 className="condensed text-[13px] font-medium flex items-center gap-2">
          {title}
          {count !== undefined && <span className="tnum text-ink-2 font-normal">{count}</span>}
        </h2>
        {actions !== undefined && <div className="flex items-center gap-2">{actions}</div>}
      </header>
      <div className="flex-1 min-h-0 overflow-auto">{children}</div>
    </section>
  );
}
