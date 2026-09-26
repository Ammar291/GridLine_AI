import type { Channel } from '@/api/types';
import { fmtPct } from '@/live/format';
import { ACCENT, BLOCKED_THRESHOLD, NON_SCALING, WATER, bandColor } from '../mapStyles';
import { selectable } from '../mapUtils';

interface DrainageLayerProps { channels: Channel[]; selectedId: string | null; onSelect: (channelId: string) => void }

/** Dashed drains, thickness proportional to remaining capacity, red once more than 30% blocked. */
export function DrainageLayer({ channels, selectedId, onSelect }: DrainageLayerProps) {
  return (
    <g data-layer="drainage">
      {channels.map((c) => {
        const ratio = c.design_capacity_m3s > 0 ? Math.min(1, Math.max(0, c.current_capacity_m3s / c.design_capacity_m3s)) : 0;
        const blocked = c.blocked_fraction > BLOCKED_THRESHOLD;
        const width = 1 + 3 * ratio;
        const label = `${c.name}, ${fmtPct(ratio)} of design capacity${blocked ? ', blocked' : ''}`;
        return (
          <g key={c.id} data-channel-id={c.id} data-blocked={blocked} {...selectable(label, () => { onSelect(c.id); })}>
            <path d={c.svg_path} fill="none" stroke="transparent" strokeWidth={12} {...NON_SCALING} />
            {c.id === selectedId && (
              <path d={c.svg_path} fill="none" stroke={ACCENT} strokeOpacity={0.5} strokeWidth={width + 5} strokeLinecap="round" {...NON_SCALING} />
            )}
            <path d={c.svg_path} fill="none" stroke={blocked ? bandColor('critical') : WATER} strokeWidth={width}
              strokeDasharray="6 4" strokeLinecap="round" strokeLinejoin="round" {...NON_SCALING} />
            <title>{label}</title>
          </g>
        );
      })}
    </g>
  );
}
