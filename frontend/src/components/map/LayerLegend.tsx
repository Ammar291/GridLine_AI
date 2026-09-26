import { useState, type ReactNode } from 'react';
import { IconChevron } from '@/components/ui/icons';
import { ALL_LAYERS, type LayerId } from '@/ui/uiStore';
import { INK, INK_3, LINE_STRONG, OK, RAISED, WATER, bandColor, LAYER_LABELS } from './mapStyles';

/** A 16×10 key that mirrors how each layer is drawn on the map. */
function LayerKey({ layer }: { layer: LayerId }) {
  const art: Record<LayerId, ReactNode> = {
    hills: <path d="M1 9 Q8 1 15 9" fill="none" stroke={LINE_STRONG} />,
    water: <path d="M1 7 Q5 3 8 6 T15 4" fill="none" stroke={WATER} strokeOpacity={0.7} strokeWidth={2.5} />,
    zones: <rect x={2} y={1} width={12} height={8} fill={bandColor('watch')} fillOpacity={0.28} stroke={LINE_STRONG} />,
    drainage: <path d="M1 5 H15" stroke={WATER} strokeWidth={2} strokeDasharray="3 2" />,
    roads: <path d="M1 5 H15" stroke={INK_3} strokeWidth={3} />,
    construction: <><rect x={4} y={1} width={8} height={8} fill={RAISED} stroke={INK} /><path d="M4 6 L9 1" stroke={INK} /></>,
    hospitals: <><circle cx={8} cy={5} r={4.5} fill={RAISED} stroke={LINE_STRONG} /><path d="M8 2.5 V7.5 M5.5 5 H10.5" stroke={INK} strokeWidth={1.5} /></>,
    shelters: <path d="M3 5 L8 1 L13 5 V9 H3 Z" fill={OK} />,
    crews: <path d="M8 0.5 L12.5 9 L8 7 L3.5 9 Z" fill={OK} />,
    sensors: <circle cx={8} cy={5} r={2} fill={INK_3} />,
    threats: <rect x={2} y={1} width={12} height={8} fill="none" stroke={bandColor('critical')} strokeWidth={2} />,
  };
  return <svg width={16} height={10} viewBox="0 0 16 10" aria-hidden="true" className="shrink-0">{art[layer]}</svg>;
}

/** Map legend that doubles as the layer switch. Collapsible so it never has to cover the city. */
export function LayerLegend({ active, onToggle }: { active: ReadonlySet<LayerId>; onToggle: (l: LayerId) => void }) {
  const [open, setOpen] = useState(true);
  return (
    <div className="absolute top-2 left-2 bg-raised/90 border border-line rounded-[3px] text-[11px]">
      <button type="button" aria-expanded={open} onClick={() => { setOpen((o) => !o); }}
        className="flex items-center gap-1 h-6 px-2 w-full text-ink-2 hover:text-ink">
        <IconChevron className={`size-3 transition-transform ${open ? 'rotate-90' : ''}`} />
        Layers
      </button>
      {open && (
        <ul className="grid grid-cols-2 gap-x-3 gap-y-0.5 px-2 pb-2">
          {ALL_LAYERS.map((layer) => (
            <li key={layer}>
              <label className="flex items-center gap-1.5 h-5 cursor-pointer text-ink-2 hover:text-ink">
                <input type="checkbox" checked={active.has(layer)} onChange={() => { onToggle(layer); }}
                  className="size-3 accent-accent" />
                <LayerKey layer={layer} />
                <span>{LAYER_LABELS[layer]}</span>
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
