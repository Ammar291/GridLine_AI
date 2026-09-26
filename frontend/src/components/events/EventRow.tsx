import type { City, Event } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { describeEvent, eventGroup } from '@/live/describeEvent';
import { fmtSimTimeSec, fmtWall } from '@/live/format';
import { GROUP_BORDER, SEVERITY_TAG } from './eventGroups';

interface EventRowProps { event: Event; city: City | null; onSelectIncident: (id: string) => void }

/** One feed line: wall clock, sim time, the event in words, its sensor band when raised, and an incident tag. */
export function EventRow({ event, city, onSelectIncident }: EventRowProps) {
  const incidentId = event.incident_id ?? null;
  const group = eventGroup(event.event_type);
  const tick = event.event_type === 'sim.tick';
  const routine = group === 'reading' && (event.severity === 'info' || event.severity === 'low');
  const tag = SEVERITY_TAG[event.severity];
  const text = describeEvent(event, city);
  return (
    <li
      data-event-type={event.event_type}
      data-severity={event.severity}
      className={`gl-feed-in grid grid-cols-[56px_56px_1fr_auto_auto] items-center gap-2 min-h-6 pl-2.5 pr-3 border-l-2 ${GROUP_BORDER[group]}`}
    >
      <time dateTime={event.timestamp} title="Wall clock" className="tnum text-[11px] text-ink-3">{fmtWall(event.timestamp)}</time>
      <time dateTime={event.sim_time} title="Sim time" className="tnum text-[11px] text-ink-2">{fmtSimTimeSec(event.sim_time)}</time>
      <span className={`min-w-0 truncate text-[12px] ${tick ? 'text-ink-3' : routine ? 'text-ink-2' : 'text-ink'}`} title={text}>{text}</span>
      {tag ? <span className={`text-[11px] font-medium ${tag.className}`} title="Sensor band">{tag.label}</span> : <span />}
      {incidentId !== null ? (
        <Button size="sm" className="h-5 px-1.5 text-[11px]" title={`Show incident ${incidentId}`} onClick={() => { onSelectIncident(incidentId); }}>
          Incident
        </Button>
      ) : <span />}
    </li>
  );
}
