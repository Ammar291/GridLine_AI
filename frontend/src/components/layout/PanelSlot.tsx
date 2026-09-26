import { EmptyState } from '@/components/ui/EmptyState';
import { Panel } from '@/components/ui/Panel';

/** Placeholder panel; later tasks replace each slot with the real panel. */
export function PanelSlot({ title }: { title: string }) {
  return (
    <Panel title={title}>
      <EmptyState title="Coming in a later task" />
    </Panel>
  );
}
