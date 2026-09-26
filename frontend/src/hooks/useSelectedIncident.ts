import type { AgentRun, Incident } from '@/api/types';
import { defaultIncidentId, latestRun } from '@/live/derive';
import { useLiveStore } from '@/live/liveStore';
import { useUiStore } from '@/ui/uiStore';

/** The incident the right column shows: the operator's selection if it still exists, else the default. */
export function useSelectedIncident(): { incident: Incident | undefined; incidentId: string | null; run: AgentRun | undefined; zoneId: string | null } {
  const selected = useUiStore((s) => s.selectedIncidentId);
  const incidents = useLiveStore((s) => s.incidents);
  const incidentId = selected !== null && selected in incidents ? selected : defaultIncidentId(incidents);
  const incident = incidentId === null ? undefined : incidents[incidentId];
  return { incident, incidentId, run: latestRun(incident), zoneId: incident?.zone_id ?? null };
}
