import type { MapFeature } from '@/api/types';
import { LINE_STRONG, NON_SCALING } from '../mapStyles';

export function HillsLayer({ features }: { features: MapFeature[] }) {
  return (
    <g data-layer="hills" pointerEvents="none">
      {features.filter((f) => f.kind === 'hill_contour').map((f) => (
        <path key={f.id} d={f.svg_path} fill="none" stroke={LINE_STRONG} strokeWidth={1} {...NON_SCALING} />
      ))}
    </g>
  );
}
