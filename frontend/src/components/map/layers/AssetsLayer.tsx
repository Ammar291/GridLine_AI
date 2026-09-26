import type { CSSProperties, ReactNode } from 'react';
import type { XY } from '@/api/types';
import type { LiveCrew } from '@/live/assets';
import { fmtNumber, statusLabel } from '@/live/format';
import type { EntityRef, LayerId } from '@/ui/uiStore';
import { ACCENT, CREW_FILL, INK, INK_2, INK_3, LINE_STRONG, NON_SCALING, OK, PAGE, RAISED, TEXT_HALO, WATER, bandColor } from '../mapStyles';
import { crewNumber, selectable } from '../mapUtils';
import type { MapData } from '../useMapData';

interface AssetsLayerProps {
  data: MapData;
  layers: ReadonlySet<LayerId>;
  u: number;
  selected: EntityRef | null;
  onSelect: (ref: EntityRef) => void;
}

interface MarkerProps {
  xy: XY; u: number; label: string; testId: string; selected: boolean; onSelect: () => void; children: ReactNode;
  /** Hit-area radius in px; small for sensor dots so the bridge or asset they sit on stays clickable. */
  hit?: number;
  /** Offset in viewBox units the marker drifts toward (crews on the move). */
  drift?: XY | null;
}

/** Pixel-sized marker art at a map point: keyboard selectable, with a hit area larger than the glyph. */
function Marker({ xy, u, label, testId, selected, onSelect, children, drift, hit = 12 }: MarkerProps) {
  const motion = drift ? ({ '--dx': `${String(drift.x)}px`, '--dy': `${String(drift.y)}px` } as CSSProperties) : undefined;
  return (
    <g transform={`translate(${String(xy.x)} ${String(xy.y)})`}>
      <g className={drift ? 'gl-crew-move' : undefined} style={motion}>
        <g transform={`scale(${String(u)})`} data-testid={testId} {...selectable(label, onSelect)}>
          <circle r={hit} fill="transparent" />
          {selected && <circle r={hit + 2} fill="none" stroke={ACCENT} strokeWidth={2} />}
          {children}
          <title>{label}</title>
        </g>
      </g>
    </g>
  );
}

const DRIFT_PX = 24;
const MOVING: readonly LiveCrew['status'][] = ['dispatched', 'en_route'];

function crewDrift(crew: LiveCrew, target: XY | undefined, u: number): XY | null {
  if (!MOVING.includes(crew.status) || !target) return null;
  const dx = target.x - crew.xy.x;
  const dy = target.y - crew.xy.y;
  const dist = Math.hypot(dx, dy);
  if (dist === 0) return null;
  const step = Math.min(dist, DRIFT_PX * u);
  return { x: (dx / dist) * step, y: (dy / dist) * step };
}

const ER_TONE = { normal: LINE_STRONG, busy: bandColor('warning'), overwhelmed: bandColor('critical') } as const;

