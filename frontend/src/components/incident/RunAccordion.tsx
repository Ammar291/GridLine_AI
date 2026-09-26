import { useId, type ReactNode } from 'react';
import type { AgentRun } from '@/api/types';
import { IconChevron } from '@/components/ui/icons';
import { statusLabel } from '@/live/format';

interface RunAccordionProps {
  run: AgentRun;
  number: number;
  expanded: boolean;
  onToggle: () => void;
  children: ReactNode;
}

/** One agent run. The header names the run and what started it; the body is the run's trace. */
export function RunAccordion({ run, number, expanded, onToggle, children }: RunAccordionProps) {
  const bodyId = useId();
  const trigger = run.trigger.replace(/_/g, ' ');
  return (
    <div className="border-b border-line last:border-b-0">
      <button type="button" aria-expanded={expanded} aria-controls={expanded ? bodyId : undefined} onClick={onToggle}
        className="flex items-center gap-2 w-full h-8 px-3 text-left hover:bg-raised">
        <IconChevron className={`shrink-0 text-ink-3 ${expanded ? 'rotate-90' : ''}`} />
        <span className="condensed text-[13px] font-medium">{`Run ${String(number)}, triggered by ${trigger}`}</span>
        <span className="ml-auto text-[11px] text-ink-2">{statusLabel(run.status)}</span>
      </button>
      {expanded && <div id={bodyId} className="flex flex-col gap-4 px-3 pb-4 pt-1">{children}</div>}
    </div>
  );
}
