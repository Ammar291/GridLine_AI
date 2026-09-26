import type { LiveBridge, LiveRoad } from '@/live/assets';
import { statusLabel } from '@/live/format';
import { ACCENT, INK_2, INK_3, NON_SCALING, PAGE, RAISED, bandColor } from '../mapStyles';
import { markerTransform, polylineMidpoint, selectable } from '../mapUtils';

interface RoadsLayerProps {
  roads: LiveRoad[];
  bridges: LiveBridge[];
  u: number;
  selectedId: string | null;
  selectedBridgeId: string | null;
  onSelect: (roadId: string) => void;
  onSelectBridge: (bridgeId: string) => void;
}

function roadLabel(r: LiveRoad): string {
  const parts = [r.name, r.status];
  if (r.reason) parts.push(r.reason);
  if (r.is_evacuation_route) parts.push('evacuation route');
  if (r.is_only_access) parts.push('only access');
  return parts.join(', ');
}

const CROSS = 'M-5 -5 L5 5 M5 -5 L-5 5';

/** Roads in ink; evacuation routes thicker in accent; blocked or closed roads dashed red with a cross at the midpoint. */
export function RoadsLayer({ roads, bridges, u, selectedId, selectedBridgeId, onSelect, onSelectBridge }: RoadsLayerProps) {
  return (
    <g data-layer="roads">
      {roads.map((r) => {
        const cut = r.status !== 'open';
        const width = r.is_evacuation_route ? 5 : 3;
        const stroke = cut ? bandColor('critical') : r.is_evacuation_route ? ACCENT : INK_3;
        const mid = cut ? polylineMidpoint(r.svg_path) : null;
        const line = { d: r.svg_path, fill: 'none', strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, ...NON_SCALING };
        const label = roadLabel(r);
        return (
          <g key={r.id} data-road-id={r.id} data-status={r.status} {...selectable(label, () => { onSelect(r.id); })}>
            <path {...line} stroke="transparent" strokeWidth={14} />
            {r.id === selectedId && <path {...line} stroke={ACCENT} strokeOpacity={0.5} strokeWidth={width + 8} />}
            <path {...line} stroke={stroke} strokeOpacity={r.is_evacuation_route && !cut ? 0.6 : 1} strokeWidth={width}
              strokeDasharray={cut ? '8 6' : undefined} />
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
      {bridges.map((b) => {
        const tone = b.status === 'closed' ? bandColor('critical') : b.status === 'restricted' ? bandColor('warning') : INK_2;
        const label = `${b.name}, ${b.status}${b.reason ? `, ${b.reason}` : ''}`;
        return (
          <g key={b.id} transform={markerTransform(b.xy, u)} data-bridge-id={b.id} data-status={b.status}
            {...selectable(label, () => { onSelectBridge(b.id); })}>
            <circle r={9} fill="transparent" />
            {b.id === selectedBridgeId && <circle r={9} fill="none" stroke={ACCENT} strokeWidth={2} />}
            <rect x={-5} y={-3.5} width={10} height={7} rx={1} fill={RAISED} stroke={tone} strokeWidth={1.5} />
            <path d="M-7 -5.5 L-5 -3.5 M7 -5.5 L5 -3.5 M-7 5.5 L-5 3.5 M7 5.5 L5 3.5" stroke={tone} strokeWidth={1.25} />
            <title>{`${statusLabel('bridge')}: ${label}`}</title>
          </g>
        );
      })}
    </g>
  );
}
