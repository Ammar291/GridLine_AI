import type { City, CitySnapshot } from '@/api/types';
import { KeyValue } from '@/components/ui/KeyValue';
import { bandLabel } from '@/components/ui/bandLabel';
import { zoneName } from '@/live/derive';
import { fmtIndex, fmtPct, fmtSimTime, statusLabel } from '@/live/format';
import type { LiveAssets } from '@/live/assets';

interface CityStateFactsProps { snapshot: CitySnapshot; city: City | null; roads: LiveAssets['roads'] }

const num = (v: number) => String(Number(v.toFixed(2)));

/** The observe node's snapshot of the zone: what the agent read before reasoning, not the live value now. */
export function CityStateFacts({ snapshot, city, roads }: CityStateFactsProps) {
  const r = snapshot.readings;
  const { project, channel } = snapshot;
  const names = (ids: string[], name: (id: string) => string) => (ids.length === 0 ? 'None' : ids.map(name).join(', '));
  const items = [
    { label: 'Zone', value: zoneName(city, snapshot.zone_id) },
    { label: 'Band', value: bandLabel(r.band) },
    { label: 'Rain intensity', value: `${num(r.rain_intensity_mm_h)} mm/h` },
    { label: 'Rain, last 24 h', value: `${num(r.rain_24h_mm)} mm` },
    { label: 'Saturation', value: fmtPct(r.saturation) },
    { label: 'Landslide index', value: fmtIndex(r.landslide_index) },
    { label: 'Flood index', value: fmtIndex(r.flood_index) },
    { label: 'Downstream zones', value: names(snapshot.downstream_zone_ids, (id) => zoneName(city, id)) },
    ...(project
      ? [
          { label: 'Project', value: `${project.name} (${statusLabel(project.status).toLowerCase()})` },
          { label: 'Excavation depth', value: `${num(project.excavation_depth_m)} of ${num(project.planned_depth_m)} m` },
        ]
      : []),
    ...(channel
      ? [
          { label: 'Channel', value: channel.name },
          { label: 'Channel capacity', value: `${num(channel.current_capacity_m3s)} of ${num(channel.design_capacity_m3s)} m³/s, ${fmtPct(channel.blocked_fraction)} blocked` },
        ]
      : []),
    { label: 'Closed roads', value: names(snapshot.closed_roads, (id) => roads[id]?.name ?? id) },
  ];
  return (
    <div className="flex flex-col gap-3">
      <p className="text-[11px] text-ink-3 tnum">{`Observed at ${fmtSimTime(snapshot.sim_time)}`}</p>
      <KeyValue columns={2} items={items} />
      <div>
        <h4 className="text-[11px] text-ink-2 font-normal">Crews</h4>
        {snapshot.crews.length === 0 ? (
          <p className="text-ink-3">No crews in the snapshot.</p>
        ) : (
          <ul aria-label="Crews" className="flex flex-col">
            {snapshot.crews.map((c) => (
              <li key={c.id}>{`${c.name}: ${statusLabel(c.status)} in ${zoneName(city, c.location_zone_id)}`}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
