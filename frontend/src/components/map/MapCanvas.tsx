import { useCallback, useRef } from 'react';
import type { City } from '@/api/types';
import { findOpenIncidentForZone } from '@/live/derive';
import { useLiveStore } from '@/live/liveStore';
import { useUiStore, type EntityRef } from '@/ui/uiStore';
import { EntityPopover } from './EntityPopover';
import { LayerLegend } from './LayerLegend';
import { MapControls } from './MapControls';
import { entityDetails } from './entityDetails';
import { AssetsLayer } from './layers/AssetsLayer';
import { DrainageLayer } from './layers/DrainageLayer';
import { HillsLayer } from './layers/HillsLayer';
import { LabelsLayer } from './layers/LabelsLayer';
import { RoadsLayer } from './layers/RoadsLayer';
import { ThreatLayer } from './layers/ThreatLayer';
import { WaterLayer } from './layers/WaterLayer';
import { ZonesLayer } from './layers/ZonesLayer';
import { MAP_MOTION_CSS } from './mapStyles';
import { useMapData } from './useMapData';
import { useDragPan, useElementSize, useWheelZoom } from './useMapInteractions';
import { unitsPerPixel, useViewBox } from './useViewBox';

const BUTTON_ZOOM = 2;

/** The interactive SVG map. Mount with a `key` on the city's view box so a new geometry resets pan and zoom. */
export function MapCanvas({ city }: { city: City }) {
  const data = useMapData(city);
  const { viewBox, viewBoxAttr, zoomAt, panBy, fit } = useViewBox(city.view_box);
  const svgRef = useRef<SVGSVGElement>(null);
  const u = unitsPerPixel(viewBox, useElementSize(svgRef));
  useWheelZoom(svgRef, viewBox, zoomAt);
  const drag = useDragPan(u, panBy);

  const layers = useUiStore((s) => s.activeLayers);
  const toggleLayer = useUiStore((s) => s.toggleLayer);
  const selected = useUiStore((s) => s.selectedEntity);
  const selectEntity = useUiStore((s) => s.selectEntity);
  const incidents = useLiveStore((s) => s.incidents);

  const onSelect = useCallback((ref: EntityRef) => {
    selectEntity(ref, ref.kind === 'zone' ? findOpenIncidentForZone(incidents, ref.id) : undefined);
  }, [selectEntity, incidents]);
  const selectedId = (kind: EntityRef['kind']) => (selected?.kind === kind ? selected.id : null);
  const details = selected ? entityDetails(selected, data) : null;
  const cx = viewBox.x + viewBox.width / 2;
  const cy = viewBox.y + viewBox.height / 2;

  return (
    <div className="relative h-full w-full overflow-hidden bg-page" onKeyDown={(e) => { if (e.key === 'Escape') selectEntity(null); }}>
      <style href="gl-map-motion" precedence="default">{MAP_MOTION_CSS}</style>
      <svg
        ref={svgRef}
        role="img"
        aria-label="Map of Nandipur"
        viewBox={viewBoxAttr}
        preserveAspectRatio="xMidYMid meet"
        className="block h-full w-full touch-none select-none"
        onClick={(e) => { if (e.target === e.currentTarget) selectEntity(null); }}
        {...drag}
      >
        {layers.has('hills') && <HillsLayer features={data.features} />}
        {layers.has('water') && <WaterLayer features={data.features} u={u} />}
        {layers.has('zones') && <ZonesLayer zones={data.zones} selectedId={selectedId('zone')} onSelect={(id) => { onSelect({ kind: 'zone', id }); }} />}
        {layers.has('drainage') && (
          <DrainageLayer channels={data.channels} selectedId={selectedId('channel')} onSelect={(id) => { onSelect({ kind: 'channel', id }); }} />
        )}
        {layers.has('roads') && <RoadsLayer roads={data.roads} u={u} selectedId={selectedId('road')} onSelect={(id) => { onSelect({ kind: 'road', id }); }} />}
        <AssetsLayer data={data} layers={layers} u={u} selected={selected} onSelect={onSelect} />
        {layers.has('threats') && <ThreatLayer data={data} u={u} />}
        <LabelsLayer zones={data.zones} features={data.features} u={u} />
      </svg>
      <LayerLegend active={layers} onToggle={toggleLayer} />
      <MapControls onZoomIn={() => { zoomAt(BUTTON_ZOOM, cx, cy); }} onZoomOut={() => { zoomAt(1 / BUTTON_ZOOM, cx, cy); }} onFit={fit} />
      {details && <EntityPopover details={details} onClose={() => { selectEntity(null); }} />}
    </div>
  );
}
