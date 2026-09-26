import { useEffect, useId, type ReactNode } from 'react';
import { IconClose } from './icons';

interface DrawerProps { open: boolean; title: string; onClose: () => void; children: ReactNode; width?: number }

export function Drawer({ open, title, onClose, children, width = 480 }: DrawerProps) {
  const titleId = useId();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      className="fixed top-0 right-0 bottom-0 z-40 flex flex-col bg-raised border-l border-line"
      style={{ width }}
    >
      <header className="flex items-center justify-between h-10 shrink-0 px-4 border-b border-line">
        <h2 id={titleId} className="condensed text-[14px] font-medium">
          {title}
        </h2>
        <button
          type="button"
          aria-label="Close"
          onClick={onClose}
          className="inline-flex items-center justify-center size-7 rounded-[3px] text-ink-2 hover:bg-panel hover:text-ink"
        >
          <IconClose />
        </button>
      </header>
      <div className="flex-1 min-h-0 overflow-auto p-4">{children}</div>
    </div>
  );
}
