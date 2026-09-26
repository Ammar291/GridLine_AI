import { useState } from 'react';
import type { City, Incident } from '@/api/types';
import { EmptyState } from '@/components/ui/EmptyState';
import type { TelemetryPoint } from '@/live/types';
import { RunAccordion } from './RunAccordion';
import { RunDetail } from './RunDetail';

interface ReasoningTraceProps { incident: Incident; telemetry: TelemetryPoint[]; city: City | null }

const NO_TELEMETRY: TelemetryPoint[] = [];

/**
 * Every agent run for the incident, newest first. The latest is open unless the operator closed it.
 * Reading deltas cover the telemetry the store holds, so only the latest run shows them.
 */
export function ReasoningTrace({ incident, telemetry, city }: ReasoningTraceProps) {
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  if (incident.runs.length === 0) {
    return <EmptyState title="No agent run yet for this incident. Reasoning appears here as each node finishes." />;
  }
  const chronological = [...incident.runs].sort((a, b) => a.started_at.localeCompare(b.started_at));
  const latestId = chronological.at(-1)?.id;
  const numbered = chronological.map((run, i) => ({ run, number: i + 1 })).reverse();

  return (
    <div className="flex flex-col">
      {numbered.map(({ run, number }) => {
        const expanded = toggled[run.id] ?? run.id === latestId;
        return (
          <RunAccordion key={run.id} run={run} number={number} expanded={expanded}
            onToggle={() => { setToggled((t) => ({ ...t, [run.id]: !expanded })); }}>
            <RunDetail incident={incident} run={run} telemetry={run.id === latestId ? telemetry : NO_TELEMETRY} city={city} />
          </RunAccordion>
        );
      })}
    </div>
  );
}
