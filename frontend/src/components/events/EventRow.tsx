import type { City, Event } from '@/api/types';
import { Button } from '@/components/ui/Button';
import { describeEvent, eventGroup } from '@/live/describeEvent';
import { fmtSimTimeSec, fmtWall } from '@/live/format';
import { GROUP_BORDER } from './eventGroups';

interface EventRowProps { event: Event; city: City | null; onSelectIncident: (id: string) => void }

/** One feed line: wall clock, sim time, the event in words, and an incident tag when the event belongs to one. */
export function EventRow({ event, city, onSelectIncident }: EventRowProps) {
  const incidentId = event.incident_id ?? null;
  const tick = event.type === 'sim.tick';
  const text = describeEvent(event, city);
  return (
    <li
      data-event-type={event.type}
      className={`gl-feed-in grid grid-cols-[56px_56px_1fr_auto] items-center gap-2 min-h-6 pl-2.5 pr-3 border-l-2 ${GROUP_BORDER[eventGroup(event.type)]}`}
    >
      <time dateTime={event.ts} title="Wall clock" className="tnum text-[11px] text-ink-3">{fmtWall(event.ts)}</time>
      <time dateTime={event.sim_time ?? undefined} title="Sim time" className="tnum text-[11px] text-ink-2">{fmtSimTimeSec(event.sim_time)}</time>
      <span className={`min-w-0 truncate text-[12px] ${tick ? 'text-ink-3' : 'text-ink'}`} title={text}>{text}</span>
      {incidentId !== null ? (
        <Button size="sm" className="h-5 px-1.5 text-[11px]" title={`Show incident ${incidentId}`} onClick={() => { onSelectIncident(incidentId); }}>
          Incident
        </Button>
      ) : <span />}
    </li>
  );
}
