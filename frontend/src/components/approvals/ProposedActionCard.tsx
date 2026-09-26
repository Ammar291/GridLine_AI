import type { Citation, ProposedAction } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { CitationChip } from '@/components/incident/CitationChip';
import { resolveCitation } from '@/components/incident/citations';
import { toolVerb } from '@/live/format';
import { PROPOSED_ACTION_STATE_LABELS, type ProposedActionState } from './proposedActionState';

interface ProposedActionCardProps {
  action: ProposedAction;
  state: ProposedActionState;
  selectable: boolean;
  selected: boolean;
  onToggle: () => void;
  onWhy: () => void;
  targetName: string;
  /** Citations recorded by the run, so evidence chips can show labels instead of raw ids. */
  citations?: Citation[];
  disabled?: boolean;
}

const STATE_CHIP: Record<ProposedActionState, string> = {
  proposed: 'bg-raised text-ink-2',
  auto_approved: 'border border-accent text-accent',
  approved: 'bg-accent text-page',
  rejected: 'border border-band-critical text-band-critical-text',
  executing: 'border border-accent text-accent',
  executed: 'border border-ok text-ok-text',
  verified: 'bg-ok text-page',
  failed: 'bg-band-critical text-white',
};

/** One action the agent proposes: what it does, to what, why, what it should change, and the evidence. */
export function ProposedActionCard({ action, state, selectable, selected, onToggle, onWhy, targetName, citations = [], disabled = false }: ProposedActionCardProps) {
  // toolVerb keeps unknown tool names as-is, so the heading is never blank.
  const verb = toolVerb(action.tool);
  const title = targetName === '' ? verb : `${verb}: ${targetName}`;
  return (
    <article aria-label={title} className="flex gap-2.5 py-2.5 border-b border-line last:border-b-0">
      <div className="w-4 shrink-0 pt-0.5">
        {selectable && (
          <input type="checkbox" aria-label={`Include ${title}`} checked={selected} onChange={onToggle} disabled={disabled}
            className="size-3.5 accent-[var(--color-accent)]" />
        )}
      </div>
      <div className="flex flex-col gap-1 min-w-0 flex-1">
        <div className="flex items-baseline gap-2 min-w-0">
          <h4 className="condensed text-[14px] font-medium shrink-0">{verb}</h4>
          <span className="text-ink-2 truncate">{targetName}</span>
          <span data-state={state} className={`ml-auto shrink-0 rounded-[3px] px-1.5 text-[11px] leading-5 font-medium ${STATE_CHIP[state]}`}>
            {PROPOSED_ACTION_STATE_LABELS[state]}
          </span>
        </div>
        <p className="text-ink max-w-[80ch]">{action.rationale}</p>
        <p className="text-ink-2 max-w-[80ch]"><span className="text-ink-3">Expected effect </span>{action.expected_effect}</p>
        <div className="flex flex-wrap items-center gap-1.5 mt-0.5">
          {action.citation_ids.map((id) => <CitationChip key={id} citation={resolveCitation(id, citations)} />)}
          <Button size="sm" className="ml-auto" aria-label={`Why? ${verb}`} onClick={onWhy}>Why?</Button>
        </div>
      </div>
    </article>
  );
}
