import type { Road } from '@/api/types';
import { ACCENT, INK_3, NON_SCALING, PAGE, bandColor } from '../mapStyles';
import { markerTransform, polylineMidpoint, selectable } from '../mapUtils';

interface RoadsLayerProps { roads: Road[]; u: number; selectedId: string | null; onSelect: (roadId: string) => void }

function roadLabel(r: Road): string {
  const parts = [r.name, r.status === 'closed' ? 'closed' : 'open'];
  if (r.is_evacuation_route) parts.push('evacuation route');
  if (r.is_bridge) parts.push('bridge');
  return parts.join(', ');
}

const CROSS = 'M-5 -5 L5 5 M5 -5 L-5 5';

/** Roads in ink; evacuation routes thicker in accent; closed roads dashed red with a cross at the midpoint. */
export function RoadsLayer({ roads, u, selectedId, onSelect }: RoadsLayerProps) {
  return (
    <g data-layer="roads">
      {roads.map((r) => {
        const closed = r.status === 'closed';
        const width = r.is_evacuation_route ? 5 : 3;
        const stroke = closed ? bandColor('critical') : r.is_evacuation_route ? ACCENT : INK_3;
        const mid = closed ? polylineMidpoint(r.svg_path) : null;
        const line = { d: r.svg_path, fill: 'none', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, ...NON_SCALING };
        const label = roadLabel(r);
        return (
          <g key={r.id} data-road-id={r.id} data-status={r.status} {...selectable(label, () => { onSelect(r.id); })}>
            <path {...line} stroke="transparent" strokeWidth={14} />
            {r.id === selectedId && <path {...line} stroke={ACCENT} strokeOpacity={0.5} strokeWidth={width + 8} />}
            {r.is_bridge && <path {...line} stroke={INK_3} strokeWidth={width + 6} strokeLinecap="butt" />}
            {r.is_bridge && <path {...line} stroke={PAGE} strokeWidth={width + 3} strokeLinecap="butt" />}
            <path {...line} stroke={stroke} strokeOpacity={r.is_evacuation_route && !closed ? 0.6 : 1} strokeWidth={width}
              strokeDasharray={closed ? '8 6' : undefined} />
            {mid && (
              <g transform={markerTransform(mid, u)}>
                <path d={CROSS} stroke={PAGE} strokeWidth={5} strokeLinecap="round" />
                <path d={CROSS} stroke={bandColor('critical')} strokeWidth={2.5} strokeLinecap="round" />
              </g>
            )}
            <title>{label}</title>
          </g>
        );
      })}
    </g>
  );
}
