import type { MapFeature } from '@/api/types';
import { bandLabel } from '@/components/ui/bandLabel';
import { INK, INK_2, TEXT_HALO } from '../mapStyles';
import { markerTransform, pathVertices } from '../mapUtils';
import type { MapZone } from '../useMapData';

/** Zone names with their band in words (colour is never the only carrier), plus free-standing map labels. */
export function LabelsLayer({ zones, features, u }: { zones: MapZone[]; features: MapFeature[]; u: number }) {
  return (
    <g data-layer="labels" pointerEvents="none">
      {zones.map(({ zone, state }) => (
        <g key={zone.id} transform={markerTransform(zone.label_xy, u)}>
          <text textAnchor="middle" fontSize={13} fontWeight={500} fill={INK} {...TEXT_HALO}>{zone.name}</text>
          <text y={14} textAnchor="middle" fontSize={11} fill={INK_2} {...TEXT_HALO}>{bandLabel(state.band)}</text>
        </g>
      ))}
      {features.filter((f) => f.kind === 'label' && f.label).map((f) => {
        const at = pathVertices(f.svg_path)?.[0];
        return at ? (
          <g key={f.id} transform={markerTransform(at, u)}>
            <text textAnchor="middle" fontSize={11} fill={INK_2} {...TEXT_HALO}>{f.label}</text>
          </g>
        ) : null;
      })}
    </g>
  );
}
