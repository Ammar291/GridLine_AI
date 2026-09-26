// What the live store currently knows about a non-document citation (sensor reading, entity state, event).
import { bandLabel } from '@/components/ui/bandLabel';
import { describeEvent } from '@/live/describeEvent';
import { zoneName } from '@/live/derive';
import { fmtIndex, fmtPct, fmtSimTime, statusLabel } from '@/live/format';
import type { LiveState } from '@/live/types';
import { citationKind } from './citations';

export interface SourceFacts {
  heading: string;
  items: { label: string; value: string }[];
  /** Said instead of, or after, the items when the live store cannot fully answer. */
  note: string | null;
}

export type LiveView = Pick<LiveState, 'city' | 'zoneState' | 'assets' | 'feed'>;

const num = (v: number) => String(Number(v.toFixed(2)));

function sensorFacts(body: string, live: LiveView): SourceFacts {
  const [sensorId = body, citedAt] = body.split('@');
  const sensor = live.assets.sensors[sensorId];
  const items = [{ label: 'Sensor', value: sensorId }];
  if (citedAt) items.push({ label: 'Cited reading at', value: fmtSimTime(citedAt) });
  if (!sensor) return { heading: 'Live reading', items, note: 'This sensor is not in the city model.' };
  items.push({ label: 'Zone', value: zoneName(live.city, sensor.zone_id) });
  if (sensor.last_value == null) return { heading: 'Live reading', items, note: 'No reading has arrived from this sensor yet.' };
  items.push({ label: 'Latest value', value: `${num(sensor.last_value)} ${sensor.unit}` });
  items.push({ label: 'Latest reading at', value: fmtSimTime(sensor.last_sim_time ?? null) });
  return { heading: 'Live reading', items, note: null };
}

function stateFacts(body: string, live: LiveView): SourceFacts {
  const dot = body.indexOf('.');
  const entity = dot < 0 ? body : body.slice(0, dot);
  const id = dot < 0 ? '' : body.slice(dot + 1);
  const heading = 'Live state';
  const zs = entity === 'zone' ? live.zoneState[id] : undefined;
  if (zs) {
    return {
      heading, note: null,
      items: [
        { label: 'Zone', value: zoneName(live.city, id) },
        { label: 'Band', value: bandLabel(zs.band) },
        { label: 'Landslide index', value: fmtIndex(zs.landslide_index) },
        { label: 'Flood index', value: fmtIndex(zs.flood_index) },
        { label: 'Saturation', value: fmtPct(zs.saturation) },
        { label: 'Rain intensity', value: `${String(Math.round(zs.rain_intensity_mm_h))} mm/h` },
      ],
    };
  }
  const channel = entity === 'channel' ? live.assets.channels[id] : undefined;
  if (channel) {
    return {
      heading, note: null,
      items: [
        { label: 'Channel', value: channel.name },
        { label: 'Capacity', value: `${num(channel.current_capacity_m3s)} of ${num(channel.design_capacity_m3s)} m³/s` },
        { label: 'Blocked', value: fmtPct(channel.blocked_fraction) },
      ],
    };
  }
  const tables = { crew: live.assets.crews, road: live.assets.roads, shelter: live.assets.shelters, project: live.assets.projects };
  const other = entity in tables ? tables[entity as keyof typeof tables][id] : undefined;
  if (other) {
    return { heading, note: null, items: [{ label: statusLabel(entity), value: other.name }, { label: 'Status', value: statusLabel(other.status) }] };
  }
  return { heading, items: [{ label: 'Entity', value: body }], note: 'No live value is held for this entity.' };
}

function eventFacts(eventId: string, live: LiveView): SourceFacts {
  const event = live.feed.find((e) => e.id === eventId);
  if (!event) return { heading: 'Event', items: [{ label: 'Event id', value: eventId }], note: 'This event is no longer in the live feed.' };
  return {
    heading: 'Event', note: null,
    items: [{ label: 'Event', value: describeEvent(event, live.city) }, { label: 'Sim time', value: fmtSimTime(event.sim_time) }],
  };
}

/** Facts for a sensor, state or event citation id; null for document chunks, which are fetched instead. */
export function sourceFacts(citationId: string, live: LiveView): SourceFacts | null {
  switch (citationKind(citationId)) {
    case 'sensor': return sensorFacts(citationId.slice('sensor:'.length), live);
    case 'state': return stateFacts(citationId.slice('state:'.length), live);
    case 'event': return eventFacts(citationId.slice('event:'.length), live);
    case 'chunk': return null;
  }
}
