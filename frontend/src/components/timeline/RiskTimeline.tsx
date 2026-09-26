import { useMemo } from 'react';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { Panel } from '@/components/ui/Panel';
import { useBands } from '@/api/queries';
import { useSelectedIncident } from '@/hooks/useSelectedIncident';
import { zoneName } from '@/live/derive';
import { useLiveStore } from '@/live/liveStore';
import { useUiStore } from '@/ui/uiStore';
import { IndexChart } from './IndexChart';
import { RainChart } from './RainChart';
import { TimelineLegend } from './TimelineLegend';
import { WaterChart } from './WaterChart';
import { buildRows, milestoneMarkers, thresholdLines, timelineHazard } from './timelineData';

/** Vertical space (px) the two chart headings take out of an explicit test size. */
const HEADINGS_PX = 40;
const selectClass = 'h-6 rounded-[3px] border border-line bg-page px-1.5 text-[12px] text-ink';

/** Rain intensity above the indices, sharing sim time on x. `size` fixes the chart dimensions (tests only). */
export function RiskTimeline({ size }: { size?: { width: number; height: number } }) {
  const telemetry = useLiveStore((s) => s.telemetry);
  const milestones = useLiveStore((s) => s.milestones);
  const city = useLiveStore((s) => s.city);
  const incidents = useLiveStore((s) => s.incidents);
  const hasSnapshot = useLiveStore((s) => s.hasSnapshot);
  const connection = useLiveStore((s) => s.connection);
  const pickedZoneId = useUiStore((s) => s.timelineZoneId);
  const setTimelineZone = useUiStore((s) => s.setTimelineZone);
  const { zoneId: incidentZoneId } = useSelectedIncident();

  const zones = city?.zones ?? [];
  const zoneId = pickedZoneId ?? incidentZoneId ?? zones[0]?.id ?? null;
  const points = zoneId === null ? undefined : telemetry[zoneId];
  const rows = useMemo(() => buildRows(points ?? []), [points]);
  const markers = useMemo(
    () => (zoneId === null ? [] : milestoneMarkers(milestones, zoneId, rows, incidents)),
    [milestones, zoneId, rows, incidents],
  );
  const hazard = zoneId === null ? 'landslide' : timelineHazard(zoneId, incidents, rows);
  const bands = useBands();
  const hasIndices = rows.some((r) => r.landslide !== null || r.flood !== null);
  // PENDING (threat detector): index thresholds come from GET /api/detector/bands; without indices there is nothing to mark.
  const thresholds = useMemo(() => (hasIndices ? thresholdLines(bands.data, hazard) : []), [hasIndices, bands.data, hazard]);
  const anyReadings = Object.values(telemetry).some((p) => p.length > 0);

  let body;
  if (!anyReadings && (connection === 'reconnecting' || connection === 'closed')) {
    body = <ErrorState message="No live connection. Readings resume when it reconnects." />;
  } else if (!anyReadings && !hasSnapshot) {
    body = <LoadingState rows={3} label="Loading readings" />;
  } else if (!anyReadings) {
    body = <EmptyState title="Readings appear here once the simulation runs." />;
  } else if (rows.length === 0) {
    body = <EmptyState title={`No readings yet for ${zoneId === null ? 'this zone' : zoneName(city, zoneId)}.`} />;
  } else {
    const chartHeight = size ? size.height - HEADINGS_PX : undefined;
    const rainHeight = chartHeight === undefined ? undefined : Math.round(chartHeight * 0.3);
    const indexHeight = chartHeight === undefined || rainHeight === undefined ? undefined : chartHeight - rainHeight;
    // A zone without soil probes or detector readings (a flood plain) charts its standing water instead.
    const soil = hasIndices || rows.some((r) => r.saturation !== null);
    const hasRain = rows.some((r) => r.rain !== null);
    const name = zoneId === null ? 'this zone' : zoneName(city, zoneId);
    body = (
      <div className="flex flex-col h-full min-h-0 px-2 pt-1">
        <h3 className="px-1 text-[11px] leading-4 font-medium text-ink-2">Rain intensity (mm/h)</h3>
        <div className="flex-[3] min-h-0">
          {hasRain
            ? <RainChart rows={rows} width={size?.width} height={rainHeight} />
            : <p className="px-1 text-[12px] text-ink-3">{`No rain gauge in ${name}.`}</p>}
        </div>
        <div className="flex items-center justify-between gap-3 px-1 mt-1">
          <h3 className="text-[11px] leading-4 font-medium text-ink-2">{hasIndices ? 'Indices' : soil ? 'Soil saturation' : 'Standing water (cm)'}</h3>
          {soil && <TimelineLegend hazard={hazard} indices={hasIndices} thresholds={thresholds.length > 0} />}
        </div>
        <div className="flex-[7] min-h-0">
          {soil
            ? <IndexChart rows={rows} thresholds={thresholds} markers={markers} width={size?.width} height={indexHeight} />
            : <WaterChart rows={rows} markers={markers} width={size?.width} height={indexHeight} />}
        </div>
      </div>
    );
  }

  const zoneSelect = zones.length > 0 && zoneId !== null ? (
    <select aria-label="Zone" className={selectClass} value={zoneId} onChange={(e) => { setTimelineZone(e.target.value); }}>
      {zones.map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
    </select>
  ) : undefined;

  return (
    <Panel title="Risk timeline" actions={zoneSelect} testId="risk-timeline">
      {body}
    </Panel>
  );
}
