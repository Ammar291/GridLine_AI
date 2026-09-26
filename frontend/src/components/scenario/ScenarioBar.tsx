import { useState } from 'react';
import { ApiError } from '@/api/client';
import { useCity, useLlmStatus, useSimulationControls } from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { IconPause, IconPlay, IconReset } from '@/components/ui/icons';
import { fmtSimTimeSec } from '@/live/format';
import { useLiveStore } from '@/live/liveStore';
import { ConnectionDot } from './ConnectionDot';
import { ProviderBadge } from './ProviderBadge';

const SPEEDS = [0.25, 0.5, 1, 2, 4, 10];
const DEFAULT_SCENARIO = 'hillside_landslide';
const FALLBACK_SCENARIOS = [{ id: DEFAULT_SCENARIO, name: 'Hillside landslide' }];
interface MutationState { isError: boolean; isPending: boolean; error: ApiError | null }
const selectClass = 'h-7 rounded-[3px] border border-line bg-page px-2 text-[12px] text-ink disabled:opacity-50';

function errorText(label: string, err: unknown): string {
  return err instanceof ApiError ? `${label} failed (${String(err.status)}). Try again.` : `${label} failed. Try again.`;
}

export function ScenarioBar() {
  const sim = useLiveStore((s) => s.sim);
  const mode = useLiveStore((s) => s.mode);
  const connection = useLiveStore((s) => s.connection);
  const storeLlm = useLiveStore((s) => s.llm);
  const city = useCity();
  const llm = useLlmStatus();
  const controls = useSimulationControls();
  const [picked, setPicked] = useState<string | null>(null);

  const scenarios = city.data?.scenarios ?? [];
  const scenarioId = picked ?? sim.scenario ?? scenarios[0]?.id ?? DEFAULT_SCENARIO;
  const injections = scenarios.find((s) => s.id === scenarioId)?.injections ?? [];
  const paused = !sim.running && sim.tick > 0 && sim.scenario !== null;

  const labelled: [string, MutationState][] = [
    ['Start', controls.start], ['Pause', controls.pause], ['Resume', controls.resume],
    ['Reset', controls.reset], ['Speed change', controls.setSpeed], ['Inject', controls.inject],
  ];
  const failed = labelled.find(([, m]) => m.isError);
  const busy = labelled.some(([, m]) => m.isPending);

  const onPrimary = () => {
    if (sim.running) controls.pause.mutate();
    else if (paused) controls.resume.mutate();
    else controls.start.mutate({ scenario: scenarioId, speed: sim.speed });
  };

  return (
    <div className="flex items-center gap-3 h-full px-4 bg-panel border-t border-line text-[12px]">
      <label className="flex items-center gap-2">
        <span className="text-ink-2">Scenario</span>
        <select aria-label="Scenario" className={selectClass} value={scenarioId} disabled={sim.running}
          onChange={(e) => { setPicked(e.target.value); }}>
          {(scenarios.length > 0 ? scenarios : FALLBACK_SCENARIOS).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      </label>
      <Button variant="primary" size="sm" onClick={onPrimary} disabled={busy} className="w-20 justify-center">
        {sim.running ? <IconPause /> : <IconPlay />}
        {sim.running ? 'Pause' : paused ? 'Resume' : 'Start'}
      </Button>
      <Button size="sm" onClick={() => { controls.reset.mutate(); }} disabled={busy}>
        <IconReset />
        Reset
      </Button>
      <label className="flex items-center gap-2">
        <span className="text-ink-2">Speed</span>
        <select aria-label="Speed" className={selectClass} value={sim.speed}
          onChange={(e) => { controls.setSpeed.mutate(Number(e.target.value)); }}>
          {SPEEDS.map((s) => <option key={s} value={s}>{`${String(s)}×`}</option>)}
        </select>
      </label>
      <label className="flex items-center gap-2">
        <span className="text-ink-2">Inject</span>
        <select aria-label="Inject" className={selectClass} value="" disabled={mode === 'mock' || injections.length === 0}
          onChange={(e) => { if (e.target.value) controls.inject.mutate({ id: e.target.value }); }}>
          <option value="">Choose an event</option>
          {injections.map((i) => <option key={i.id} value={i.id}>{i.label}</option>)}
        </select>
      </label>
      {failed && <span role="alert" className="text-band-critical-text">{errorText(failed[0], failed[1].error)}</span>}
      <div className="ml-auto flex items-center gap-4">
        <span className="tnum text-ink" title="Simulation time">
          <span className="text-ink-2 mr-1.5">Sim time</span>
          {fmtSimTimeSec(sim.simTime)}
        </span>
        <ConnectionDot connection={connection} />
        <ProviderBadge llm={llm.data ?? storeLlm} />
      </div>
    </div>
  );
}
