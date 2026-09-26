import { bandLabel } from '@/components/ui/bandLabel';
import { INK, INK_2, TEXT_HALO } from '../mapStyles';
import { markerTransform } from '../mapUtils';
import type { MapZone } from '../useMapData';
import { WATER_SHOWN_CM } from './ZonesLayer';

/** The second label line: the detector band in words (colour is never the only carrier), else standing water. */
function subtitle({ state, conditions }: MapZone): string | null {
  if (state) return bandLabel(state.band);
  const depth = conditions?.water_depth_cm ?? 0;
  return depth >= WATER_SHOWN_CM ? `Water ${String(Math.round(depth))} cm` : null;
}

/** Zone names at the anchors the backend placed clear of markers and water (GET /api/city label_xy). */
export function LabelsLayer({ zones, u }: { zones: MapZone[]; u: number }) {
  return (
    <g data-layer="labels" pointerEvents="none">
      {zones.map((z) => {
        const sub = subtitle(z);
        return (
          <g key={z.zone.id} transform={markerTransform(z.zone.label_xy, u)}>
            <text textAnchor="middle" fontSize={13} fontWeight={500} fill={INK} {...TEXT_HALO}>{z.zone.name}</text>
            {sub !== null && <text y={14} textAnchor="middle" fontSize={11} fill={INK_2} {...TEXT_HALO}>{sub}</text>}
          </g>
        );
      })}
    </g>
  );
}
