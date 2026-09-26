import type { ReactNode } from 'react';
import { IconFit, IconZoomIn, IconZoomOut } from '@/components/ui/icons';

function ControlButton({ label, onClick, children }: { label: string; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" aria-label={label} title={label} onClick={onClick}
      className="inline-flex items-center justify-center size-7 bg-raised border border-line rounded-[3px] text-ink-2 hover:text-ink hover:border-line-strong">
      {children}
    </button>
  );
}

export function MapControls({ onZoomIn, onZoomOut, onFit }: { onZoomIn: () => void; onZoomOut: () => void; onFit: () => void }) {
  return (
    <div className="absolute bottom-2 right-2 flex flex-col gap-1">
      <ControlButton label="Zoom in" onClick={onZoomIn}><IconZoomIn /></ControlButton>
      <ControlButton label="Zoom out" onClick={onZoomOut}><IconZoomOut /></ControlButton>
      <ControlButton label="Fit" onClick={onFit}><IconFit /></ControlButton>
    </div>
  );
}
