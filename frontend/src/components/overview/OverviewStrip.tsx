import { useMemo } from 'react';
import { bandLabel } from '@/components/ui/bandLabel';
import { activeThreats, cityStatus, defaultIncidentId, findOpenIncidentForZone, preventiveActions, resources, riskZones } from '@/live/derive';
import { useLiveStore } from '@/live/liveStore';
import { useUiStore } from '@/ui/uiStore';
import { statusLabel } from '@/live/format';
import { StatTile } from './StatTile';

const DASH = '—';

export function OverviewStrip() {
  const hasSnapshot = useLiveStore((s) => s.hasSnapshot);
  const zoneState = useLiveStore((s) => s.zoneState);
  const incidents = useLiveStore((s) => s.incidents);
  const actions = useLiveStore((s) => s.actions);
  const approvals = useLiveStore((s) => s.approvals);
  const assets = useLiveStore((s) => s.assets);
  const city = useLiveStore((s) => s.city);
  const selectIncident = useUiStore((s) => s.selectIncident);
  const selectEntity = useUiStore((s) => s.selectEntity);

  const status = useMemo(() => cityStatus(zoneState), [zoneState]);
  const threats = useMemo(() => activeThreats(incidents), [incidents]);
  const zones = useMemo(() => riskZones(zoneState, city), [zoneState, city]);
  const prevent = useMemo(() => preventiveActions(actions, approvals), [actions, approvals]);
  const res = useMemo(() => resources(assets), [assets]);
  const openCount = Object.values(incidents).filter((i) => i.status === 'open').length;
  const topIncident = defaultIncidentId(incidents);
  const selectTop = topIncident === null ? undefined : () => { selectIncident(topIncident); };
  const topZone = zones[0]?.zone.id;

  return (
    <div data-testid="overview-strip" aria-busy={!hasSnapshot} className="grid grid-cols-[auto_1.3fr_1fr_1fr_1fr_1fr_1.4fr] h-full bg-panel border-b border-line">
      <div className="flex flex-col justify-center px-4 border-r border-line">
        <h1 className="condensed text-[17px] font-semibold leading-5">GridLine AI</h1>
        <span className="text-[11px] text-ink-2">Nandipur emergency operations</span>
      </div>
      <StatTile label="City status" value={hasSnapshot ? status.label : DASH} band={hasSnapshot ? status.band : undefined}
        detail={hasSnapshot ? `Highest band across ${String(Object.keys(zoneState).length)} zones` : undefined} />
      <StatTile
        label="Active threats"
        value={hasSnapshot ? String(threats.reduce((n, t) => n + t.count, 0)) : DASH}
        detail={hasSnapshot ? (threats.length ? threats.map((t) => `${statusLabel(t.hazard)} ${String(t.count)}`).join(', ') : 'No open threats') : undefined}
        band={hasSnapshot ? threats[0]?.maxBand : undefined}
        onClick={selectTop}
      />
      <StatTile
        label="Risk zones"
        value={hasSnapshot ? String(zones.length) : DASH}
        detail={hasSnapshot ? (zones.length ? zones.map((z) => `${z.zone.name} (${bandLabel(z.state.band)})`).join(', ') : 'All zones normal') : undefined}
        onClick={topZone === undefined ? undefined : () => { selectEntity({ kind: 'zone', id: topZone }, findOpenIncidentForZone(incidents, topZone)); }}
      />
      <StatTile
        label="Preventive actions"
        value={hasSnapshot ? String(prevent.pending) : DASH}
        detail={hasSnapshot ? `${String(prevent.executed)} executed, ${String(prevent.verified)} verified, ${String(prevent.failed)} failed` : undefined}
      />
      <StatTile label="Active incidents" value={hasSnapshot ? String(openCount) : DASH} onClick={selectTop} />
      <StatTile
        label="Emergency resources"
        value={hasSnapshot ? `${String(res.crewsAvailable)} of ${String(res.crewsTotal)}` : DASH}
        detail={hasSnapshot
          ? `crews available, ${String(res.sheltersOpen)} shelters open, ${String(res.pumpsAtDepot)} of ${String(res.pumpsTotal)} pumps at depot`
          : undefined}
      />
    </div>
  );
}
