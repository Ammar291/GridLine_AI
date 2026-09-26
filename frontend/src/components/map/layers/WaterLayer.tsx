import { useId } from 'react';
import type { MapFeature } from '@/api/types';
import { INK_2, NON_SCALING, PAGE, WATER } from '../mapStyles';
import { markerTransform, vertexCentroid } from '../mapUtils';

/** Rivers (stroked) and lakes (washed), with river names set along their course. */
export function WaterLayer({ features, u }: { features: MapFeature[]; u: number }) {
  const prefix = useId().replace(/[^\w-]/g, '');
  const rivers = features.filter((f) => f.kind === 'river');
  const lakes = features.filter((f) => f.kind === 'lake');
  const halo = { stroke: PAGE, strokeWidth: 3 * u, paintOrder: 'stroke' as const };
  return (
    <g data-layer="water" pointerEvents="none">
      {lakes.map((f) => <path key={f.id} d={f.svg_path} fill={WATER} fillOpacity={0.2} stroke="none" />)}
      {rivers.map((f) => (
        <path key={f.id} id={`${prefix}-${f.id}`} d={f.svg_path} fill="none" stroke={WATER} strokeOpacity={0.45} strokeWidth={6}
          strokeLinecap="round" strokeLinejoin="round" {...NON_SCALING} />
      ))}
      {rivers.map((f) => f.label ? (
        <text key={`label-${f.id}`} fontSize={11 * u} fill={INK_2} dy={-6 * u} {...halo}>
          <textPath href={`#${prefix}-${f.id}`} startOffset="50%" textAnchor="middle">{f.label}</textPath>
        </text>
      ) : null)}
      {lakes.map((f) => {
        const at = f.label ? vertexCentroid(f.svg_path) : null;
        return at && f.label ? (
          <g key={`label-${f.id}`} transform={markerTransform(at, u)}>
            <text textAnchor="middle" dy={4} fontSize={11} fill={INK_2} stroke={PAGE} strokeWidth={3} paintOrder="stroke">{f.label}</text>
          </g>
        ) : null;
      })}
    </g>
  );
}
