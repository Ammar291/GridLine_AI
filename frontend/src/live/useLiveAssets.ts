import { useMemo } from 'react';
import { liveAssets, type LiveAssets } from './assets';
import { useLiveStore } from './liveStore';

/** The city's assets merged with their live state; recomputed only when the city, world or readings change. */
export function useLiveAssets(): LiveAssets {
  const city = useLiveStore((s) => s.city);
  const world = useLiveStore((s) => s.world);
  const readings = useLiveStore((s) => s.readings);
  return useMemo(() => liveAssets(city, world, readings), [city, world, readings]);
}