export function AssetsLayer({ data, layers, u, selected, onSelect }: AssetsLayerProps) {
  const is = (kind: EntityRef['kind'], id: string) => selected?.kind === kind && selected.id === id;
  const pick = (kind: EntityRef['kind'], id: string) => () => { onSelect({ kind, id }); };
  /** A crew away from its base is drawn at its base with a line to the zone it is working in. */
  const awayAt = (c: LiveCrew) => (c.location_zone_id !== c.base_zone_id ? data.zoneById.get(c.location_zone_id)?.zone.label_xy : undefined);
  const atDepot = data.depot.units.filter((p) => p.status === 'available').length;
  const away = data.crews.filter((c) => awayAt(c));

  return (
    <>
      {layers.has('construction') && (
        <g data-layer="construction">
          {data.projects.map((p) => {
            const tone = p.status === 'halted' ? INK_3 : INK;
            const label = `${p.name}, ${statusLabel(p.status)}, ${String(Number(p.excavation_depth_m.toFixed(1)))} of ${String(p.planned_depth_m)} m dug`;
            return (
              <Marker key={p.id} xy={p.xy} u={u} testId={`project-${p.id}`} label={label}
                selected={is('project', p.id)} onSelect={pick('project', p.id)}>
                <rect x={-7} y={-7} width={14} height={14} fill={RAISED} stroke={tone} strokeWidth={1.5} />
                <path d="M-7 1 L1 -7 M-3 7 L7 -3" stroke={tone} strokeWidth={1.5} />
              </Marker>
            );
          })}
        </g>
      )}
      {layers.has('hospitals') && (
        <g data-layer="hospitals">
          {data.hospitals.map((h) => (
            <Marker key={h.id} xy={h.xy} u={u} testId={`hospital-${h.id}`}
              label={`${h.name}, ${fmtNumber(h.beds_occupied)} of ${fmtNumber(h.beds_total)} beds occupied, ER ${h.er_status}`}
              selected={is('hospital', h.id)} onSelect={pick('hospital', h.id)}>
              <circle r={9} fill={RAISED} stroke={ER_TONE[h.er_status]} strokeWidth={h.er_status === 'normal' ? 1 : 2} />
              <path d="M0 -5 V5 M-5 0 H5" stroke={INK} strokeWidth={2} />
            </Marker>
          ))}
        </g>
      )}
      {layers.has('shelters') && (
        <g data-layer="shelters">
          {data.shelters.map((s) => {
            const open = s.status !== 'closed';
            return (
              <Marker key={s.id} xy={s.xy} u={u} testId={`shelter-${s.id}`}
                label={`${s.name}, ${s.status}, ${fmtNumber(s.occupancy)} of ${fmtNumber(s.capacity)} places used`}
                selected={is('shelter', s.id)} onSelect={pick('shelter', s.id)}>
                <path d="M-8 0 L0 -8 L8 0 V7 H-8 Z" fill={open ? OK : RAISED} stroke={open ? PAGE : INK_2} strokeWidth={1.5} strokeLinejoin="round" />
              </Marker>
            );
          })}
        </g>
      )}
      {layers.has('crews') && (
        <g data-layer="crews">
          {away.map((c) => {
            const t = awayAt(c);
            return t ? (
              <line key={`route-${c.id}`} data-crew-route={c.id} x1={c.xy.x} y1={c.xy.y} x2={t.x} y2={t.y} stroke={ACCENT} strokeOpacity={0.7}
                strokeWidth={1.5} strokeDasharray="3 4" pointerEvents="none" {...NON_SCALING} />
            ) : null;
          })}
          <Marker xy={data.depot.xy} u={u} testId="pump-depot" label={`Pump depot, ${String(atDepot)} of ${String(data.depot.units.length)} mobile pumps available`}
            selected={is('pump_depot', data.depot.zone_id)} onSelect={pick('pump_depot', data.depot.zone_id)}>
            <rect x={-8} y={-7} width={16} height={14} rx={2} fill={RAISED} stroke={WATER} strokeWidth={1.5} />
            <text y={4} textAnchor="middle" fontSize={10} fontWeight={600} fill={INK}>P</text>
            <text x={11} y={4} fontSize={11} fill={INK} {...TEXT_HALO}>{atDepot}</text>
          </Marker>
          {data.crews.map((c) => (
            <Marker key={c.id} xy={c.xy} u={u} testId={`crew-${c.id}`} label={`${c.name}, ${statusLabel(c.status)}${c.task ? `, ${c.task}` : ''}`}
              selected={is('crew', c.id)} onSelect={pick('crew', c.id)} drift={crewDrift(c, awayAt(c), u)}>
              <path d="M0 -9 L8 6 L0 2 L-8 6 Z" fill={CREW_FILL[c.status]} stroke={PAGE} strokeWidth={1.5} strokeLinejoin="round" />
              <text x={10} y={4} fontSize={11} fontWeight={600} fill={INK} {...TEXT_HALO}>{crewNumber(c.id)}</text>
            </Marker>
          ))}
        </g>
      )}
      {layers.has('sensors') && (
        <g data-layer="sensors">
          {data.sensors.map((s) => (
            <Marker key={s.id} xy={s.xy} u={u} testId={`sensor-${s.id}`} label={`${s.id} ${s.name}, ${s.reading?.text ?? 'no reading yet'}`}
              selected={is('sensor', s.id)} onSelect={pick('sensor', s.id)} hit={6}>
              <circle r={3} fill={INK_3} stroke={PAGE} strokeWidth={1} />
            </Marker>
          ))}
        </g>
      )}
    </>
  );
}
