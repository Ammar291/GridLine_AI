import { Button } from '@/components/ui/Button';

interface DecisionBarProps {
  total: number;
  selected: number;
  onApproveAll: () => void;
  onApproveSelected: () => void;
  onReject: () => void;
  note: string;
  onNote: (s: string) => void;
  disabled: boolean;
}

/** The operator's decision: approve what is ticked (all of it, or part), or reject the plan, with an optional note. */
export function DecisionBar({ total, selected, onApproveAll, onApproveSelected, onReject, note, onNote, disabled }: DecisionBarProps) {
  const all = selected === total;
  return (
    <div className="flex items-start gap-2 pt-2.5">
      <textarea aria-label="Note" placeholder="Note for the record (optional)" rows={1} value={note} disabled={disabled}
        onChange={(e) => { onNote(e.target.value); }}
        className="flex-1 min-w-0 h-8 min-h-8 resize-y rounded-[3px] border border-line bg-page px-2 py-1.5 text-[12px] text-ink placeholder:text-ink-3 disabled:opacity-50" />
      <Button variant="primary" disabled={disabled || selected === 0} onClick={all ? onApproveAll : onApproveSelected}>
        {`Approve ${String(selected)} ${selected === 1 ? 'action' : 'actions'}`}
      </Button>
      <Button variant="danger" disabled={disabled} onClick={onReject}>Reject plan</Button>
    </div>
  );
}
