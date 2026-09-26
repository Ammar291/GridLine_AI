import { useId } from 'react';
import { NON_SCALING, bandColor } from '../mapStyles';
import type { MapData } from '../useMapData';

/** Gap left between a cascade arrow and the zone labels it joins, in screen pixels. */
const ARROW_GAP_PX = 22;

/** Critical zones pulse, evacuated zones get a hatched exclusion ring, cascades draw source → affected zone arrows. */
export function ThreatLayer({ data, u }: { data: MapData; u: number }) {
  const markerId = `${useId().replace(/[^\w-]/g, '')}-cascade-head`;
  const critical = bandColor('critical');
  return (
    <g data-layer="threats" pointerEvents="none">
      <defs>
        <marker id={markerId} viewBox="0 0 10 10" refX={9} refY={5} markerWidth={10 * u} markerHeight={10 * u}
          markerUnits="userSpaceOnUse" orient="auto">
          <path d="M0 0 L10 5 L0 10 Z" fill={bandColor('warning')} />
        </marker>
      </defs>
      {data.evacuatedZoneIds.map((id) => {
        const z = data.zoneById.get(id);
        return z ? (
          <path key={`evac-${id}`} d={z.zone.svg_path} data-threat="evacuate" data-threat-zone-id={id} fill="none"
            stroke={critical} strokeOpacity={0.35} strokeWidth={8} strokeDasharray="2 6" {...NON_SCALING} />
        ) : null;
      })}
      {data.zones.filter((z) => z.state.band === 'critical').map(({ zone }) => (
        <path key={`crit-${zone.id}`} d={zone.svg_path} data-threat="critical" data-threat-zone-id={zone.id} className="animate-pulse"
          fill="none" stroke={critical} strokeWidth={3} {...NON_SCALING} />
      ))}
      {data.cascades.map(({ from, to }) => {
        const a = data.zoneById.get(from)?.zone.label_xy;
        const b = data.zoneById.get(to)?.zone.label_xy;
        if (!a || !b) return null;
        const dist = Math.hypot(b.x - a.x, b.y - a.y);
        const gap = Math.min(ARROW_GAP_PX * u, dist / 3);
        const ux = dist > 0 ? (b.x - a.x) / dist : 0;
        const uy = dist > 0 ? (b.y - a.y) / dist : 0;
        return (
          <line key={`${from}>${to}`} data-cascade={`${from}>${to}`} x1={a.x + ux * gap} y1={a.y + uy * gap} x2={b.x - ux * gap} y2={b.y - uy * gap}
            stroke={bandColor('warning')} strokeWidth={2} markerEnd={`url(#${markerId})`} {...NON_SCALING} />
        );
      })}
    </g>
  );
}
