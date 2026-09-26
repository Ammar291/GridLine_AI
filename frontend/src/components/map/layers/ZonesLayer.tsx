import { bandLabel } from '@/components/ui/bandLabel';
import { ACCENT, LINE_STRONG, NON_SCALING, ZONE_FILL_OPACITY, bandColor } from '../mapStyles';
import { selectable } from '../mapUtils';
import type { MapZone } from '../useMapData';

interface ZonesLayerProps { zones: MapZone[]; selectedId: string | null; onSelect: (zoneId: string) => void }

/** Zone polygons washed by band; the selected outline is redrawn on top so shared edges do not hide it. */
export function ZonesLayer({ zones, selectedId, onSelect }: ZonesLayerProps) {
  const selected = zones.find((z) => z.zone.id === selectedId);
  return (
    <g data-layer="zones">
      {zones.map(({ zone, state }) => {
        const { className, ...interactive } = selectable(`${zone.name}, ${bandLabel(state.band)}`, () => { onSelect(zone.id); });
        return (
          <path
            key={zone.id}
            d={zone.svg_path}
            data-zone-id={zone.id}
            data-band={state.band}
            data-testid={`zone-${zone.id}`}
            fill={bandColor(state.band)}
            fillOpacity={ZONE_FILL_OPACITY[state.band]}
            stroke={LINE_STRONG}
            strokeWidth={1}
            className={`${className} hover:stroke-ink-2`}
            {...NON_SCALING}
            {...interactive}
          />
        );
      })}
      {selected && (
        <path d={selected.zone.svg_path} fill="none" stroke={ACCENT} strokeWidth={2} pointerEvents="none" {...NON_SCALING} />
      )}
    </g>
  );
}
