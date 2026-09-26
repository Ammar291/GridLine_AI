import { bandLabel } from '@/components/ui/bandLabel';
import { ACCENT, LINE_STRONG, NON_SCALING, WATER, ZONE_FILL_OPACITY, bandColor } from '../mapStyles';
import { selectable } from '../mapUtils';
import type { MapZone } from '../useMapData';

interface ZonesLayerProps { zones: MapZone[]; selectedId: string | null; onSelect: (zoneId: string) => void }

/** Standing water deeper than this (cm) washes the zone in water colour, stronger as it deepens. */
export const WATER_SHOWN_CM = 1;
const WATER_FULL_CM = 50;

/**
 * Zone polygons washed by their detector band (neutral until the threat detector reports the zone), with a water wash
 * where the simulation reports standing water. The selected outline is redrawn on top so shared edges do not hide it.
 */
export function ZonesLayer({ zones, selectedId, onSelect }: ZonesLayerProps) {
  const selected = zones.find((z) => z.zone.id === selectedId);
  return (
    <g data-layer="zones">
      {zones.map(({ zone, state }) => {
        const band = state?.band ?? 'normal';
        const label = state ? `${zone.name}, ${bandLabel(band)}` : zone.name;
        const { className, ...interactive } = selectable(label, () => { onSelect(zone.id); });
        return (
          <path
            key={zone.id}
            d={zone.svg_path}
            data-zone-id={zone.id}
            data-band={state?.band}
            data-testid={`zone-${zone.id}`}
            fill={bandColor(band)}
            fillOpacity={ZONE_FILL_OPACITY[band]}
            stroke={LINE_STRONG}
            strokeWidth={1}
            className={`${className} hover:stroke-ink-2`}
            {...NON_SCALING}
            {...interactive}
          />
        );
      })}
      {zones.map(({ zone, conditions }) => {
        const depth = conditions?.water_depth_cm ?? 0;
        return depth >= WATER_SHOWN_CM ? (
          <path key={`water-${zone.id}`} d={zone.svg_path} data-water-zone-id={zone.id} fill={WATER} pointerEvents="none"
            fillOpacity={0.12 + 0.33 * Math.min(1, depth / WATER_FULL_CM)} />
        ) : null;
      })}
      {selected && (
        <path d={selected.zone.svg_path} fill="none" stroke={ACCENT} strokeWidth={2} pointerEvents="none" {...NON_SCALING} />
      )}
    </g>
  );
}
