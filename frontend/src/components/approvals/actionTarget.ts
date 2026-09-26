import type { City } from '@/api/types';
import { zoneName } from '@/live/derive';
import type { LiveAssets } from '@/live/assets';

const str = (v: unknown): string | null => (typeof v === 'string' && v !== '' ? v : null);

/** Name of the entity a tool input points at, by its id key; `asset_id` may name any asset or zone. */
function primaryName(input: Record<string, unknown>, assets: LiveAssets, city: City | null): string | null {
  const lookups: [key: string, find: (id: string) => string | undefined][] = [
    ['project_id', (id) => assets.projects[id]?.name],
    ['road_id', (id) => assets.roads[id]?.name],
    ['crew_id', (id) => assets.crews[id]?.name],
    ['shelter_id', (id) => assets.shelters[id]?.name],
    ['channel_id', (id) => assets.channels[id]?.name],
    ['asset_id', (id) => assets.channels[id]?.name ?? assets.roads[id]?.name ?? assets.projects[id]?.name
      ?? assets.shelters[id]?.name ?? assets.crews[id]?.name ?? city?.zones.find((z) => z.id === id)?.name],
  ];
  for (const [key, find] of lookups) {
    const id = str(input[key]);
    if (id !== null) return find(id) ?? id;
  }
  return null;
}

/**
 * Human target for a proposed or executed action, e.g. `Rescue Team 03 to Hillview` or `D-7 Kalinadi drain, 2 units`.
 * Unknown tools fall back to the first string value in the input; '' when there is none.
 */
export function actionTargetName(tool: string, input: Record<string, unknown>, assets: LiveAssets, city: City | null): string {
  const primary = primaryName(input, assets, city);
  const zoneId = str(input.zone_id);
  const zone = zoneId === null ? null : zoneName(city, zoneId);
  let target: string;
  if (primary !== null && zone !== null && tool === 'dispatch_crew') target = `${primary} to ${zone}`;
  else target = primary ?? zone ?? Object.values(input).map(str).find((v) => v !== null) ?? '';
  const units = input.units;
  if (typeof units === 'number') {
    const count = `${String(units)} ${units === 1 ? 'unit' : 'units'}`;
    target = target === '' ? count : `${target}, ${count}`;
  }
  return target;
}
