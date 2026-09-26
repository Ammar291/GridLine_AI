import type { AgentRun, Incident, Zone, ZoneState } from '@/api/types';
import { KeyValue } from '@/components/ui/KeyValue';
import { SeverityChip } from '@/components/ui/SeverityChip';
import { IconDrop, IconSlope } from '@/components/ui/icons';
import { stepOutput } from '@/live/derive';
import { fmtIndex, fmtNumber, fmtPct, fmtSimTime } from '@/live/format';
import { CitationChip } from './CitationChip';
import { resolveCitation, runCitations } from './citations';

interface ThreatCardProps {
  incident: Incident;
  run: AgentRun | undefined;
  zone: Zone | undefined;
  zoneState: ZoneState | undefined;
  cascadeZones: Zone[];
}

const awaiting = (text: string) => <span className="text-ink-3">{text}</span>;

/** Detector facts for the incident plus the latest run's assessment and prediction, when they exist. */
export function ThreatCard({ incident, run, zone, zoneState, cascadeZones }: ThreatCardProps) {
  const assess = stepOutput(run, 'assess');
  const predict = stepOutput(run, 'predict');
  const citations = runCitations(run);
  const flood = incident.hazard === 'flood';
  const others = cascadeZones.filter((z) => z.id !== incident.zone_id);
  const population = (zone?.population ?? 0) + others.reduce((n, z) => n + z.population, 0);
  const onset = predict?.onset_sim_time ? `, onset ${fmtSimTime(predict.onset_sim_time)}` : '';

  return (
    <div className="flex flex-col gap-3 p-3 border-b border-line">
      <div className="flex items-center gap-2 min-w-0">
        {flood ? <IconDrop className="shrink-0 text-ink-2" /> : <IconSlope className="shrink-0 text-ink-2" />}
        <h3 className="condensed text-[15px] font-medium">{flood ? 'Flood risk' : 'Landslide risk'}</h3>
        <span className="text-ink-2 truncate">{zone?.name ?? incident.zone_id}</span>
        <SeverityChip band={incident.band} />
        <span className="ml-auto text-[11px] text-ink-3 tnum">Opened {fmtSimTime(incident.opened_sim_time)}</span>
      </div>
      <KeyValue
        columns={3}
        items={[
          { label: 'Confidence', value: assess ? fmtPct(assess.confidence) : awaiting('Awaiting assessment') },
          {
            label: 'Population at risk',
            value: zone ? (
              <>
                {fmtNumber(population)}
                {others.length > 0 && <span className="text-ink-3 text-[11px]">{` including ${others.map((z) => z.name).join(', ')}`}</span>}
              </>
            ) : awaiting('Not reported'),
          },
          { label: 'Estimated onset', value: predict ? `${predict.time_horizon}${onset}` : awaiting('Awaiting prediction') },
          {
            label: flood ? 'Flood index' : 'Landslide index',
            value: zoneState ? fmtIndex(flood ? zoneState.flood_index : zoneState.landslide_index) : '—',
          },
          { label: 'Saturation', value: zoneState ? fmtPct(zoneState.saturation) : '—' },
          { label: 'Rain intensity', value: zoneState ? `${String(Math.round(zoneState.rain_intensity_mm_h))} mm/h` : '—' },
        ]}
      />
      <div data-testid="contributing-factors" className="flex flex-col gap-1">
        <span className="text-[11px] text-ink-2">Contributing factors</span>
        {assess?.contributing_factors.length === 0 && awaiting('None reported by the assessment')}
        {assess && assess.contributing_factors.length > 0 && (
          <ul aria-label="Contributing factors" className="flex flex-wrap gap-1.5">
            {assess.contributing_factors.map((f) => (
              <li key={f.factor} className="inline-flex items-center gap-1.5 pl-2 rounded-[3px] bg-raised">
                <span className="text-[12px]">{`${f.factor}: ${f.value}`}</span>
                {f.citation_ids.map((id) => <CitationChip key={id} citation={resolveCitation(id, citations)} />)}
              </li>
            ))}
          </ul>
        )}
        {!assess && awaiting('Awaiting assessment')}
      </div>
    </div>
  );
}
