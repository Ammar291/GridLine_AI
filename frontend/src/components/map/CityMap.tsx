import { useCity } from '@/api/queries';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { Panel } from '@/components/ui/Panel';
import { useLiveStore } from '@/live/liveStore';
import { MapCanvas } from './MapCanvas';

/** Geometry comes from GET /api/city; while that is unavailable the live snapshot's city is used instead. */
export function CityMap() {
  const query = useCity();
  const liveCity = useLiveStore((s) => s.city);
  const city = query.data ?? liveCity;

  let body;
  if (city && city.zones.length > 0) {
    const vb = city.view_box;
    body = <MapCanvas key={`${String(vb.x)} ${String(vb.y)} ${String(vb.width)} ${String(vb.height)}`} city={city} />;
  } else if (city) {
    body = <EmptyState title="The city model has no zones yet." body="Zones appear here once the backend seeds the city." />;
  } else if (query.isError) {
    body = <ErrorState message="City map could not be loaded." onRetry={() => { void query.refetch(); }} />;
  } else {
    body = <LoadingState rows={4} label="Loading city map" />;
  }
  return (
    <Panel title="City map" testId="city-map">
      {body}
    </Panel>
  );
}
