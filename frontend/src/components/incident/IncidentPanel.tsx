import { useMemo, type ReactNode } from 'react';
import type { Incident } from '@/api/types';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { Panel } from '@/components/ui/Panel';
import { bandLabel } from '@/components/ui/bandLabel';
import { useSelectedIncident } from '@/hooks/useSelectedIncident';
import { stepOutput, zoneName } from '@/live/derive';
import { statusLabel } from '@/live/format';
import { useLiveStore } from '@/live/liveStore';
import type { TelemetryPoint } from '@/live/types';
import { useUiStore } from '@/ui/uiStore';
import { ReasoningTrace } from './ReasoningTrace';
import { SourceDrawer } from './SourceDrawer';
import { ThreatCard } from './ThreatCard';

const NO_TELEMETRY: TelemetryPoint[] = [];
const selectClass = 'h-6 max-w-[240px] rounded-[3px] border border-line bg-page px-1.5 text-[12px] text-ink';

/** The right column's top panel: the selected incident's threat card and the agent's reasoning for it. */
export function IncidentPanel() {
  const hasSnapshot = useLiveStore((s) => s.hasSnapshot);
  const connection = useLiveStore((s) => s.connection);
  const incidents = useLiveStore((s) => s.incidents);
  const city = useLiveStore((s) => s.city);
  const zoneState = useLiveStore((s) => s.zoneState);
  const selectIncident = useUiStore((s) => s.selectIncident);
  const { incident, run } = useSelectedIncident();
  const telemetry = useLiveStore((s) => (incident ? s.telemetry[incident.zone_id] : undefined)) ?? NO_TELEMETRY;

  const open = useMemo(() => Object.values(incidents).filter((i) => i.status === 'open'), [incidents]);
  const choices: Incident[] = incident && !open.includes(incident) ? [...open, incident] : open;
  const cascadeZones = useMemo(() => {
    const ids = stepOutput(run, 'cascade')?.affected_zone_ids ?? [];
    return (city?.zones ?? []).filter((z) => ids.includes(z.id));
  }, [run, city]);

  const switcher = choices.length > 1 && incident ? (
    <select aria-label="Incident" className={selectClass} value={incident.id} onChange={(e) => { selectIncident(e.target.value); }}>
      {choices.map((i) => (
        <option key={i.id} value={i.id}>{`${statusLabel(i.hazard)} in ${zoneName(city, i.zone_id)} (${bandLabel(i.band)})`}</option>
      ))}
    </select>
  ) : undefined;

  let body: ReactNode;
  if (!hasSnapshot) {
    body = connection === 'closed'
      ? <ErrorState message="Live connection closed before the city state arrived. Reload the page to reconnect." />
      : <LoadingState label="Waiting for city state" />;
  } else if (!incident) {
    body = <EmptyState title="No open incidents. Threats appear here when the detector opens an incident." />;
  } else {
    body = (
      <>
        <ThreatCard incident={incident} run={run} zone={city?.zones.find((z) => z.id === incident.zone_id)}
          zoneState={zoneState[incident.zone_id]} cascadeZones={cascadeZones} />
        <ReasoningTrace key={incident.id} incident={incident} telemetry={telemetry} city={city} />
      </>
    );
  }

  return (
    <Panel title="Incident" count={hasSnapshot ? open.length : undefined} actions={switcher}>
      {body}
      <SourceDrawer />
    </Panel>
  );
}
