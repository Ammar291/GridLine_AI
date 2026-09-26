import { useEffect, useId, useRef, type ReactNode } from 'react';
import { IconClose } from './icons';

interface DrawerProps {
  open: boolean;
  title: string;
  onClose: () => void;
  children: ReactNode;
  width?: number;
  /** Opens from inside another drawer (the source behind a citation): sits above it and takes Escape first. */
  stacked?: boolean;
}

export function Drawer({ open, title, onClose, children, width = 480, stacked = false }: DrawerProps) {
  const titleId = useId();
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      if (!stacked && document.querySelector('[data-drawer="stacked"]')) return;
      onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose, stacked]);

  // Move focus into the dialog while it is open; hand it back to whatever opened it.
  useEffect(() => {
    if (!open) return;
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    ref.current?.focus();
    return () => {
      if (opener?.isConnected === true) opener.focus();
    };
  }, [open]);

  if (!open) return null;
  return (
    <div
      ref={ref}
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      tabIndex={-1}
      data-drawer={stacked ? 'stacked' : 'base'}
      className={`fixed top-0 right-0 bottom-0 ${stacked ? 'z-50' : 'z-40'} flex flex-col bg-raised border-l border-line outline-none`}
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
