import type { LiveChannel } from '@/live/assets';
import { fmtPct } from '@/live/format';
import { ACCENT, BLOCKED_THRESHOLD, NON_SCALING, WATER, bandColor } from '../mapStyles';
import { selectable } from '../mapUtils';

interface DrainageLayerProps { channels: LiveChannel[]; selectedId: string | null; onSelect: (channelId: string) => void }

const num = (v: number) => String(Number(v.toFixed(1)));

/**
 * Dashed drains, thickness proportional to the capacity left (blockage included), red once more than 30% blocked;
 * an overflowing drain is drawn solid.
 */
export function DrainageLayer({ channels, selectedId, onSelect }: DrainageLayerProps) {
  return (
    <g data-layer="drainage">
      {channels.map((c) => {
        const ratio = c.design_capacity_m3s > 0 ? Math.min(1, Math.max(0, c.capacity_m3s / c.design_capacity_m3s)) : 0;
        const blocked = c.blocked_fraction > BLOCKED_THRESHOLD;
        const overflowing = c.overflow_m3s > 0;
        const width = 1 + 3 * ratio;
        const label = [
          c.name,
          `${num(c.flow_m3s)} of ${num(c.capacity_m3s)} m³/s`,
          `${fmtPct(ratio)} of design capacity`,
          ...(blocked ? [`${fmtPct(c.blocked_fraction)} blocked`] : []),
          ...(overflowing ? [`overflowing ${num(c.overflow_m3s)} m³/s`] : []),
        ].join(', ');
        return (
          <g key={c.id} data-channel-id={c.id} data-blocked={blocked} data-overflowing={overflowing} {...selectable(label, () => { onSelect(c.id); })}>
            <path d={c.svg_path} fill="none" stroke="transparent" strokeWidth={12} {...NON_SCALING} />
            {c.id === selectedId && (
              <path d={c.svg_path} fill="none" stroke={ACCENT} strokeOpacity={0.5} strokeWidth={width + 5} strokeLinecap="round" {...NON_SCALING} />
            )}
            <path d={c.svg_path} fill="none" stroke={blocked ? bandColor('critical') : WATER} strokeWidth={width}
              strokeDasharray={overflowing ? undefined : '6 4'} strokeLinecap="round" strokeLinejoin="round" {...NON_SCALING} />
            <title>{label}</title>
          </g>
        );
      })}
    </g>
  );
}
